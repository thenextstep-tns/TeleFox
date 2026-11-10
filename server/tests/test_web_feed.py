"""The browser client's message feed, run in Node exactly as the page has it.

Files sent together as one group (a driver sending two permits, say) must show as separate messages, each with its file;
only photos and videos share one grid.
"""
import json
import shutil
import subprocess

import pytest

from foxygram.web_page import PAGE

node = shutil.which("node")


def js_function(name: str) -> str:
    """The source of one top-level function of the page, found by matching its braces."""
    start = PAGE.index(f"\nfunction {name}(") + 1
    depth, i = 0, PAGE.index("{", start)
    while True:
        if PAGE[i] == "{":
            depth += 1
        elif PAGE[i] == "}":
            depth -= 1
            if depth == 0:
                return PAGE[start:i + 1]
        i += 1


def feed(messages: list[dict]) -> list[dict]:
    script = "\n".join([
        "const dayOf = epoch => Math.floor(epoch / 86400);",
        "const dayHeader = epoch => 'day ' + dayOf(epoch);",
        js_function("sortedIds"), js_function("sameGroup"), js_function("buildFeed"),
        f"const list = {json.dumps(messages)};",
        "const view = { msgs: new Map(list.map(m => [m.id, m])), chat: { kind: 'group' }, firstUnread: null };",
        "process.stdout.write(JSON.stringify(buildFeed(view).filter(r => r.t === 'msg').map(r => r.m)));",
    ])
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(done.stdout)


def message(id_: int, body: dict, album: str) -> dict:
    return {"id": id_, "chat_id": -100, "date": 1794345124, "out": False, "sender": {"id": 7, "name": "Nick"}, "body": body,
            "reply": None, "forward": None, "album": album, "reactions": []}


def document(file_id: int, name: str) -> dict:
    return {"type": "document", "file": file_id, "name": name, "size": 43041, "mime": "application/pdf", "thumb": None,
            "caption": {"text": "", "spans": []}}


def photo(file_id: int) -> dict:
    return {"type": "photo", "image": {"file": file_id, "w": 800, "h": 600}, "caption": {"text": "", "spans": []}}


@pytest.mark.skipif(node is None, reason="needs Node to run the page's script")
def test_pdfs_sent_together_each_show_as_a_file():
    shown = feed([message(1, document(3216, "KS permit truck 1442.pdf"), "143547"),
                  message(2, document(3215, "MO permit truck 1442.pdf"), "143547")])
    assert [m["body"]["type"] for m in shown] == ["document", "document"]
    assert [m["body"]["name"] for m in shown] == ["KS permit truck 1442.pdf", "MO permit truck 1442.pdf"]


@pytest.mark.skipif(node is None, reason="needs Node to run the page's script")
def test_photos_sent_together_still_share_one_grid():
    shown = feed([message(1, photo(1), "99"), message(2, photo(2), "99"), message(3, document(5, "x.pdf"), "0")])
    assert [m["body"]["type"] for m in shown] == ["album", "document"]
    assert shown[0]["ids"] == [1, 2] and len(shown[0]["body"]["items"]) == 2
