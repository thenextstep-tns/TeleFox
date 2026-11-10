"""The TDLib objects the browser client shows, kept current from the update stream."""
from __future__ import annotations

from typing import Any

# Updates that change something on the chat list. The browser refetches the list after them.
CHAT_LIST_UPDATES = {
    "updateNewChat",
    "updateChatTitle",
    "updateChatPhoto",
    "updateChatAccentColors",
    "updateChatLastMessage",
    "updateChatPosition",
    "updateChatReadInbox",
    "updateChatReadOutbox",
    "updateChatUnreadMentionCount",
    "updateChatUnreadReactionCount",
    "updateMessageMentionRead",
    "updateChatIsMarkedAsUnread",
    "updateChatNotificationSettings",
    "updateChatDraftMessage",
    "updateScopeNotificationSettings",
    "updateUnreadChatCount",
    "updateChatFolders",
}

SCOPES = {
    "notificationSettingsScopePrivateChats": "private",
    "notificationSettingsScopeGroupChats": "group",
    "notificationSettingsScopeChannelChats": "channel",
}


def list_key(chat_list: dict[str, Any] | None) -> str:
    match (chat_list or {}).get("@type"):
        case "chatListArchive":
            return "archive"
        case "chatListFolder":
            return f"folder{chat_list['chat_folder_id']}"
        case _:
            return "main"


def chat_list(key: str) -> dict[str, Any]:
    if key == "archive":
        return {"@type": "chatListArchive"}
    if key.startswith("folder"):
        return {"@type": "chatListFolder", "chat_folder_id": int(key.removeprefix("folder"))}
    return {"@type": "chatListMain"}


def folder_title(info: dict[str, Any]) -> str:
    """Newer TDLib nests the name as formatted text; older versions had a plain title."""
    name = info.get("name")
    if isinstance(name, dict):
        text = name.get("text")
        return text.get("text", "") if isinstance(text, dict) else str(text or "")
    return str(info.get("title", ""))


def _order(position: dict[str, Any]) -> int:
    return int(position.get("order") or 0)


def _merge_positions(current: list[dict[str, Any]], changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {list_key(p.get("list")): p for p in current}
    for change in changes:
        key = list_key(change.get("list"))
        if _order(change) == 0:
            merged.pop(key, None)
        else:
            merged[key] = change
    return list(merged.values())


class TdStore:
    def __init__(self) -> None:
        self.chats: dict[int, dict[str, Any]] = {}
        self.users: dict[int, dict[str, Any]] = {}
        self.basic_groups: dict[int, dict[str, Any]] = {}
        self.supergroups: dict[int, dict[str, Any]] = {}
        self.folders: list[dict[str, Any]] = []
        self.unread_by_list: dict[str, int] = {}
        self.scope_settings: dict[str, dict[str, Any]] = {}
        self.my_id = 0

    def apply(self, update: dict[str, Any]) -> bool:
        """Applies one update. True when the chat list may look different afterwards."""
        tag = update.get("@type", "")
        chat = self.chats.get(update.get("chat_id", 0)) if "chat_id" in update else None
        match tag:
            case "updateNewChat":
                new = dict(update["chat"])
                new["positions"] = [p for p in new.get("positions") or [] if _order(p)]
                self.chats[new["id"]] = new
            case "updateChatTitle" if chat:
                chat["title"] = update.get("title", "")
            case "updateChatPhoto" if chat:
                chat["photo"] = update.get("photo")
            case "updateChatAccentColors" if chat:
                chat["accent_color_id"] = update.get("accent_color_id", 0)
            case "updateChatLastMessage" if chat:
                chat["last_message"] = update.get("last_message")
                chat["positions"] = _merge_positions(chat.get("positions") or [], update.get("positions") or [])
            case "updateChatPosition" if chat:
                chat["positions"] = _merge_positions(chat.get("positions") or [], [update["position"]])
            case "updateChatReadInbox" if chat:
                chat["last_read_inbox_message_id"] = update.get("last_read_inbox_message_id", 0)
                chat["unread_count"] = update.get("unread_count", 0)
            case "updateChatReadOutbox" if chat:
                chat["last_read_outbox_message_id"] = update.get("last_read_outbox_message_id", 0)
            case "updateChatUnreadMentionCount" | "updateMessageMentionRead" if chat:
                chat["unread_mention_count"] = update.get("unread_mention_count", 0)
            case "updateChatUnreadReactionCount" if chat:
                chat["unread_reaction_count"] = update.get("unread_reaction_count", 0)
            case "updateChatIsMarkedAsUnread" if chat:
                chat["is_marked_as_unread"] = update.get("is_marked_as_unread", False)
            case "updateChatNotificationSettings" if chat:
                chat["notification_settings"] = update.get("notification_settings") or {}
            case "updateChatDraftMessage" if chat:
                chat["draft_message"] = update.get("draft_message")
                chat["positions"] = _merge_positions(chat.get("positions") or [], update.get("positions") or [])
            case "updateScopeNotificationSettings":
                scope = SCOPES.get(update.get("scope", {}).get("@type", ""))
                if scope:
                    self.scope_settings[scope] = update.get("notification_settings") or {}
            case "updateUnreadChatCount":
                self.unread_by_list[list_key(update.get("chat_list"))] = int(update.get("unread_unmuted_count", 0))
            case "updateChatFolders":
                self.folders = list(update.get("chat_folders") or [])
            case "updateUser":
                self.users[update["user"]["id"]] = update["user"]
            case "updateUserStatus":
                user = self.users.get(update.get("user_id", 0))
                if user:
                    user["status"] = update.get("status")
            case "updateBasicGroup":
                self.basic_groups[update["basic_group"]["id"]] = update["basic_group"]
            case "updateSupergroup":
                self.supergroups[update["supergroup"]["id"]] = update["supergroup"]
            case "updateOption" if update.get("name") == "my_id":
                self.my_id = int((update.get("value") or {}).get("value", 0))
            case _:
                return False
        return tag in CHAT_LIST_UPDATES

    def position(self, chat: dict[str, Any], key: str) -> dict[str, Any] | None:
        for position in chat.get("positions") or []:
            if list_key(position.get("list")) == key and _order(position):
                return position
        return None

    def ordered(self, key: str) -> list[dict[str, Any]]:
        placed = [(chat, self.position(chat, key)) for chat in self.chats.values()]
        placed = [(chat, position) for chat, position in placed if position]
        placed.sort(key=lambda pair: _order(pair[1]), reverse=True)
        return [chat for chat, _ in placed]

    def has_archive(self) -> bool:
        return any(self.position(chat, "archive") for chat in self.chats.values())

    def scope_of(self, chat: dict[str, Any]) -> str:
        chat_type = chat.get("type") or {}
        match chat_type.get("@type"):
            case "chatTypeBasicGroup":
                return "group"
            case "chatTypeSupergroup":
                return "channel" if chat_type.get("is_channel") else "group"
            case _:
                return "private"

    def is_muted(self, chat: dict[str, Any]) -> bool:
        settings = chat.get("notification_settings") or {}
        if settings.get("use_default_mute_for", True):
            return int((self.scope_settings.get(self.scope_of(chat)) or {}).get("mute_for", 0)) > 0
        return int(settings.get("mute_for", 0)) > 0
