from foxygram.config import ServerConfig, TunnelConfig
from foxygram.tunnel import Tunnel


def make(tmp_path):
    return Tunnel(TunnelConfig(), ServerConfig(api_port=8787), tmp_path / "cloudflared.yml")


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
