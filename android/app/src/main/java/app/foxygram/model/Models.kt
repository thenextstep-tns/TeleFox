package app.foxygram.model

import androidx.compose.runtime.Immutable

/** A file the UI can show: a tiny inline preview now, the real file once downloaded. */
@Immutable
data class ImageRef(
    val fileId: Int,
    val mini: ByteArray? = null,
    val width: Int = 0,
    val height: Int = 0,
) {
    override fun equals(other: Any?) = other is ImageRef && other.fileId == fileId
    override fun hashCode() = fileId
}

enum class ChatKind { Private, Group, Channel, Saved }

enum class SendState { None, Sending, Failed, Sent, Read }

/** Labels that come from the laptop server. */
@Immutable
data class ChatLabel(
    val needsReply: Boolean = false,
    val urgent: Boolean = false,
    val projectName: String? = null,
    val projectColor: Long? = null,
    val categoryName: String? = null,
    val caseId: Long? = null,
    val caseTitle: String? = null,
    val aiEnabled: Boolean = false,
)

@Immutable
data class ChatItem(
    val id: Long,
    val title: String,
    val kind: ChatKind,
    val photo: ImageRef? = null,
    val colorIndex: Int = 0,
    val senderPrefix: String? = null,
    val preview: String = "",
    val previewIsLabel: Boolean = false,
    val previewThumb: ImageRef? = null,
    val date: Int = 0,
    val unread: Int = 0,
    val mentions: Int = 0,
    val reactions: Int = 0,
    val muted: Boolean = false,
    val pinned: Boolean = false,
    val status: SendState = SendState.None,
    val draft: String? = null,
    val typing: String? = null,
    val verified: Boolean = false,
    val isForum: Boolean = false,
    val label: ChatLabel? = null,
)

@Immutable
data class FolderTab(val id: Int, val title: String, val unread: Int = 0)

@Immutable
data class TopicItem(val id: Int, val title: String, val preview: String, val date: Int, val unread: Int, val mentions: Int, val color: Long)

enum class SpanType { Bold, Italic, Underline, Strike, Spoiler, Code, Pre, Url, TextUrl, Mention, Hashtag, Command, Email, Phone, BlockQuote }

@Immutable
data class TextSpan(val start: Int, val length: Int, val type: SpanType, val url: String? = null, val userId: Long = 0)

@Immutable
data class RichText(val text: String, val spans: List<TextSpan> = emptyList()) {
    val isBlank get() = text.isBlank()

    companion object {
        val Empty = RichText("")
    }
}

@Immutable
data class Sender(
    val id: Long,
    val name: String,
    val photo: ImageRef? = null,
    val colorIndex: Int = 0,
    val isChat: Boolean = false,
)

@Immutable
data class ReplyInfo(
    val messageId: Long,
    val senderName: String,
    val text: String,
    val colorIndex: Int = 0,
    val thumb: ImageRef? = null,
)

@Immutable
data class ReactionItem(val emoji: String, val count: Int, val chosen: Boolean)

@Immutable
data class WebPreview(
    val site: String,
    val title: String,
    val description: String,
    val photo: ImageRef? = null,
    val url: String,
)

@Immutable
data class PollOptionItem(val text: String, val percent: Int, val votes: Int, val chosen: Boolean)

enum class StickerFormat { Webp, Lottie, Video }

@Immutable
sealed interface MessageBody {
    val caption: RichText get() = RichText.Empty

    @Immutable data class Text(val text: RichText, val web: WebPreview? = null) : MessageBody
    @Immutable data class Photo(val image: ImageRef, override val caption: RichText = RichText.Empty) : MessageBody
    @Immutable data class Video(
        val fileId: Int,
        val thumb: ImageRef?,
        val width: Int,
        val height: Int,
        val duration: Int,
        val isGif: Boolean = false,
        val size: Long = 0,
        override val caption: RichText = RichText.Empty,
    ) : MessageBody
    @Immutable data class Album(val items: List<MessageBody>, override val caption: RichText = RichText.Empty) : MessageBody
    @Immutable data class Voice(
        val fileId: Int,
        val duration: Int,
        val waveform: List<Int>,
        val listened: Boolean = true,
        override val caption: RichText = RichText.Empty,
    ) : MessageBody
    @Immutable data class Round(val fileId: Int, val thumb: ImageRef?, val duration: Int) : MessageBody
    @Immutable data class Audio(val fileId: Int, val title: String, val performer: String, val duration: Int, override val caption: RichText = RichText.Empty) : MessageBody
    @Immutable data class Document(
        val fileId: Int,
        val name: String,
        val size: Long,
        val mime: String,
        val thumb: ImageRef? = null,
        override val caption: RichText = RichText.Empty,
    ) : MessageBody
    @Immutable data class Sticker(val fileId: Int, val width: Int, val height: Int, val format: StickerFormat, val emoji: String, val thumb: ImageRef? = null) : MessageBody
    @Immutable data class Poll(val pollId: Long, val question: String, val options: List<PollOptionItem>, val total: Int, val closed: Boolean, val quiz: Boolean, val voted: Boolean) : MessageBody
    @Immutable data class Location(val latitude: Double, val longitude: Double, val title: String = "") : MessageBody
    @Immutable data class Contact(val name: String, val phone: String, val userId: Long) : MessageBody
    @Immutable data class Call(val video: Boolean, val duration: Int, val missed: Boolean) : MessageBody
    @Immutable data class Service(val text: String) : MessageBody
    @Immutable data object Unsupported : MessageBody
}

@Immutable
data class MessageItem(
    val id: Long,
    val chatId: Long,
    val date: Int,
    val outgoing: Boolean,
    val sender: Sender?,
    val body: MessageBody,
    val reply: ReplyInfo? = null,
    val forwardFrom: String? = null,
    val edited: Boolean = false,
    val state: SendState = SendState.None,
    val reactions: List<ReactionItem> = emptyList(),
    val albumId: Long = 0,
    val views: Int = 0,
    val canEdit: Boolean = false,
    val canDelete: Boolean = true,
    val mentionsMe: Boolean = false,
    /** Every message id behind an album row, oldest first. Empty for a single message. */
    val groupIds: List<Long> = emptyList(),
)

/** One row of the conversation, newest first because the list is laid out from the bottom. */
@Immutable
sealed interface FeedRow {
    val key: String

    @Immutable data class Date(val text: String, val epochDay: Long) : FeedRow {
        override val key get() = "d$epochDay"
    }

    @Immutable data object UnreadMarker : FeedRow {
        override val key get() = "unread"
    }

    @Immutable data class Message(
        val item: MessageItem,
        val startsGroup: Boolean,
        val endsGroup: Boolean,
        val showSenderName: Boolean,
        val showAvatar: Boolean,
    ) : FeedRow {
        override val key get() = "m${item.id}"
    }
}

@Immutable
data class CaseSummary(
    val id: Long,
    val title: String,
    val summary: String,
    val status: String,
    val updatedAt: Long,
    val chats: List<String>,
    val entities: List<String>,
    val needsReview: Int,
)

@Immutable
data class CaseEvent(
    val burstId: Long,
    val chatId: Long,
    val chatTitle: String,
    val createdAt: Long,
    val intent: String,
    val needsReply: Boolean,
    val urgency: String,
    val summary: String,
    val needsReview: Boolean,
    val messages: List<CaseMessage>,
)

@Immutable
data class CaseMessage(val messageId: Long, val date: Long, val sender: String, val outgoing: Boolean, val text: String)
