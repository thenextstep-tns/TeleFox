import base64
import json
import time

from foxygram.service import pairing_uri
from foxygram.telegram.messages import chat_kind, content_of, parse

from .conftest import add_chat


def test_parse_message():
    p = parse({
        "chat_id": 5, "id": 9, "date": 100, "is_outgoing": False,
        "sender_id": {"@type": "messageSenderUser", "user_id": 77},
        "reply_to": {"@type": "messageReplyToMessage", "message_id": 4},
        "content": {"@type": "messagePhoto", "caption": {"text": "инвойс"}},
    })
    assert (p.kind, p.text, p.sender_id, p.reply_to, p.pending) == ("photo", "инвойс", 77, 4, False)


def test_sending_message_is_pending():
    p = parse({"chat_id": 1, "id": 1, "sending_state": {"@type": "messageSendingStatePending"},
               "content": {"@type": "messageText", "text": {"text": "x"}}})
    assert p.pending


def test_kinds():
    assert content_of({"@type": "messagePinMessage"}) == ("service", "")
    assert content_of({"@type": "messageDocument", "document": {"file_name": "a.pdf"}}) == ("document", "a.pdf")
    assert chat_kind({"@type": "chatTypeSupergroup", "is_channel": True}) == "channel"
    assert chat_kind({"@type": "chatTypeSupergroup", "is_channel": False}) == "group"


def test_pairing_contains_everything(config):
    uri = pairing_uri(config, "https://x.example")
    assert uri.startswith("foxygram://pair?d=")
    body = uri.split("d=")[1]
    data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    assert data == {"u": "https://x.example", "t": config.secrets.api_token, "i": 12345, "h": "abc"}


def message(chat_id=100, message_id=1, text="привет", outgoing=False):
    return {"chat_id": chat_id, "id": message_id, "date": int(time.time()), "is_outgoing": outgoing,
            "sender_id": {"@type": "messageSenderUser", "user_id": 7},
            "content": {"@type": "messageText", "text": {"text": text}}}


async def test_unselected_chat_is_not_stored(service):
    add_chat(service, ai=False)
    await service.on_message(message())
    assert service.db.scalar("SELECT COUNT(*) FROM messages") == 0


async def test_selected_chat_is_stored(service):
    add_chat(service, ai=True)
    await service.on_message(message())
    assert service.db.scalar("SELECT COUNT(*) FROM messages") == 1


async def test_edit_updates_stored_text(service):
    add_chat(service, ai=True)
    await service.on_message(message(text="старое"))
    await service.on_edited(100, 1, {"@type": "messageText", "text": {"text": "новое"}})
    assert service.db.scalar("SELECT text FROM messages") == "новое"


async def test_delete_removes_stored_message(service):
    add_chat(service, ai=True)
    await service.on_message(message())
    await service.on_deleted(100, [1])
    assert service.db.scalar("SELECT COUNT(*) FROM messages") == 0
