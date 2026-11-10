"""The browser client: chat list, history, sending, reading, files and the guards on the control port."""
import asyncio
import base64

import httpx
import pytest

from foxygram import web_model as model
from foxygram.admin import create_admin
from foxygram.events import EventHub
from foxygram.telegram.store import TdStore
from foxygram.telegram.tdjson import TdError

from .conftest import add_chat

ME = 1
ALICE = 7
GROUP = -1001
PRIVATE = 7
FOLDER = 3
CSRF = {"x-foxygram": "1"}


def position(order, key="main", pinned=False):
    chat_list = {"main": {"@type": "chatListMain"}, "archive": {"@type": "chatListArchive"}}.get(
        key, {"@type": "chatListFolder", "chat_folder_id": FOLDER})
    return {"@type": "chatPosition", "list": chat_list, "order": str(order), "is_pinned": pinned}


def text_message(message_id, chat_id, text, sender=ALICE, outgoing=False, date=1_700_000_000, **extra):
    return {
        "@type": "message", "id": message_id, "chat_id": chat_id, "date": date, "is_outgoing": outgoing,
        "sender_id": {"@type": "messageSenderUser", "user_id": sender},
        "content": {"@type": "messageText", "text": {"@type": "formattedText", "text": text, "entities": []}},
        **extra,
    }


class Telegram:
    """Answers the TDLib calls the browser routes make, and records them."""

    def __init__(self, tdlib_dir):
        self.calls = []
        self.history = []
        self.extra = {}
        self.file_path = None
        self.tdlib_dir = tdlib_dir
        self.topics = []

    async def call(self, query, timeout=60.0):
        self.calls.append(query)
        match query["@type"]:
            case "getChatHistory":
                return {"@type": "messages", "messages": self.history}
            case "getMessages":
                return {"@type": "messages", "messages": [self.extra.get(i) for i in query["message_ids"]]}
            case "sendMessage":
                return text_message(999, query["chat_id"], query["input_message_content"]["text"]["text"],
                                    sender=ME, outgoing=True, sending_state={"@type": "messageSendingStatePending"})
            case "downloadFile":
                if self.file_path is None:
                    raise TdError(400, "file not found")
                return {"@type": "file", "id": query["file_id"],
                        "local": {"path": str(self.file_path), "is_downloading_completed": True}}
            case "getForumTopics":
                return {"@type": "forumTopics", "topics": self.topics, "next_offset_date": 0,
                        "next_offset_message_id": 0, "next_offset_forum_topic_id": 0}
            case "getForumTopic":
                return next(t for t in self.topics if t["info"]["forum_topic_id"] == query["forum_topic_id"])
            case "getForumTopicHistory":
                return {"@type": "messages", "messages": self.history}
            case "searchChats":
                return {"@type": "chats", "chat_ids": [GROUP]}
            case "searchChatsOnServer":
                return {"@type": "chats", "chat_ids": [PRIVATE]}
        return {"@type": "ok"}

    def of(self, kind):
        return [c for c in self.calls if c["@type"] == kind]


async def feed(session, *updates):
    for update in updates:
        await session._on_update(update)


@pytest.fixture
async def telegram(service):
    fake = Telegram(service.config.tdlib_dir)
    service.session.client.call = fake.call
    session = service.session
    session.auth.state = "ready"
    await feed(
        session,
        {"@type": "updateOption", "name": "my_id", "value": {"@type": "optionValueInteger", "value": str(ME)}},
        {"@type": "updateUser", "user": {"id": ME, "first_name": "Я", "last_name": "", "accent_color_id": 1}},
        {"@type": "updateUser", "user": {"id": ALICE, "first_name": "Алиса", "last_name": "Петрова", "accent_color_id": 2,
                                          "status": {"@type": "userStatusOffline", "was_online": 1_700_000_000}}},
        {"@type": "updateSupergroup", "supergroup": {"id": 1001, "member_count": 5, "is_channel": False}},
        {"@type": "updateScopeNotificationSettings", "scope": {"@type": "notificationSettingsScopeGroupChats"},
         "notification_settings": {"mute_for": 100}},
        {"@type": "updateChatFolders", "chat_folders": [{"id": FOLDER, "name": {"text": {"text": "Работа"}}}]},
        {"@type": "updateNewChat", "chat": {
            "id": GROUP, "title": "Логистика", "type": {"@type": "chatTypeSupergroup", "supergroup_id": 1001, "is_channel": False},
            "positions": [], "unread_count": 3, "notification_settings": {"use_default_mute_for": True},
            "accent_color_id": 4, "last_read_inbox_message_id": 10}},
        {"@type": "updateNewChat", "chat": {
            "id": PRIVATE, "title": "Алиса Петрова", "type": {"@type": "chatTypePrivate", "user_id": ALICE},
            "positions": [], "unread_count": 0, "notification_settings": {"use_default_mute_for": False, "mute_for": 0},
            "last_read_outbox_message_id": 50}},
        {"@type": "updateChatLastMessage", "chat_id": GROUP, "positions": [position(100), position(5, "folder")],
         "last_message": {**text_message(20, GROUP, ""), "content": {
             "@type": "messagePhoto", "photo": {"sizes": []}, "caption": {"text": "накладная"}}}},
        {"@type": "updateChatLastMessage", "chat_id": PRIVATE, "positions": [position(200, pinned=True)],
         "last_message": text_message(50, PRIVATE, "привет", sender=ME, outgoing=True)},
        {"@type": "updateUnreadChatCount", "chat_list": {"@type": "chatListMain"}, "unread_unmuted_count": 4},
    )
    add_chat(service, chat_id=GROUP, title="Логистика")
    service.db.execute("UPDATE chats SET needs_reply = 1, urgency = 'high' WHERE chat_id = ?", (GROUP,))
    return fake


@pytest.fixture
async def web(service):
    port = service.config.server.admin_port
    transport = httpx.ASGITransport(app=create_admin(service))
    async with httpx.AsyncClient(transport=transport, base_url=f"http://127.0.0.1:{port}") as client:
        yield client


# --- the store behind the chat list ---

def test_store_orders_by_position_and_drops_a_chat_leaving_a_list():
    store = TdStore()
    for chat_id, order in ((1, 10), (2, 30), (3, 20)):
        store.apply({"@type": "updateNewChat", "chat": {"id": chat_id, "title": str(chat_id), "positions": [position(order)]}})
    assert [c["id"] for c in store.ordered("main")] == [2, 3, 1]
    store.apply({"@type": "updateChatPosition", "chat_id": 2, "position": position(0)})
    store.apply({"@type": "updateChatPosition", "chat_id": 1, "position": position(5, "archive")})
    assert [c["id"] for c in store.ordered("main")] == [3, 1]
    assert [c["id"] for c in store.ordered("archive")] == [1]
    assert store.has_archive()


def test_mute_follows_the_scope_unless_the_chat_overrides_it():
    store = TdStore()
    store.apply({"@type": "updateScopeNotificationSettings", "scope": {"@type": "notificationSettingsScopePrivateChats"},
                 "notification_settings": {"mute_for": 60}})
    chat = {"id": 1, "type": {"@type": "chatTypePrivate"}, "notification_settings": {"use_default_mute_for": True}}
    assert store.is_muted(chat)
    chat["notification_settings"] = {"use_default_mute_for": False, "mute_for": 0}
    assert not store.is_muted(chat)


# --- what the browser gets ---

async def test_chat_list_reads_like_the_phone(web, telegram):
    body = (await web.get("/app/api/chats")).json()
    first, second = body["chats"]
    assert first["title"] == "Алиса Петрова"
    assert first["pinned"] and first["sender"] == "Вы" and first["preview"] == "привет"
    assert first["status"] == "read"
    assert second["title"] == "Логистика"
    assert second["preview"] == "Фото, накладная" and second["preview_label"] is True
    assert second["sender"] == "Алиса" and second["unread"] == 3 and second["muted"] is True
    assert second["label"]["needs_reply"] is True and second["label"]["urgent"] is True
    assert [f["title"] for f in body["folders"]] == ["Все", "Работа"]
    assert body["folders"][0]["unread"] == 4


async def test_folder_list_shows_only_its_chats(web, telegram):
    body = (await web.get("/app/api/chats", params={"list": f"folder{FOLDER}"})).json()
    assert [c["id"] for c in body["chats"]] == [GROUP]
    assert (await web.get("/app/api/chats", params={"list": "../etc"})).status_code == 400


async def test_header_shows_members_and_last_seen(web, telegram):
    group = (await web.get(f"/app/api/chats/{GROUP}")).json()
    assert group["subtitle"]["text"] == "5 участников"
    assert group["last_read_inbox"] == 10
    private = (await web.get(f"/app/api/chats/{PRIVATE}")).json()
    assert private["subtitle"] == {"text": "был(а)", "seen": 1_700_000_000}


async def test_history_brings_the_messages_replies_point_to(web, telegram):
    telegram.history = [
        text_message(12, GROUP, "ответ", reply_to={"@type": "messageReplyToMessage", "chat_id": GROUP, "message_id": 5}),
        text_message(11, GROUP, "**ok**", sender=ME, outgoing=True),
    ]
    telegram.extra[5] = text_message(5, GROUP, "исходное сообщение")
    messages = (await web.get(f"/app/api/chats/{GROUP}/messages", params={"limit": 2})).json()["messages"]
    assert [m["id"] for m in messages] == [12, 11]
    assert messages[0]["reply"] == {"id": 5, "sender": "Алиса Петрова", "text": "исходное сообщение", "color": 2, "thumb": None}
    assert messages[0]["sender"]["name"] == "Алиса Петрова"
    assert messages[1]["out"] is True and messages[1]["state"] == "sent"
    assert telegram.of("getMessages")[0]["message_ids"] == [5]


async def test_sending_needs_text_and_passes_the_reply(web, telegram):
    assert (await web.post(f"/app/api/chats/{GROUP}/send", json={"text": "  "}, headers=CSRF)).status_code == 400
    assert (await web.post(f"/app/api/chats/{GROUP}/send", json={"text": "x" * 4097}, headers=CSRF)).status_code == 400
    response = await web.post(f"/app/api/chats/{GROUP}/send", json={"text": " Готово ", "reply_to": 12}, headers=CSRF)
    assert response.json()["message"]["state"] == "sending"
    sent = telegram.of("sendMessage")[0]
    assert sent["input_message_content"]["text"]["text"] == "Готово"
    assert sent["reply_to"] == {"@type": "inputMessageReplyToMessage", "message_id": 12}


async def test_reading_marks_messages_seen(web, telegram):
    await web.post(f"/app/api/chats/{GROUP}/open", headers=CSRF)
    await web.post(f"/app/api/chats/{GROUP}/read", json={"ids": [11, 12, -1]}, headers=CSRF)
    viewed = telegram.of("viewMessages")[0]
    assert viewed["message_ids"] == [11, 12] and viewed["force_read"] is True
    assert telegram.of("openChat")[0]["chat_id"] == GROUP


async def test_chat_actions(web, telegram):
    await web.post(f"/app/api/chats/{GROUP}/settings", json={"pinned": True, "list": f"folder{FOLDER}", "muted": True}, headers=CSRF)
    pin = telegram.of("toggleChatIsPinned")[0]
    assert pin["chat_list"] == {"@type": "chatListFolder", "chat_folder_id": FOLDER} and pin["is_pinned"] is True
    mute = telegram.of("setChatNotificationSettings")[0]["notification_settings"]
    assert mute["use_default_mute_for"] is False and mute["mute_for"] > 0
    await web.post(f"/app/api/chats/{GROUP}/settings", json={"archived": True}, headers=CSRF)
    assert telegram.of("addChatToList")[0]["chat_list"] == {"@type": "chatListArchive"}


def forum_topic(topic_id, name, order, pinned=False, unread=0, color=0x6FB9F0):
    return {"@type": "forumTopic", "info": {"forum_topic_id": topic_id, "name": name, "icon": {"color": color}},
            "order": str(order), "is_pinned": pinned, "unread_count": unread, "unread_mention_count": 0,
            "last_read_inbox_message_id": 40, "last_message": text_message(50 + topic_id, GROUP, f"в теме {name}")}


async def test_a_group_with_topics_says_so_and_lists_them_like_the_phone(web, telegram, service):
    await feed(service.session, {"@type": "updateSupergroup", "supergroup": {"id": 1001, "member_count": 5, "is_forum": True}})
    chats = (await web.get("/app/api/chats")).json()["chats"]
    assert next(c for c in chats if c["id"] == GROUP)["forum"] is True
    telegram.topics = [forum_topic(1, "General", 10), forum_topic(7, "Склад", 30, unread=2), forum_topic(9, "Таможня", 5, pinned=True)]
    topics = (await web.get(f"/app/api/chats/{GROUP}/topics")).json()["topics"]
    assert [t["title"] for t in topics] == ["Таможня", "Склад", "General"]
    assert topics[1] | {"date": 0} == {"id": 7, "title": "Склад", "preview": "в теме Склад", "date": 0, "unread": 2, "mentions": 0,
                                      "color": "#6fb9f0", "pinned": False, "closed": False, "last_read_inbox": 40}
    one = (await web.get(f"/app/api/chats/{GROUP}/topics/7")).json()["topic"]
    assert one["title"] == "Склад"


async def test_a_topic_reads_sends_and_marks_read_inside_that_topic(web, telegram):
    telegram.history = [text_message(60, GROUP, "в теме", topic_id={"@type": "messageTopicForum", "forum_topic_id": 7})]
    messages = (await web.get(f"/app/api/chats/{GROUP}/messages", params={"topic": 7})).json()["messages"]
    assert messages[0]["topic"] == 7
    history = telegram.of("getForumTopicHistory")[0]
    assert history["forum_topic_id"] == 7 and telegram.of("getChatHistory") == []

    await web.post(f"/app/api/chats/{GROUP}/send", json={"text": "привет", "topic": 7}, headers=CSRF)
    assert telegram.of("sendMessage")[0]["topic_id"] == {"@type": "messageTopicForum", "forum_topic_id": 7}

    await web.post(f"/app/api/chats/{GROUP}/read", json={"ids": [60], "topic": 7}, headers=CSRF)
    assert telegram.of("viewMessages")[0]["source"] == {"@type": "messageSourceForumTopicHistory"}


async def test_sending_outside_a_topic_names_none(web, telegram):
    await web.post(f"/app/api/chats/{GROUP}/send", json={"text": "привет"}, headers=CSRF)
    assert "topic_id" not in telegram.of("sendMessage")[0]


async def test_topic_changes_reach_the_browser(service):
    seen = []
    service.session.on_event = seen.append
    await feed(service.session,
               {"@type": "updateForumTopicInfo", "info": {"chat_id": GROUP, "forum_topic_id": 7, "name": "Склад 2"}},
               {"@type": "updateForumTopic", "chat_id": GROUP, "forum_topic_id": 7, "last_read_inbox_message_id": 60})
    assert seen == [{"t": "topics", "chat_id": GROUP}, {"t": "topics", "chat_id": GROUP}]


async def test_search_merges_local_and_server_results(web, telegram):
    found = (await web.get("/app/api/search", params={"q": "ло"})).json()["chats"]
    assert [c["id"] for c in found] == [GROUP, PRIVATE]


async def test_files_come_only_from_the_telegram_folder(web, telegram, service, tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("no")
    telegram.file_path = outside
    assert (await web.get("/app/api/files/1")).status_code == 404

    photos = service.config.tdlib_dir / "photos"
    photos.mkdir(parents=True, exist_ok=True)
    photo = photos / "file_1.jpg"
    photo.write_bytes(b"\xff\xd8jpeg")
    telegram.file_path = photo
    response = await web.get("/app/api/files/1")
    assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
    assert "attachment" not in response.headers.get("content-disposition", "")

    page = photos / "file_2.svg"
    page.write_text("<svg onload='alert(1)'/>")
    telegram.file_path = page
    response = await web.get("/app/api/files/2", params={"name": "x.svg"})
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment")


async def test_nothing_works_before_telegram_signs_in(web, telegram, service):
    service.session.auth.state = "need_login"
    assert (await web.get(f"/app/api/chats/{GROUP}/messages")).status_code == 503
    assert (await web.get("/app/api/state")).json()["telegram"] == "need_login"


# --- guards ---

async def test_page_is_served_with_a_strict_policy(web):
    response = await web.get("/app")
    assert response.status_code == 200
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "<title>FoxyGram</title>" in response.text


async def test_writes_need_the_control_page_header(web, telegram):
    assert (await web.post(f"/app/api/chats/{GROUP}/send", json={"text": "x"})).status_code == 403
    assert telegram.of("sendMessage") == []


async def test_other_sites_cannot_read_or_post(web, telegram):
    cross = {"sec-fetch-site": "cross-site"}
    assert (await web.get("/app/api/chats", headers=cross)).status_code == 403
    assert (await web.get("/v1/cases", headers=cross)).status_code == 403
    evil = {**CSRF, "origin": "http://evil.example"}
    assert (await web.post(f"/app/api/chats/{GROUP}/read", json={"ids": [1]}, headers=evil)).status_code == 403


async def test_a_foreign_host_name_is_refused(service):
    transport = httpx.ASGITransport(app=create_admin(service))
    async with httpx.AsyncClient(transport=transport, base_url="http://foxygram.example") as client:
        assert (await client.get("/app/api/chats")).status_code == 403


async def test_phone_routes_work_here_without_the_token(web, telegram):
    assert (await web.get("/v1/cases")).status_code == 200
    assert (await web.get("/v1/flags")).status_code == 200


async def test_the_event_stream_ends_when_the_server_stops(web, service):
    service.stop.set()
    response = await web.get("/app/api/events")
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.startswith("retry:")


# --- live updates ---

async def test_hub_merges_bursts_but_keeps_every_send():
    hub = EventHub(delay=0.01)
    queue = hub.subscribe()
    for _ in range(5):
        hub.publish({"t": "chats"})
    hub.publish({"t": "sent", "chat_id": 1, "old_id": 1, "new_id": 2})
    hub.publish({"t": "sent", "chat_id": 1, "old_id": 3, "new_id": 4})
    await asyncio.sleep(0.05)
    events = [queue.get_nowait() for _ in range(queue.qsize())]
    assert [e["t"] for e in events] == ["chats", "sent", "sent"]


async def test_session_tells_the_browser_what_changed(service):
    seen = []
    service.session.on_event = seen.append
    await feed(service.session,
               {"@type": "updateNewChat", "chat": {"id": 5, "title": "t", "positions": []}},
               {"@type": "updateNewMessage", "message": text_message(1, 5, "hi")},
               {"@type": "updateMessageSendSucceeded", "old_message_id": 1, "message": text_message(2, 5, "hi")},
               {"@type": "updateDeleteMessages", "chat_id": 5, "message_ids": [2], "is_permanent": True, "from_cache": False})
    assert {"t": "chats"} in seen
    assert {"t": "messages", "chat_id": 5} in seen
    assert {"t": "sent", "chat_id": 5, "old_id": 1, "new_id": 2} in seen
    assert {"t": "deleted", "chat_id": 5, "ids": [2]} in seen


# --- message mapping ---

def test_voice_waveform_unpacks_five_bit_samples():
    packed = base64.b64encode(bytes([0b11111_000 >> 3 | 0b000_00000, 0])).decode()
    assert model.waveform(packed)[:2] == [31, 0]


def test_entities_keep_utf16_offsets_and_kinds():
    rich = model.rich_text({"text": "🙂 ссылка", "entities": [
        {"offset": 3, "length": 6, "type": {"@type": "textEntityTypeTextUrl", "url": "https://t.me"}}]})
    assert rich["spans"] == [[3, 6, "text_url", "https://t.me"]]


def test_service_lines_and_member_counts():
    store = TdStore()
    message = {"id": 1, "sender_id": {"@type": "messageSenderUser", "user_id": 9},
               "content": {"@type": "messageChatChangeTitle", "title": "Новое"}}
    store.users[9] = {"first_name": "Олег", "last_name": ""}
    assert model.body(store, message) == {"type": "service", "text": "Олег изменил(а) название на «Новое»"}
    assert model.members(21, False) == "21 участник"
    assert model.members(3, True) == "3 подписчика"
