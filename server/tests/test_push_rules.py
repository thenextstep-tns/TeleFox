import base64
import json
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from foxygram.push import encrypt
from foxygram.service import pairing_uri, should_push
from foxygram.telegram.messages import Parsed, chat_kind, content_of, parse, preview
from foxygram.telegram.session import ChatInfo

from .conftest import add_chat, settle


def parsed(**over):
    base = dict(chat_id=1, message_id=2, date=int(time.time()), sender_id=3, outgoing=False, kind="text",
                text="hi", reply_to=0, mention=False, pending=False)
    return Parsed(**{**base, **over})


def info(muted=False):
    return ChatInfo(1, "t", "group", {"use_default_mute_for": False, "mute_for": 3600 if muted else 0,
                                      "use_default_disable_mention_notifications": True})


def test_normal_message_pushes():
    assert should_push(parsed(), info(), {}, time.time())


def test_own_message_never_pushes():
    assert not should_push(parsed(outgoing=True), info(), {}, time.time())


def test_muted_chat_stays_silent():
    assert not should_push(parsed(), info(muted=True), {}, time.time())


def test_mention_breaks_through_mute():
    assert should_push(parsed(mention=True), info(muted=True), {}, time.time())


def test_mention_respects_scope_setting():
    scopes = {"notificationSettingsScopeGroupChats": {"disable_mention_notifications": True}}
    assert not should_push(parsed(mention=True), info(muted=True), scopes, time.time())


def test_scope_default_mute_applies():
    chat = ChatInfo(1, "t", "channel", {"use_default_mute_for": True})
    scopes = {"notificationSettingsScopeChannelChats": {"mute_for": 2147483647}}
    assert not should_push(parsed(), chat, scopes, time.time())


def test_catch_up_after_sleep_is_silent():
    assert not should_push(parsed(date=int(time.time()) - 3600), info(), {}, time.time())


def test_ciphertext_roundtrip():
    key = bytes(range(32))
    sealed = encrypt(key, {"t": "msg", "text": "привет"})
    pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
    plain = AESGCM(key).decrypt(
        base64.urlsafe_b64decode(pad(sealed["n"])), base64.urlsafe_b64decode(pad(sealed["c"])), None
    )
    assert json.loads(plain)["text"] == "привет"
    assert "привет" not in json.dumps(sealed, ensure_ascii=False)


def test_parse_message():
    p = parse({
        "chat_id": 5, "id": 9, "date": 100, "is_outgoing": False,
        "sender_id": {"@type": "messageSenderUser", "user_id": 77},
        "reply_to": {"@type": "messageReplyToMessage", "message_id": 4},
        "contains_unread_mention": True,
        "content": {"@type": "messagePhoto", "caption": {"text": "инвойс"}},
    })
    assert (p.kind, p.text, p.sender_id, p.reply_to, p.mention, p.pending) == ("photo", "инвойс", 77, 4, True, False)


def test_preview_labels():
    assert preview("voice", "") == "Голосовое сообщение"
    assert preview("photo", "x") == "Фото: x"
    assert preview("text", "abc") == "abc"


def test_kinds():
    assert content_of({"@type": "messagePinMessage"}) == ("service", "")
    assert chat_kind({"@type": "chatTypeSupergroup", "is_channel": True}) == "channel"
    assert chat_kind({"@type": "chatTypeSupergroup", "is_channel": False}) == "group"


def test_pairing_contains_everything(config):
    uri = pairing_uri(config, "https://x.example")
    assert uri.startswith("foxygram://pair?d=")
    body = uri.split("d=")[1]
    data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    assert data["u"] == "https://x.example" and data["i"] == 12345 and data["h"] == "abc"
    assert len(base64.b64decode(data["k"])) == 32


def message(chat_id=100, message_id=1, text="привет", outgoing=False):
    return {"chat_id": chat_id, "id": message_id, "date": int(time.time()), "is_outgoing": outgoing,
            "sender_id": {"@type": "messageSenderUser", "user_id": 7},
            "content": {"@type": "messageText", "text": {"text": text}}}


async def test_unselected_chat_pushes_but_stores_nothing(service):
    add_chat(service, ai=False)
    await service.on_message(message())
    await settle()
    assert len(service.pusher.sent) == 1
    assert service.db.scalar("SELECT COUNT(*) FROM messages") == 0


async def test_selected_chat_is_stored(service):
    add_chat(service, ai=True)
    await service.on_message(message())
    await settle()
    assert service.db.scalar("SELECT COUNT(*) FROM messages") == 1


async def test_read_elsewhere_clears_notification(service):
    add_chat(service, ai=False)
    await service.on_message(message())
    await settle()
    await service.on_read(100, 0)
    await settle()
    assert service.pusher.sent[-1] == {"t": "clear", "chat": "100"}


async def test_read_without_notification_sends_nothing(service):
    add_chat(service, ai=False)
    await service.on_read(100, 0)
    await settle()
    assert service.pusher.sent == []
