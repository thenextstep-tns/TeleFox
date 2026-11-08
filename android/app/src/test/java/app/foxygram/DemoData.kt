package app.foxygram

import app.foxygram.model.ChatItem
import app.foxygram.model.ChatKind
import app.foxygram.model.ChatLabel
import app.foxygram.model.FolderTab
import app.foxygram.model.ImageRef
import app.foxygram.model.MessageBody
import app.foxygram.model.MessageItem
import app.foxygram.model.PollOptionItem
import app.foxygram.model.ReactionItem
import app.foxygram.model.ReplyInfo
import app.foxygram.model.RichText
import app.foxygram.model.SendState
import app.foxygram.model.Sender
import app.foxygram.model.SpanType
import app.foxygram.model.StickerFormat
import app.foxygram.model.TextSpan
import app.foxygram.model.WebPreview

object DemoData {
    val now = (System.currentTimeMillis() / 1000).toInt()

    val folders = listOf(FolderTab(0, "Все", 9), FolderTab(1, "Работа", 5), FolderTab(2, "Личные"), FolderTab(3, "Каналы", 3))

    val chats = listOf(
        ChatItem(1, "Избранное", ChatKind.Saved, preview = "договор_финал.pdf", previewIsLabel = true, date = now - 300, pinned = true, status = SendState.Read),
        ChatItem(2, "Логистика / Таллин", ChatKind.Group, colorIndex = 1, senderPrefix = "Андрей", preview = "Контейнер задержали в порту, нужен инвойс и CMR до завтра", date = now - 120, unread = 12, mentions = 1,
            label = ChatLabel(needsReply = true, urgent = true, projectName = "Авто", projectColor = 0xFFA371F7)),
        ChatItem(3, "Дмитрий Орлов", ChatKind.Private, colorIndex = 4, preview = "Скинул VIN и инвойс, посмотрите когда будет время", date = now - 1800, unread = 3,
            label = ChatLabel(needsReply = true, projectName = "Авто", projectColor = 0xFFA371F7)),
        ChatItem(4, "Анна Смирнова", ChatKind.Private, colorIndex = 5, preview = "Спасибо, получила документы", date = now - 3700, status = SendState.Read),
        ChatItem(5, "Таможня новости", ChatKind.Channel, colorIndex = 2, preview = "Новые правила ввоза с 1 ноября", date = now - 7000, unread = 54, muted = true),
        ChatItem(6, "Игорь (брокер)", ChatKind.Private, colorIndex = 3, preview = "Голосовое сообщение", previewIsLabel = true, date = now - 90000),
        ChatItem(7, "Команда", ChatKind.Group, colorIndex = 6, draft = "Завтра созвон в 11", date = now - 200000, muted = true),
        ChatItem(8, "Елена", ChatKind.Private, colorIndex = 7, typing = "печатает…", preview = "", date = now - 400000),
    )

    private val andrey = Sender(10, "Андрей Ким", colorIndex = 1)
    private val olga = Sender(11, "Ольга Юрьева", colorIndex = 4)

    private fun text(id: Long, sender: Sender?, outgoing: Boolean, body: String, ago: Int, state: SendState = SendState.None, reply: ReplyInfo? = null, edited: Boolean = false, spans: List<TextSpan> = emptyList(), reactions: List<ReactionItem> = emptyList(), forward: String? = null) =
        MessageItem(id, 2, now - ago, outgoing, sender, MessageBody.Text(RichText(body, spans)), reply = reply, state = state, edited = edited, reactions = reactions, forwardFrom = forward)

    val messages: List<MessageItem> = listOf(
        MessageItem(20, 2, now - 30, false, olga, MessageBody.Voice(1, 37, List(60) { (it * 7 % 31) }, listened = false)),
        MessageItem(19, 2, now - 60, true, null, MessageBody.Document(2, "CMR_WBA3A5C58DF123456.pdf", 1_840_000, "application/pdf"), state = SendState.Sent),
        text(18, null, true, "Приняли, проверяем. Вернусь с ответом сегодня.", 120, SendState.Read,
            reply = ReplyInfo(16, "Андрей Ким", "Контейнер MSKU1234565 задержали в порту", 1)),
        MessageItem(17, 2, now - 200, false, olga, MessageBody.Poll(1, "Когда удобно созвониться?", listOf(
            PollOptionItem("Сегодня после 15:00", 60, 3, true), PollOptionItem("Завтра утром", 40, 2, false),
        ), 5, false, false, true), reactions = emptyList()),
        text(16, andrey, false, "Контейнер MSKU1234565 задержали в порту, нужен инвойс и CMR до завтра 12:00. Иначе простой 150 евро в день.", 400,
            spans = listOf(TextSpan(10, 11, SpanType.Bold)), reactions = listOf(ReactionItem("👍", 2, true), ReactionItem("🔥", 1, false))),
        text(15, andrey, false, "Коллеги, по BMW есть новости", 430),
        text(14, null, true, "Отлично, жду ссылку", 3000, SendState.Read, edited = true),
        text(13, olga, false, "Трекинг: https://example.com/track/123", 3100, spans = listOf(TextSpan(8, 29, SpanType.Url))),
        MessageItem(12, 2, now - 3200, false, olga, MessageBody.Text(RichText("Вот статья про новые правила"), WebPreview("Таможня.рф", "Изменения с 1 ноября", "Что изменится для ввоза легковых автомобилей и какие документы потребуются.", url = "https://example.com")),
            forwardFrom = "Таможня новости"),
        MessageItem(11, 2, now - 90000, false, andrey, MessageBody.Service("Андрей Ким закрепил сообщение")),
        MessageItem(10, 2, now - 90100, true, null, MessageBody.Photo(ImageRef(0, width = 1280, height = 960), RichText("Фото машины на складе")), state = SendState.Read),
        MessageItem(9, 2, now - 90200, false, olga, MessageBody.Video(0, null, 1280, 720, 83)),
        MessageItem(8, 2, now - 90300, false, olga, MessageBody.Sticker(0, 512, 512, StickerFormat.Webp, "😀")),
    )
}
