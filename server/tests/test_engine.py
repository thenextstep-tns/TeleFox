import json
import sys
from pathlib import Path

import pytest

from foxygram.config import ClaudeConfig
from foxygram.db import Database
from foxygram.engine import ClaudeEngine, EngineError, EnginePaused, build_arguments

SCHEMA = {"type": "object"}

FAKE = r"""
import json, os, sys
mode = open(os.environ["FAKE_MODE"]).read().strip() if os.environ.get("FAKE_MODE") else "ok"
record = os.environ.get("FAKE_RECORD")
stdin = sys.stdin.buffer.read().decode("utf-8")
if record:
    open(record, "w", encoding="utf-8").write(json.dumps({
        "argv": sys.argv[1:], "stdin": stdin, "cwd": os.getcwd(),
        "api_key": os.environ.get("ANTHROPIC_API_KEY"),
    }))
if mode == "ok":
    print(json.dumps({"type":"result","subtype":"success","is_error":False,"result":"",
                      "structured_output":{"a":1},"usage":{"input_tokens":10,"output_tokens":5}}))
elif mode == "login":
    print(json.dumps({"type":"result","subtype":"success","is_error":True,"result":"Not logged in · Please run /login"}))
    sys.exit(1)
elif mode == "limit":
    print(json.dumps({"type":"result","is_error":True,"result":"You've hit your weekly usage limit"}))
    sys.exit(1)
elif mode == "garbage":
    print("not json")
elif mode == "noschema":
    print(json.dumps({"type":"result","is_error":False,"result":"I declined"}))
elif mode == "sleep":
    import time; time.sleep(30)
"""


@pytest.fixture
def harness(tmp_path, monkeypatch):
    script = tmp_path / "fake_claude.py"
    script.write_text(FAKE, encoding="utf-8")
    launcher = tmp_path / "fake.bin"
    mode_file = tmp_path / "mode"
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_MODE", str(mode_file))
    monkeypatch.setenv("FAKE_RECORD", str(record))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-be-removed")
    mode_file.write_text("ok")
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    db = Database(tmp_path / "t.db")

    import foxygram.engine as module

    real = module.asyncio.create_subprocess_exec

    async def spawn(_exe, *args, **kwargs):
        return await real(sys.executable, str(script), *args, **kwargs)

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(module, "resolve_command", lambda _c: launcher)
    return {"db": db, "sandbox": sandbox, "mode": mode_file, "record": record}


def engine_for(harness, **over):
    return ClaudeEngine(ClaudeConfig(**over), harness["db"], harness["sandbox"])


def test_arguments_disable_every_tool():
    args = build_arguments(ClaudeConfig(), SCHEMA, "sys")
    assert args[args.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in args
    assert args[args.index("--setting-sources") + 1] == ""
    assert "--no-session-persistence" in args
    assert "--bare" not in args  # bare mode cannot use your plan login


async def test_success_returns_structured_output(harness):
    assert await engine_for(harness).run("sys", SCHEMA, "hello") == {"a": 1}
    row = harness["db"].one("SELECT ok, input_tokens, output_tokens FROM claude_calls")
    assert row == {"ok": 1, "input_tokens": 10, "output_tokens": 5}


async def test_message_goes_only_through_stdin(harness):
    secret = "текст незнакомца $(rm -rf /)"
    await engine_for(harness).run("sys", SCHEMA, secret)
    record = json.loads(Path(harness["record"]).read_text(encoding="utf-8"))
    assert record["stdin"] == secret
    assert secret not in " ".join(record["argv"])


async def test_runs_in_sandbox_without_api_key(harness):
    await engine_for(harness).run("sys", SCHEMA, "x")
    record = json.loads(Path(harness["record"]).read_text(encoding="utf-8"))
    assert Path(record["cwd"]).resolve() == harness["sandbox"].resolve()
    assert record["api_key"] is None


async def test_login_problem_pauses(harness):
    harness["mode"].write_text("login")
    engine = engine_for(harness)
    with pytest.raises(EnginePaused):
        await engine.run("sys", SCHEMA, "x")
    assert engine.status().state == "login_needed"
    with pytest.raises(EnginePaused):  # stays paused without trying again
        await engine.run("sys", SCHEMA, "x")
    assert harness["db"].scalar("SELECT COUNT(*) FROM claude_calls") == 1


async def test_weekly_limit_pauses(harness):
    harness["mode"].write_text("limit")
    engine = engine_for(harness)
    with pytest.raises(EnginePaused):
        await engine.run("sys", SCHEMA, "x")
    assert engine.status().state == "quota"


@pytest.mark.parametrize("mode", ["garbage", "noschema"])
async def test_bad_output_is_retryable(harness, mode):
    harness["mode"].write_text(mode)
    with pytest.raises(EngineError):
        await engine_for(harness).run("sys", SCHEMA, "x")


async def test_timeout_kills_and_retries(harness):
    harness["mode"].write_text("sleep")
    with pytest.raises(EngineError):
        await engine_for(harness, timeout_seconds=1).run("sys", SCHEMA, "x")


async def test_hourly_cap_stops_calls(harness):
    engine = engine_for(harness, max_calls_per_hour=2)
    await engine.run("sys", SCHEMA, "x")
    await engine.run("sys", SCHEMA, "x")
    with pytest.raises(EnginePaused):
        await engine.run("sys", SCHEMA, "x")
    assert engine.status().state == "capped"
