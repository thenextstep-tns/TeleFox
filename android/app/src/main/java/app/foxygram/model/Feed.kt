package app.foxygram.model

import app.foxygram.ui.common.dayHeader
import app.foxygram.ui.common.epochDay

private const val GROUP_WINDOW_SECONDS = 5 * 60

/** Merges album members and works out grouping, dates and avatars. Input and output are newest first. */
fun buildFeed(messages: List<MessageItem>, kind: ChatKind, firstUnreadId: Long?): List<FeedRow> {
    val merged = mergeAlbums(messages)
    val rows = ArrayList<FeedRow>(merged.size + 16)
    for (index in merged.indices) {
        val current = merged[index]
        val newer = merged.getOrNull(index - 1)
        val older = merged.getOrNull(index + 1)
        val joinsOlder = older != null && sameGroup(older, current)
        val joinsNewer = newer != null && sameGroup(current, newer)
        val isGroupChat = kind == ChatKind.Group
        rows += FeedRow.Message(
            item = current,
            startsGroup = !joinsOlder,
            endsGroup = !joinsNewer,
            showSenderName = isGroupChat && !current.outgoing && !joinsOlder && current.body.showsName(),
            showAvatar = isGroupChat && !current.outgoing && !joinsNewer,
        )
        if (firstUnreadId != null && current.id == firstUnreadId) rows += FeedRow.UnreadMarker
        if (older == null || epochDay(older.date) != epochDay(current.date)) {
            rows += FeedRow.Date(dayHeader(current.date), epochDay(current.date))
        }
    }
    return rows
}

private fun MessageBody.showsName(): Boolean = this !is MessageBody.Sticker && this !is MessageBody.Round

private fun sameGroup(older: MessageItem, newer: MessageItem): Boolean {
    if (older.body is MessageBody.Service || newer.body is MessageBody.Service) return false
    if (older.outgoing != newer.outgoing || older.sender?.id != newer.sender?.id) return false
    if (epochDay(older.date) != epochDay(newer.date)) return false
    return newer.date - older.date <= GROUP_WINDOW_SECONDS
}

private fun mergeAlbums(messages: List<MessageItem>): List<MessageItem> {
    val result = ArrayList<MessageItem>(messages.size)
    var index = 0
    while (index < messages.size) {
        val head = messages[index]
        if (head.albumId == 0L) {
            result += head
            index++
            continue
        }
        var end = index + 1
        while (end < messages.size && messages[end].albumId == head.albumId) end++
        // Only photos and videos share one grid. Files sent together (several PDFs, say) stay one message each, so every
        // file shows with its name and can be opened; a grid has no place for them.
        val visual = messages.subList(index, end).all { it.body is MessageBody.Photo || it.body is MessageBody.Video }
        if (end - index == 1 || !visual) {
            for (i in index until end) result += messages[i]
        } else {
            val members = messages.subList(index, end).asReversed()
            val caption = members.firstOrNull { !it.body.caption.isBlank }?.body?.caption ?: RichText.Empty
            result += head.copy(
                body = MessageBody.Album(members.map { it.body }, caption),
                reply = members.firstNotNullOfOrNull { it.reply },
                groupIds = members.map { it.id },
                reactions = members.flatMap { it.reactions },
            )
        }
        index = end
    }
    return result
}
