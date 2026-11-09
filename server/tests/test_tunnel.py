from foxygram.config import ServerConfig, TunnelConfig, ensure_config, load_config
from foxygram.tunnel import Tunnel


def make(tmp_path):
    return Tunnel(TunnelConfig(), ServerConfig(api_port=8787), tmp_path / "cloudflared.yml")


def named(tmp_path, **overrides):
    settings = {"mode": "named", "tunnel_id": "abc-123", "credentials_file": "C:/data/tunnel.json", **overrides}
    return Tunnel(
        TunnelConfig(**settings),
        ServerConfig(api_port=8787, public_url="https://tlg.example.com"),
        tmp_path / "cloudflared.yml",
    )


def test_never_falls_back_to_the_machine_wide_cloudflared_config(tmp_path):
    tunnel = make(tmp_path)
    command = tunnel.command("cloudflared")
    assert command[command.index("--config") + 1] == str(tunnel.config_file)
    assert command[command.index("--url") + 1] == "http://127.0.0.1:8787"


def test_picks_up_the_assigned_address(tmp_path):
    tunnel = make(tmp_path)
    tunnel.note_output(b"INF |  https://brave-fox-river.trycloudflare.com   |")
    assert tunnel.url == "https://brave-fox-river.trycloudflare.com"


def test_ignores_cloudflares_own_endpoint_in_error_output(tmp_path):
    tunnel = make(tmp_path)
    tunnel.note_output(b'ERR failed to request quick Tunnel: Post "https://api.trycloudflare.com/tunnel": EOF')
    assert tunnel.url == ""


def test_named_tunnel_uses_its_own_config_and_keeps_the_fixed_address(tmp_path):
    tunnel = named(tmp_path)
    assert tunnel.wanted()
    assert tunnel.url == "https://tlg.example.com"
    command = tunnel.command("cloudflared")
    assert command[command.index("--config") + 1] == str(tunnel.config_file)
    assert command[-1] == "run"
    assert "--url" not in command


def test_named_tunnel_publishes_only_the_phone_api(tmp_path):
    text = named(tmp_path).config_text()
    assert "tunnel: abc-123\n" in text
    assert 'credentials-file: "C:/data/tunnel.json"\n' in text
    assert "hostname: tlg.example.com\n" in text
    assert "service: http://127.0.0.1:8787\n" in text
    assert text.endswith("- service: http_status:404\n")


def write_credentials_setting(home, value):
    path = ensure_config(home)
    path.write_text(path.read_text(encoding="utf-8").replace('credentials_file = ""', f'credentials_file = "{value}"'), encoding="utf-8")


def test_relative_credentials_file_follows_the_data_folder(tmp_path):
    write_credentials_setting(tmp_path, "tunnel.json")
    assert load_config(tmp_path).tunnel.credentials_file == (tmp_path / "tunnel.json").as_posix()


def test_absolute_credentials_file_is_left_alone(tmp_path):
    write_credentials_setting(tmp_path, "C:/elsewhere/tunnel.json")
    assert load_config(tmp_path).tunnel.credentials_file == "C:/elsewhere/tunnel.json"


def test_named_tunnel_without_its_settings_does_not_start(tmp_path):
    assert not named(tmp_path, tunnel_id="").wanted()
