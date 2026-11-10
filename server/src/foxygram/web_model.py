"""Turns TDLib objects into the small shapes the browser client draws. Mirrors the phone's td/TdMapper.kt."""
from __future__ import annotations

import base64
from typing import Any

from .telegram.store import TdStore, folder_title

MAX_PHOTO_SIDE = 1280
WAVEFORM_BITS = 5
SAVED_TITLE = "Избранное"
DELETED_ACCOUNT = "Удалённый аккаунт"
SKIPPED_THUMBNAILS = {"thumbnailFormatMpeg4", "thumbnailFormatTgs", "thumbnailFormatWebm"}

Json = dict[str, Any]


def _text(formatted: Any) -> str:
    return formatted.get("text", "") if isinstance(formatted, dict) else ""


def kind_of(store: TdStore, chat: Json) -> str:
    chat_type = chat.get("type") or {}
    match chat_type.get("@type"):
        case "chatTypePrivate":
            return "saved" if store.my_id and chat_type.get("user_id") == store.my_id else "private"
        case "chatTypeBasicGroup":
            return "group"
        case "chatTypeSupergroup":
            return "channel" if chat_type.get("is_channel") else "group"
        case _:
            return "private"


def file_id(file: Any) -> int:
    return int(file.get("id", 0)) if isinstance(file, dict) else 0


def image(file: Any, mini: Any = None, width: int = 0, height: int = 0) -> Json | None:
    data = mini.get("data") if isinstance(mini, dict) else None
    if not file_id(file) and not data:
        return None
    return {"file": file_id(file), "mini": data or None, "w": width, "h": height}


def chat_photo(photo: Any) -> Json | None:
    if not isinstance(photo, dict):
        return None
    return image(photo.get("small"), photo.get("minithumbnail"))


def user_name(store: TdStore, user_id: int) -> str:
    user = store.users.get(user_id)
    if user is None:
        return ""
    name = " ".join(p for p in (user.get("first_name", ""), user.get("last_name", "")) if p.strip())
    return name or DELETED_ACCOUNT


def sender_name(store: TdStore, sender: Any) -> str:
    sender = sender or {}
    if sender.get("@type") == "messageSenderUser":
        return user_name(store, sender.get("user_id", 0))
    if sender.get("@type") == "messageSenderChat":
        return (store.chats.get(sender.get("chat_id", 0)) or {}).get("title", "")
    return ""


def _short_sender_name(store: TdStore, sender: Any) -> str | None:
    sender = sender or {}
    if sender.get("@type") == "messageSenderUser":
        return (store.users.get(sender.get("user_id", 0)) or {}).get("first_name") or None
    if sender.get("@type") == "messageSenderChat":
        return (store.chats.get(sender.get("chat_id", 0)) or {}).get("title") or None
    return None


def sender(store: TdStore, source: Any) -> Json | None:
    source = source or {}
    if source.get("@type") == "messageSenderUser":
        user = store.users.get(source.get("user_id", 0)) or {}
        photo = user.get("profile_photo") or {}
        return {
            "id": source.get("user_id", 0),
            "name": user_name(store, source.get("user_id", 0)),
            "photo": image(photo.get("small"), photo.get("minithumbnail")) if photo else None,
            "color": user.get("accent_color_id", 0),
        }
    if source.get("@type") == "messageSenderChat":
        chat = store.chats.get(source.get("chat_id", 0)) or {}
        return {
            "id": source.get("chat_id", 0),
            "name": chat.get("title", ""),
            "photo": chat_photo(chat.get("photo")),
            "color": chat.get("accent_color_id", 0),
        }
    return None


SERVICE_TEXT = {
    "messagePinMessage": "{who} закрепил(а) сообщение",
    "messageChatChangePhoto": "{who} обновил(а) фото группы",
    "messageChatDeletePhoto": "{who} удалил(а) фото группы",
    "messageChatAddMembers": "{who} добавил(а) участников",
    "messageChatJoinByLink": "{who} присоединился(ась)",
    "messageChatJoinByRequest": "{who} присоединился(ась)",
    "messageChatDeleteMember": "{who} покинул(а) группу",
    "messageBasicGroupChatCreate": "Группа создана",
    "messageSupergroupChatCreate": "Группа создана",
    "messageChatUpgradeFrom": "Группа преобразована",
    "messageChatUpgradeTo": "Группа преобразована",
    "messageScreenshotTaken": "{who} сделал(а) скриншот",
    "messageContactRegistered": "{who} теперь в Telegram",
    "messageVideoChatStarted": "Видеочат начат",
    "messageVideoChatEnded": "Видеочат завершён",
    "messageExpiredPhoto": "Фото истекло",
    "messageExpiredVideo": "Видео истекло",
    "messageExpiredVideoNote": "Видеосообщение истекло",
    "messageExpiredVoiceNote": "Голосовое сообщение истекло",
}

NOT_SERVICE = {
    "messageText", "messageAnimatedEmoji", "messagePhoto", "messageVideo", "messageAnimation", "messageAudio",
    "messageDocument", "messageVoiceNote", "messageVideoNote", "messageSticker", "messagePoll", "messageLocation",
    "messageVenue", "messageContact", "messageCall", "messageUnsupported",
}


def is_service(content: Json) -> bool:
    return content.get("@type", "") not in NOT_SERVICE


def service_text(content: Json, who: str | None) -> str:
    who = who or "Участник"
    tag = content.get("@type", "")
    if tag == "messageChatChangeTitle":
        return f"{who} изменил(а) название на «{content.get('title', '')}»"
    if tag == "messageForumTopicCreated":
        return f"Создана тема «{content.get('name', '')}»"
    if tag == "messageCustomServiceAction":
        return content.get("text", "")
    template = SERVICE_TEXT.get(tag)
    return template.format(who=who) if template else "Служебное сообщение"


def preview_of(content: Json) -> tuple[str, bool]:
    """Short text for the chat list, and whether it is a label like «Фото» rather than what someone wrote."""
    def labelled(label: str, caption: Any) -> tuple[str, bool]:
        text = _text(caption).replace("\n", " ")
        return (f"{label}, {text}" if text.strip() else label), True

    tag = content.get("@type", "")
    match tag:
        case "messageText":
            return _text(content.get("text")).replace("\n", " "), False
        case "messageAnimatedEmoji":
            return content.get("emoji", ""), False
        case "messagePhoto":
            return labelled("Фото", content.get("caption"))
        case "messageVideo":
            return labelled("Видео", content.get("caption"))
        case "messageAnimation":
            return labelled("GIF", content.get("caption"))
        case "messageAudio":
            return labelled("Аудио", content.get("caption"))
        case "messageDocument":
            return ((content.get("document") or {}).get("file_name") or "Файл"), True
        case "messageVoiceNote":
            return labelled("Голосовое сообщение", content.get("caption"))
        case "messageVideoNote":
            return "Видеосообщение", True
        case "messageSticker":
            return f"{(content.get('sticker') or {}).get('emoji', '')} Стикер".strip(), True
        case "messagePoll":
            return f"Опрос: {_text((content.get('poll') or {}).get('question'))}", True
        case "messageLocation" | "messageVenue":
            return "Геопозиция", True
        case "messageContact":
            return "Контакт", True
        case "messageCall":
            missed = (content.get("discard_reason") or {}).get("@type") == "callDiscardReasonMissed"
            return ("Пропущенный звонок" if missed else "Звонок"), True
        case _:
            return service_text(content, None), True


def _preview_thumb(content: Json) -> Json | None:
    if content.get("@type") == "messagePhoto":
        photo = content.get("photo") or {}
        sizes = photo.get("sizes") or []
        if sizes:
            return image(sizes[0].get("photo"), photo.get("minithumbnail"))
    if content.get("@type") == "messageVideo":
        video = content.get("video") or {}
        thumb = video.get("thumbnail") or {}
        if thumb:
            return image(thumb.get("file"), video.get("minithumbnail"))
    return None


def send_state(message: Json, chat: Json | None) -> str:
    if not message.get("is_outgoing"):
        return "none"
    sending = (message.get("sending_state") or {}).get("@type")
    if sending == "messageSendingStatePending":
        return "sending"
    if sending == "messageSendingStateFailed":
        return "failed"
    if chat is not None and message.get("id", 0) <= chat.get("last_read_outbox_message_id", 0):
        return "read"
    return "sent"


def verified(store: TdStore, chat: Json) -> bool:
    chat_type = chat.get("type") or {}
    if chat_type.get("@type") == "chatTypePrivate":
        owner = store.users.get(chat_type.get("user_id", 0)) or {}
    elif chat_type.get("@type") == "chatTypeSupergroup":
        owner = store.supergroups.get(chat_type.get("supergroup_id", 0)) or {}
    else:
        return False
    return bool((owner.get("verification_status") or {}).get("is_verified"))


def is_forum(store: TdStore, chat: Json) -> bool:
    chat_type = chat.get("type") or {}
    if chat_type.get("@type") != "chatTypeSupergroup":
        return False
    return bool((store.supergroups.get(chat_type.get("supergroup_id", 0)) or {}).get("is_forum"))


def chat_item(store: TdStore, chat: Json, key: str = "main", label: Json | None = None) -> Json:
    kind = kind_of(store, chat)
    last = chat.get("last_message") or None
    position = store.position(chat, key) or {}
    draft_content = (chat.get("draft_message") or {}).get("content") or {}
    draft = _text(draft_content.get("text")).strip() or None
    preview, is_label = preview_of(last["content"]) if last else ("", False)
    prefix = None
    if last and kind not in ("channel", "saved") and not is_service(last.get("content") or {}):
        if last.get("is_outgoing"):
            prefix = "Вы"
        elif kind == "group":
            prefix = _short_sender_name(store, last.get("sender_id"))
    unread = chat.get("unread_count", 0) or (1 if chat.get("is_marked_as_unread") else 0)
    return {
        "id": chat["id"],
        "title": SAVED_TITLE if kind == "saved" else (chat.get("title") or DELETED_ACCOUNT),
        "kind": kind,
        "photo": chat_photo(chat.get("photo")),
        "color": chat.get("accent_color_id", 0),
        "sender": prefix,
        "preview": preview,
        "preview_label": is_label,
        "thumb": _preview_thumb(last.get("content") or {}) if last else None,
        "date": (last or {}).get("date", 0),
        "unread": unread,
        "mentions": chat.get("unread_mention_count", 0),
        "reactions": chat.get("unread_reaction_count", 0),
        "muted": store.is_muted(chat),
        "pinned": bool(position.get("is_pinned")),
        "archived": store.position(chat, "archive") is not None,
        "status": send_state(last, chat) if last else "none",
        "draft": draft,
        "verified": verified(store, chat),
        "forum": is_forum(store, chat),
        "label": label,
    }


def subtitle(store: TdStore, chat: Json) -> Json:
    """The line under the name in a chat's header. 'seen' is a last-seen time the browser formats itself."""
    chat_type = chat.get("type") or {}
    tag = chat_type.get("@type")
    if tag in ("chatTypePrivate", "chatTypeSecret"):
        if kind_of(store, chat) == "saved":
            return {"text": "", "seen": 0}
        user = store.users.get(chat_type.get("user_id", 0))
        if user is None:
            return {"text": "", "seen": 0}
        if (user.get("type") or {}).get("@type") == "userTypeBot":
            return {"text": "бот", "seen": 0}
        status = user.get("status") or {}
        match status.get("@type"):
            case "userStatusOnline":
                return {"text": "в сети", "seen": 0}
            case "userStatusOffline":
                return {"text": "был(а)", "seen": status.get("was_online", 0)}
            case "userStatusRecently":
                return {"text": "был(а) недавно", "seen": 0}
            case "userStatusLastWeek":
                return {"text": "был(а) на этой неделе", "seen": 0}
            case "userStatusLastMonth":
                return {"text": "был(а) в этом месяце", "seen": 0}
            case _:
                return {"text": "был(а) давно", "seen": 0}
    if tag == "chatTypeBasicGroup":
        count = (store.basic_groups.get(chat_type.get("basic_group_id", 0)) or {}).get("member_count", 0)
        return {"text": members(count, False), "seen": 0}
    if tag == "chatTypeSupergroup":
        count = (store.supergroups.get(chat_type.get("supergroup_id", 0)) or {}).get("member_count", 0)
        return {"text": members(count, bool(chat_type.get("is_channel"))), "seen": 0}
    return {"text": "", "seen": 0}


def plural_ru(count: int, one: str, few: str, many: str) -> str:
    if 11 <= count % 100 <= 14:
        return many
    if count % 10 == 1:
        return one
    if 2 <= count % 10 <= 4:
        return few
    return many


def members(count: int, channel: bool) -> str:
    if count == 0:
        return "канал" if channel else "группа"
    if channel:
        return f"{count} {plural_ru(count, 'подписчик', 'подписчика', 'подписчиков')}"
    return f"{count} {plural_ru(count, 'участник', 'участника', 'участников')}"


ENTITY_TYPES = {
    "textEntityTypeBold": "bold",
    "textEntityTypeItalic": "italic",
    "textEntityTypeUnderline": "underline",
    "textEntityTypeStrikethrough": "strike",
    "textEntityTypeSpoiler": "spoiler",
    "textEntityTypeCode": "code",
    "textEntityTypePre": "pre",
    "textEntityTypePreCode": "pre",
    "textEntityTypeBlockQuote": "quote",
    "textEntityTypeExpandableBlockQuote": "quote",
    "textEntityTypeUrl": "url",
    "textEntityTypeTextUrl": "text_url",
    "textEntityTypeMention": "mention",
    "textEntityTypeMentionName": "mention",
    "textEntityTypeHashtag": "hashtag",
    "textEntityTypeCashtag": "hashtag",
    "textEntityTypeBotCommand": "command",
    "textEntityTypeEmailAddress": "email",
    "textEntityTypePhoneNumber": "phone",
}


def rich_text(formatted: Any) -> Json:
    """Offsets stay in UTF-16 units, which is also how JavaScript strings count."""
    if not isinstance(formatted, dict):
        return {"text": "", "spans": []}
    spans = []
    for entity in formatted.get("entities") or []:
        entity_type = entity.get("type") or {}
        kind = ENTITY_TYPES.get(entity_type.get("@type", ""))
        if kind:
            spans.append([entity.get("offset", 0), entity.get("length", 0), kind, entity_type.get("url")])
    return {"text": formatted.get("text", ""), "spans": spans}


def _best_size(photo: Json) -> Json | None:
    sizes = photo.get("sizes") or []
    fitting = [s for s in sizes if s.get("width", 0) <= MAX_PHOTO_SIDE and s.get("height", 0) <= MAX_PHOTO_SIDE]
    return (fitting or sizes or [None])[-1]


def photo_image(photo: Json) -> Json | None:
    size = _best_size(photo) or {}
    return image(size.get("photo"), photo.get("minithumbnail"), size.get("width", 0), size.get("height", 0))


def thumb(thumbnail: Any, mini: Any) -> Json | None:
    usable = thumbnail if isinstance(thumbnail, dict) else None
    if usable and (usable.get("format") or {}).get("@type") in SKIPPED_THUMBNAILS:
        usable = None
    if usable is None and not (isinstance(mini, dict) and mini.get("data")):
        return None
    usable = usable or {}
    return image(usable.get("file"), mini, usable.get("width", 0), usable.get("height", 0))


def waveform(data: str | None) -> list[int]:
    if not data:
        return []
    try:
        raw = base64.b64decode(data)
    except ValueError:
        return []
    count = len(raw) * 8 // WAVEFORM_BITS
    values = []
    for index in range(count):
        bit = index * WAVEFORM_BITS
        byte, shift = divmod(bit, 8)
        current = raw[byte]
        following = raw[byte + 1] if byte + 1 < len(raw) else 0
        values.append(((current | (following << 8)) >> shift) & 0x1F)
    return values


def _size(file: Any) -> int:
    if not isinstance(file, dict):
        return 0
    return int(file.get("size") or file.get("expected_size") or 0)


def _web_preview(preview: Any) -> Json | None:
    if not isinstance(preview, dict):
        return None
    preview_type = preview.get("type") or {}
    photo = preview_type.get("photo") if preview_type.get("@type") in ("linkPreviewTypeArticle", "linkPreviewTypePhoto") else None
    return {
        "site": preview.get("site_name", ""),
        "title": preview.get("title", ""),
        "description": _text(preview.get("description")),
        "photo": photo_image(photo) if isinstance(photo, dict) else None,
        "url": preview.get("url", ""),
    }


def body(store: TdStore, message: Json) -> Json:
    content = message.get("content") or {}
    tag = content.get("@type", "")
    caption = rich_text(content.get("caption"))
    match tag:
        case "messageText":
            return {"type": "text", "text": rich_text(content.get("text")), "web": _web_preview(content.get("link_preview"))}
        case "messageAnimatedEmoji":
            return {"type": "text", "text": {"text": content.get("emoji", ""), "spans": []}, "web": None}
        case "messagePhoto":
            return {"type": "photo", "image": photo_image(content.get("photo") or {}), "caption": caption}
        case "messageVideo" | "messageAnimation":
            media = content.get("video") or content.get("animation") or {}
            file = media.get("video") or media.get("animation")
            return {
                "type": "video", "gif": tag == "messageAnimation", "file": file_id(file), "size": _size(file),
                "thumb": thumb(media.get("thumbnail"), media.get("minithumbnail")),
                "w": media.get("width", 0), "h": media.get("height", 0), "duration": media.get("duration", 0),
                "mime": media.get("mime_type", ""), "caption": caption,
            }
        case "messageVoiceNote":
            voice = content.get("voice_note") or {}
            return {"type": "voice", "file": file_id(voice.get("voice")), "duration": voice.get("duration", 0),
                    "waveform": waveform(voice.get("waveform")), "caption": caption}
        case "messageVideoNote":
            note = content.get("video_note") or {}
            return {"type": "round", "file": file_id(note.get("video")), "duration": note.get("duration", 0),
                    "thumb": thumb(note.get("thumbnail"), note.get("minithumbnail"))}
        case "messageAudio":
            audio = content.get("audio") or {}
            return {"type": "audio", "file": file_id(audio.get("audio")), "title": audio.get("title") or audio.get("file_name", ""),
                    "performer": audio.get("performer", ""), "duration": audio.get("duration", 0), "caption": caption}
        case "messageDocument":
            document = content.get("document") or {}
            return {"type": "document", "file": file_id(document.get("document")), "name": document.get("file_name", ""),
                    "size": _size(document.get("document")), "mime": document.get("mime_type", ""),
                    "thumb": thumb(document.get("thumbnail"), document.get("minithumbnail")), "caption": caption}
        case "messageSticker":
            sticker = content.get("sticker") or {}
            sticker_format = {"stickerFormatTgs": "tgs", "stickerFormatWebm": "webm"}.get(
                (sticker.get("format") or {}).get("@type", ""), "webp")
            return {"type": "sticker", "file": file_id(sticker.get("sticker")), "w": sticker.get("width", 0),
                    "h": sticker.get("height", 0), "format": sticker_format, "emoji": sticker.get("emoji", ""),
                    "thumb": thumb(sticker.get("thumbnail"), None)}
        case "messagePoll":
            poll = content.get("poll") or {}
            return {
                "type": "poll", "question": _text(poll.get("question")),
                "options": [{"text": _text(o.get("text")), "percent": o.get("vote_percentage", 0),
                             "votes": o.get("voter_count", 0), "chosen": bool(o.get("is_chosen"))}
                            for o in poll.get("options") or []],
                "total": poll.get("total_voter_count", 0), "closed": bool(poll.get("is_closed")),
                "quiz": (poll.get("type") or {}).get("@type") == "pollTypeQuiz",
            }
        case "messageLocation":
            location = content.get("location") or {}
            return {"type": "location", "lat": location.get("latitude", 0), "lon": location.get("longitude", 0), "title": ""}
        case "messageVenue":
            venue = content.get("venue") or {}
            location = venue.get("location") or {}
            return {"type": "location", "lat": location.get("latitude", 0), "lon": location.get("longitude", 0),
                    "title": venue.get("title", "")}
        case "messageContact":
            contact = content.get("contact") or {}
            name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
            return {"type": "contact", "name": name, "phone": contact.get("phone_number", "")}
        case "messageCall":
            missed = (content.get("discard_reason") or {}).get("@type") == "callDiscardReasonMissed"
            return {"type": "call", "video": bool(content.get("is_video")), "duration": content.get("duration", 0), "missed": missed}
        case "messageUnsupported":
            return {"type": "unsupported"}
        case _:
            return {"type": "service", "text": service_text(content, sender_name(store, message.get("sender_id")))}


def _forward_name(store: TdStore, info: Any) -> str | None:
    origin = (info or {}).get("origin") if isinstance(info, dict) else None
    if not isinstance(origin, dict):
        return None
    match origin.get("@type"):
        case "messageOriginUser":
            return user_name(store, origin.get("sender_user_id", 0))
        case "messageOriginHiddenUser":
            return origin.get("sender_name", "")
        case "messageOriginChat":
            return (store.chats.get(origin.get("sender_chat_id", 0)) or {}).get("title", "")
        case "messageOriginChannel":
            return (store.chats.get(origin.get("chat_id", 0)) or {}).get("title", "")
    return ""


def reply_info(store: TdStore, replied: Json) -> Json:
    source = replied.get("sender_id") or {}
    if source.get("@type") == "messageSenderUser":
        color = (store.users.get(source.get("user_id", 0)) or {}).get("accent_color_id", 0)
    else:
        color = (store.chats.get(source.get("chat_id", 0)) or {}).get("accent_color_id", 0)
    content = replied.get("content") or {}
    return {
        "id": replied.get("id", 0),
        "sender": sender_name(store, source),
        "text": preview_of(content)[0],
        "color": color,
        "thumb": _preview_thumb(content),
    }


def replied_id(message: Json) -> int:
    reply = message.get("reply_to") or {}
    if reply.get("@type") != "messageReplyToMessage":
        return 0
    if reply.get("chat_id") and reply.get("chat_id") != message.get("chat_id"):
        return 0
    return int(reply.get("message_id") or 0)


def message_item(store: TdStore, chat: Json | None, message: Json, replied: Json | None = None) -> Json:
    interaction = message.get("interaction_info") or {}
    reactions = []
    for reaction in (interaction.get("reactions") or {}).get("reactions") or []:
        reaction_type = reaction.get("type") or {}
        if reaction_type.get("@type") == "reactionTypeEmoji":
            reactions.append({"emoji": reaction_type.get("emoji", ""), "count": reaction.get("total_count", 0),
                              "chosen": bool(reaction.get("is_chosen"))})
    channel_post = bool(message.get("is_channel_post"))
    return {
        "id": message["id"],
        "chat_id": message.get("chat_id", 0),
        "date": message.get("date", 0),
        "out": bool(message.get("is_outgoing")) and not channel_post,
        "sender": sender(store, message.get("sender_id")),
        "body": body(store, message),
        "reply": reply_info(store, replied) if replied else None,
        "forward": _forward_name(store, message.get("forward_info")),
        "edited": bool(message.get("edit_date")),
        "state": send_state(message, chat),
        "reactions": reactions,
        "album": str(message.get("media_album_id") or "0"),
        "views": interaction.get("view_count", 0) if channel_post else 0,
        "mention": bool(message.get("contains_unread_mention")),
    }


def folder_tabs(store: TdStore) -> list[Json]:
    tabs = [{"key": "main", "title": "Все", "unread": store.unread_by_list.get("main", 0)}]
    for folder in store.folders:
        key = f"folder{folder['id']}"
        tabs.append({"key": key, "title": folder_title(folder), "unread": store.unread_by_list.get(key, 0)})
    if store.has_archive():
        tabs.append({"key": "archive", "title": "Архив", "unread": store.unread_by_list.get("archive", 0)})
    return tabs


def connection_label(connection: str) -> str | None:
    """What the phone shows in place of the app name while it is not connected."""
    return {
        "WaitingForNetwork": "Ожидание сети…",
        "Connecting": "Соединение…",
        "ConnectingToProxy": "Соединение…",
        "Updating": "Обновление…",
    }.get(connection)
