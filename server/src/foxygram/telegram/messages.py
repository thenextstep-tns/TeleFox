"""Turns TDLib message objects into the small shape the rest of the server uses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

NO_MESSAGE_KINDS = {
    # Things that are not worth a notification or an AI call.
    "messagePinMessage",
    "messageChatChangeTitle",
    "messageChatChangePhoto",
    "messageChatDeletePhoto",
    "messageChatSetMessageAutoDeleteTime",
    "messageChatSetBackground",
    "messageChatSetTheme",
    "messageScreenshotTaken",
    "messageContactRegistered",
    "messageForumTopicEdited",
    "messageForumTopicIsClosedToggled",
    "messageForumTopicIsHiddenToggled",
    "messageForumTopicCreated",
    "messageChatUpgradeTo",
    "messageChatUpgradeFrom",
    "messageBasicGroupChatCreate",
    "messageSupergroupChatCreate",
}


@dataclass(frozen=True)
class Parsed:
    chat_id: int
    message_id: int
    date: int
    sender_id: int
    outgoing: bool
    kind: str
    text: str
    reply_to: int
    pending: bool


def formatted(value: Any) -> str:
    return value.get("text", "") if isinstance(value, dict) else ""


def content_of(content: dict[str, Any]) -> tuple[str, str]:
    """Return (kind, text). Text is the caption for media, so Claude sees what people wrote."""
    tag = content.get("@type", "")
    match tag:
        case "messageText":
            return "text", formatted(content.get("text"))
        case "messagePhoto":
            return "photo", formatted(content.get("caption"))
        case "messageVideo":
            return "video", formatted(content.get("caption"))
        case "messageAnimation":
            return "gif", formatted(content.get("caption"))
        case "messageAudio":
            audio = content.get("audio", {})
            name = " - ".join(p for p in (audio.get("performer"), audio.get("title")) if p)
            return "audio", formatted(content.get("caption")) or name
        case "messageDocument":
            name = content.get("document", {}).get("file_name", "")
            caption = formatted(content.get("caption"))
            return "document", f"{name} {caption}".strip()
        case "messageVoiceNote":
            return "voice", formatted(content.get("caption"))
        case "messageVideoNote":
            return "round_video", ""
        case "messageSticker":
            return "sticker", content.get("sticker", {}).get("emoji", "")
        case "messageAnimatedEmoji":
            return "text", content.get("emoji", "")
        case "messagePoll":
            return "poll", formatted(content.get("poll", {}).get("question"))
        case "messageLocation" | "messageVenue":
            return "location", ""
        case "messageContact":
            contact = content.get("contact", {})
            name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
            return "contact", f"{name} {contact.get('phone_number', '')}".strip()
        case "messageCall":
            return "call", ""
    if tag in NO_MESSAGE_KINDS:
        return "service", ""
    return "other", ""


def parse(message: dict[str, Any]) -> Parsed:
    sender = message.get("sender_id", {})
    sender_id = int(sender.get("user_id") or sender.get("chat_id") or 0)
    reply = message.get("reply_to") or {}
    kind, text = content_of(message.get("content", {}))
    return Parsed(
        chat_id=int(message["chat_id"]),
        message_id=int(message["id"]),
        date=int(message.get("date", 0)),
        sender_id=sender_id,
        outgoing=bool(message.get("is_outgoing")),
        kind=kind,
        text=text,
        reply_to=int(reply.get("message_id", 0)) if reply.get("@type") == "messageReplyToMessage" else 0,
        pending="sending_state" in message and message["sending_state"] is not None,
    )


def chat_kind(chat_type: dict[str, Any]) -> str:
    match chat_type.get("@type"):
        case "chatTypeBasicGroup":
            return "group"
        case "chatTypeSupergroup":
            return "channel" if chat_type.get("is_channel") else "group"
    return "private"
