package app.foxygram.td

import app.foxygram.model.ChatItem
import app.foxygram.model.ChatKind
import app.foxygram.model.ChatLabel
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
import org.drinkless.tdlib.TdApi

private const val MAX_PHOTO_WIDTH = 1280
private const val WAVEFORM_BITS = 5

/** Turns TDLib objects into plain UI models. Runs on Telegram.serial. */
class TdMapper(private val store: TdStore, private val files: TdFiles) {

    fun kindOf(chat: TdApi.Chat): ChatKind = when (val type = chat.type) {
        is TdApi.ChatTypePrivate -> if (type.userId == store.myId) ChatKind.Saved else ChatKind.Private
        is TdApi.ChatTypeSecret -> ChatKind.Private
        is TdApi.ChatTypeBasicGroup -> ChatKind.Group
        is TdApi.ChatTypeSupergroup -> if (type.isChannel) ChatKind.Channel else ChatKind.Group
        else -> ChatKind.Private
    }

    private fun track(file: TdApi.File?): Int {
        if (file == null) return 0
        files.onFile(file)
        return file.id
    }

    private fun chatPhoto(photo: TdApi.ChatPhotoInfo?): ImageRef? =
        photo?.let { ImageRef(track(it.small), it.minithumbnail?.data) }

    fun toChatItem(chat: TdApi.Chat, listKey: String, label: ChatLabel?): ChatItem {
        val kind = kindOf(chat)
        val position = store.position(chat, listKey)
        val last = chat.lastMessage
        val isGroup = kind == ChatKind.Group
        val draft = (chat.draftMessage?.content as? TdApi.DraftMessageContentText)?.text?.text?.ifBlank { null }
        val preview = last?.let { previewOf(it.content) }
        val prefix = when {
            last == null || kind == ChatKind.Channel || kind == ChatKind.Saved -> null
            last.isOutgoing -> if (isServiceContent(last.content)) null else "Вы"
            isGroup && !isServiceContent(last.content) -> shortSenderName(last.senderId)
            else -> null
        }
        val status = when {
            last == null || !last.isOutgoing || kind == ChatKind.Channel && false -> SendState.None
            else -> sendState(last, chat)
        }
        return ChatItem(
            id = chat.id,
            title = if (kind == ChatKind.Saved) "Избранное" else chat.title.ifBlank { "Удалённый аккаунт" },
            kind = kind,
            photo = chatPhoto(chat.photo),
            colorIndex = chat.accentColorId,
            senderPrefix = prefix,
            preview = preview?.first.orEmpty(),
            previewIsLabel = preview?.second ?: false,
            previewThumb = last?.let { previewThumb(it.content) },
            date = last?.date ?: 0,
            unread = if (chat.unreadCount > 0) chat.unreadCount else if (chat.isMarkedAsUnread) 1 else 0,
            mentions = chat.unreadMentionCount,
            reactions = chat.unreadReactionCount,
            muted = store.isMuted(chat),
            pinned = position?.isPinned ?: false,
            status = status,
            draft = draft,
            typing = store.typingLabel(chat.id, System.currentTimeMillis(), isGroup),
            verified = verified(chat),
            isForum = (chat.type as? TdApi.ChatTypeSupergroup)?.let { store.supergroup(it.supergroupId)?.isForum } ?: false,
            label = label,
        )
    }

    private fun verified(chat: TdApi.Chat): Boolean = when (val type = chat.type) {
        is TdApi.ChatTypePrivate -> store.user(type.userId)?.verificationStatus?.isVerified ?: false
        is TdApi.ChatTypeSupergroup -> store.supergroup(type.supergroupId)?.verificationStatus?.isVerified ?: false
        else -> false
    }

    fun sendState(message: TdApi.Message, chat: TdApi.Chat?): SendState = when {
        !message.isOutgoing -> SendState.None
        message.sendingState is TdApi.MessageSendingStatePending -> SendState.Sending
        message.sendingState is TdApi.MessageSendingStateFailed -> SendState.Failed
        chat != null && message.id <= chat.lastReadOutboxMessageId -> SendState.Read
        else -> SendState.Sent
    }

    private fun shortSenderName(sender: TdApi.MessageSender): String? = when (sender) {
        is TdApi.MessageSenderUser -> store.user(sender.userId)?.firstName?.ifBlank { null }
        is TdApi.MessageSenderChat -> store.chat(sender.chatId)?.title
        else -> null
    }

    fun senderName(sender: TdApi.MessageSender): String = when (sender) {
        is TdApi.MessageSenderUser -> userName(sender.userId)
        is TdApi.MessageSenderChat -> store.chat(sender.chatId)?.title.orEmpty()
        else -> ""
    }

    fun userName(id: Long): String {
        val user = store.user(id) ?: return ""
        return listOf(user.firstName, user.lastName).filter { it.isNotBlank() }.joinToString(" ").ifBlank { "Удалённый аккаунт" }
    }

    private fun sender(message: TdApi.Message): Sender? = when (val source = message.senderId) {
        is TdApi.MessageSenderUser -> store.user(source.userId).let { user ->
            Sender(
                source.userId,
                userName(source.userId),
                user?.profilePhoto?.let { ImageRef(track(it.small), it.minithumbnail?.data) },
                user?.accentColorId ?: 0,
            )
        }
        is TdApi.MessageSenderChat -> store.chat(source.chatId).let { chat ->
            Sender(source.chatId, chat?.title.orEmpty(), chatPhoto(chat?.photo), chat?.accentColorId ?: 0, isChat = true)
        }
        else -> null
    }

    /** Short text for the chat list and notifications, and whether it is a label like "Фото". */
    fun previewOf(content: TdApi.MessageContent): Pair<String, Boolean> {
        fun labelled(label: String, caption: TdApi.FormattedText?): Pair<String, Boolean> {
            val text = caption?.text.orEmpty().replace('\n', ' ')
            return if (text.isBlank()) label to true else "$label, $text" to true
        }
        return when (content) {
            is TdApi.MessageText -> content.text.text.replace('\n', ' ') to false
            is TdApi.MessageAnimatedEmoji -> content.emoji to false
            is TdApi.MessagePhoto -> labelled("Фото", content.caption)
            is TdApi.MessageVideo -> labelled("Видео", content.caption)
            is TdApi.MessageAnimation -> labelled("GIF", content.caption)
            is TdApi.MessageAudio -> labelled("Аудио", content.caption)
            is TdApi.MessageDocument -> (content.document.fileName.ifBlank { "Файл" }) to true
            is TdApi.MessageVoiceNote -> labelled("Голосовое сообщение", content.caption)
            is TdApi.MessageVideoNote -> "Видеосообщение" to true
            is TdApi.MessageSticker -> "${content.sticker.emoji} Стикер".trim() to true
            is TdApi.MessagePoll -> "Опрос: ${content.poll.question.text}" to true
            is TdApi.MessageLocation -> "Геопозиция" to true
            is TdApi.MessageVenue -> "Геопозиция" to true
            is TdApi.MessageContact -> "Контакт" to true
            is TdApi.MessageCall -> callLabel(content) to true
            else -> serviceText(content, null) to true
        }
    }

    private fun callLabel(content: TdApi.MessageCall): String =
        if (content.discardReason is TdApi.CallDiscardReasonMissed) "Пропущенный звонок" else "Звонок"

    private fun previewThumb(content: TdApi.MessageContent): ImageRef? = when (content) {
        is TdApi.MessagePhoto -> content.photo.sizes.firstOrNull()?.let { ImageRef(track(it.photo), content.photo.minithumbnail?.data) }
        is TdApi.MessageVideo -> content.video.thumbnail?.let { ImageRef(track(it.file), content.video.minithumbnail?.data) }
        else -> null
    }

    fun isServiceContent(content: TdApi.MessageContent): Boolean = when (content) {
        is TdApi.MessageText, is TdApi.MessageAnimatedEmoji, is TdApi.MessagePhoto, is TdApi.MessageVideo,
        is TdApi.MessageAnimation, is TdApi.MessageAudio, is TdApi.MessageDocument, is TdApi.MessageVoiceNote,
        is TdApi.MessageVideoNote, is TdApi.MessageSticker, is TdApi.MessagePoll, is TdApi.MessageLocation,
        is TdApi.MessageVenue, is TdApi.MessageContact, is TdApi.MessageCall, is TdApi.MessageUnsupported -> false
        else -> true
    }

    private fun serviceText(content: TdApi.MessageContent, senderName: String?): String {
        val who = senderName?.ifBlank { null } ?: "Участник"
        return when (content) {
            is TdApi.MessagePinMessage -> "$who закрепил(а) сообщение"
            is TdApi.MessageChatChangeTitle -> "$who изменил(а) название на «${content.title}»"
            is TdApi.MessageChatChangePhoto -> "$who обновил(а) фото группы"
            is TdApi.MessageChatDeletePhoto -> "$who удалил(а) фото группы"
            is TdApi.MessageChatAddMembers -> "$who добавил(а) участников"
            is TdApi.MessageChatJoinByLink, is TdApi.MessageChatJoinByRequest -> "$who присоединился(ась)"
            is TdApi.MessageChatDeleteMember -> "$who покинул(а) группу"
            is TdApi.MessageBasicGroupChatCreate, is TdApi.MessageSupergroupChatCreate -> "Группа создана"
            is TdApi.MessageChatUpgradeFrom, is TdApi.MessageChatUpgradeTo -> "Группа преобразована"
            is TdApi.MessageScreenshotTaken -> "$who сделал(а) скриншот"
            is TdApi.MessageContactRegistered -> "$who теперь в Telegram"
            is TdApi.MessageForumTopicCreated -> "Создана тема «${content.name}»"
            is TdApi.MessageVideoChatStarted -> "Видеочат начат"
            is TdApi.MessageVideoChatEnded -> "Видеочат завершён"
            is TdApi.MessageExpiredPhoto -> "Фото истекло"
            is TdApi.MessageExpiredVideo -> "Видео истекло"
            is TdApi.MessageExpiredVideoNote -> "Видеосообщение истекло"
            is TdApi.MessageExpiredVoiceNote -> "Голосовое сообщение истекло"
            is TdApi.MessageCustomServiceAction -> content.text
            else -> "Служебное сообщение"
        }
    }

    fun richText(formatted: TdApi.FormattedText?): RichText {
        if (formatted == null) return RichText.Empty
        val spans = formatted.entities.orEmpty().mapNotNull { entity ->
            val type: Pair<SpanType, String?>? = when (val kind = entity.type) {
                is TdApi.TextEntityTypeBold -> SpanType.Bold to null
                is TdApi.TextEntityTypeItalic -> SpanType.Italic to null
                is TdApi.TextEntityTypeUnderline -> SpanType.Underline to null
                is TdApi.TextEntityTypeStrikethrough -> SpanType.Strike to null
                is TdApi.TextEntityTypeSpoiler -> SpanType.Spoiler to null
                is TdApi.TextEntityTypeCode -> SpanType.Code to null
                is TdApi.TextEntityTypePre, is TdApi.TextEntityTypePreCode -> SpanType.Pre to null
                is TdApi.TextEntityTypeBlockQuote, is TdApi.TextEntityTypeExpandableBlockQuote -> SpanType.BlockQuote to null
                is TdApi.TextEntityTypeUrl -> SpanType.Url to null
                is TdApi.TextEntityTypeTextUrl -> SpanType.TextUrl to kind.url
                is TdApi.TextEntityTypeMention -> SpanType.Mention to null
                is TdApi.TextEntityTypeHashtag, is TdApi.TextEntityTypeCashtag -> SpanType.Hashtag to null
                is TdApi.TextEntityTypeBotCommand -> SpanType.Command to null
                is TdApi.TextEntityTypeEmailAddress -> SpanType.Email to null
                is TdApi.TextEntityTypePhoneNumber -> SpanType.Phone to null
                is TdApi.TextEntityTypeMentionName -> SpanType.Mention to "tg://user?id=${kind.userId}"
                else -> null
            }
            type?.let { TextSpan(entity.offset, entity.length, it.first, it.second) }
        }
        return RichText(formatted.text, spans)
    }

    private fun bestSize(photo: TdApi.Photo): TdApi.PhotoSize? =
        photo.sizes.lastOrNull { it.width <= MAX_PHOTO_WIDTH && it.height <= MAX_PHOTO_WIDTH } ?: photo.sizes.lastOrNull()

    private fun image(photo: TdApi.Photo): ImageRef {
        val size = bestSize(photo)
        return ImageRef(track(size?.photo), photo.minithumbnail?.data, size?.width ?: 0, size?.height ?: 0)
    }

    private fun thumb(thumbnail: TdApi.Thumbnail?, mini: TdApi.Minithumbnail?): ImageRef? {
        val usable = thumbnail?.takeUnless { it.format is TdApi.ThumbnailFormatMpeg4 || it.format is TdApi.ThumbnailFormatTgs || it.format is TdApi.ThumbnailFormatWebm }
        if (usable == null && mini == null) return null
        return ImageRef(track(usable?.file), mini?.data, usable?.width ?: 0, usable?.height ?: 0)
    }

    private fun waveform(data: ByteArray?): List<Int> {
        if (data == null || data.isEmpty()) return emptyList()
        val count = data.size * 8 / WAVEFORM_BITS
        return List(count) { index ->
            val bit = index * WAVEFORM_BITS
            val byte = bit / 8
            val shift = bit % 8
            val current = data[byte].toInt() and 0xFF
            val next = if (byte + 1 < data.size) data[byte + 1].toInt() and 0xFF else 0
            ((current or (next shl 8)) shr shift) and 0x1F
        }
    }

    private fun link(preview: TdApi.LinkPreview?): WebPreview? {
        if (preview == null) return null
        val photo = (preview.type as? TdApi.LinkPreviewTypeArticle)?.photo ?: (preview.type as? TdApi.LinkPreviewTypePhoto)?.photo
        return WebPreview(preview.siteName, preview.title, preview.description?.text.orEmpty(), photo?.let(::image), preview.url)
    }

    fun body(message: TdApi.Message): MessageBody = when (val content = message.content) {
        is TdApi.MessageText -> MessageBody.Text(richText(content.text), link(content.linkPreview))
        is TdApi.MessageAnimatedEmoji -> MessageBody.Text(RichText(content.emoji))
        is TdApi.MessagePhoto -> MessageBody.Photo(image(content.photo), richText(content.caption))
        is TdApi.MessageVideo -> content.video.let {
            MessageBody.Video(track(it.video), thumb(it.thumbnail, it.minithumbnail), it.width, it.height, it.duration, size = it.video.size, caption = richText(content.caption))
        }
        is TdApi.MessageAnimation -> content.animation.let {
            MessageBody.Video(track(it.animation), thumb(it.thumbnail, it.minithumbnail), it.width, it.height, it.duration, isGif = true, size = it.animation.size, caption = richText(content.caption))
        }
        is TdApi.MessageVoiceNote -> content.voiceNote.let {
            MessageBody.Voice(track(it.voice), it.duration, waveform(it.waveform), content.isListened, richText(content.caption))
        }
        is TdApi.MessageVideoNote -> content.videoNote.let { MessageBody.Round(track(it.video), thumb(it.thumbnail, it.minithumbnail), it.duration) }
        is TdApi.MessageAudio -> content.audio.let { MessageBody.Audio(track(it.audio), it.title.ifBlank { it.fileName }, it.performer, it.duration, richText(content.caption)) }
        is TdApi.MessageDocument -> content.document.let {
            MessageBody.Document(track(it.document), it.fileName, it.document.size, it.mimeType, thumb(it.thumbnail, it.minithumbnail), richText(content.caption))
        }
        is TdApi.MessageSticker -> content.sticker.let {
            val format = when (it.format) {
                is TdApi.StickerFormatTgs -> StickerFormat.Lottie
                is TdApi.StickerFormatWebm -> StickerFormat.Video
                else -> StickerFormat.Webp
            }
            MessageBody.Sticker(track(it.sticker), it.width, it.height, format, it.emoji, thumb(it.thumbnail, null))
        }
        is TdApi.MessagePoll -> content.poll.let { poll ->
            MessageBody.Poll(
                poll.id, poll.question.text,
                poll.options.map { PollOptionItem(it.text.text, it.votePercentage, it.voterCount, it.isChosen) },
                poll.totalVoterCount, poll.isClosed, poll.type is TdApi.PollTypeQuiz, poll.options.any { it.isChosen },
            )
        }
        is TdApi.MessageLocation -> MessageBody.Location(content.location.latitude, content.location.longitude)
        is TdApi.MessageVenue -> MessageBody.Location(content.venue.location.latitude, content.venue.location.longitude, content.venue.title)
        is TdApi.MessageContact -> content.contact.let { MessageBody.Contact("${it.firstName} ${it.lastName}".trim(), it.phoneNumber, it.userId) }
        is TdApi.MessageCall -> MessageBody.Call(content.isVideo, content.duration, content.discardReason is TdApi.CallDiscardReasonMissed)
        is TdApi.MessageUnsupported -> MessageBody.Unsupported
        else -> MessageBody.Service(serviceText(content, senderName(message.senderId)))
    }

    private fun reactions(message: TdApi.Message): List<ReactionItem> =
        message.interactionInfo?.reactions?.reactions.orEmpty().mapNotNull { reaction ->
            val type = reaction.type as? TdApi.ReactionTypeEmoji ?: return@mapNotNull null
            ReactionItem(type.emoji, reaction.totalCount, reaction.isChosen)
        }

    private fun forwardName(info: TdApi.MessageForwardInfo?): String? = when (val origin = info?.origin) {
        null -> null
        is TdApi.MessageOriginUser -> userName(origin.senderUserId)
        is TdApi.MessageOriginHiddenUser -> origin.senderName
        is TdApi.MessageOriginChat -> store.chat(origin.senderChatId)?.title.orEmpty()
        is TdApi.MessageOriginChannel -> store.chat(origin.chatId)?.title.orEmpty()
        else -> ""
    }

    fun replyInfo(replied: TdApi.Message): ReplyInfo = ReplyInfo(
        messageId = replied.id,
        senderName = senderName(replied.senderId),
        text = previewOf(replied.content).first,
        colorIndex = when (val source = replied.senderId) {
            is TdApi.MessageSenderUser -> store.user(source.userId)?.accentColorId ?: 0
            is TdApi.MessageSenderChat -> store.chat(source.chatId)?.accentColorId ?: 0
            else -> 0
        },
        thumb = previewThumb(replied.content),
    )

    fun toItem(message: TdApi.Message, chat: TdApi.Chat?, replied: TdApi.Message?): MessageItem {
        val canEdit = message.isOutgoing && message.sendingState == null &&
            System.currentTimeMillis() / 1000 - message.date < EDIT_WINDOW_SECONDS &&
            (message.content is TdApi.MessageText || message.content is TdApi.MessagePhoto || message.content is TdApi.MessageVideo || message.content is TdApi.MessageDocument)
        return MessageItem(
            id = message.id,
            chatId = message.chatId,
            date = message.date,
            outgoing = message.isOutgoing && !message.isChannelPost,
            sender = sender(message),
            body = body(message),
            reply = replied?.let(::replyInfo),
            forwardFrom = forwardName(message.forwardInfo),
            edited = message.editDate > 0,
            state = sendState(message, chat),
            reactions = reactions(message),
            albumId = message.mediaAlbumId,
            views = if (message.isChannelPost) message.interactionInfo?.viewCount ?: 0 else 0,
            canEdit = canEdit,
            canDelete = true,
            mentionsMe = message.containsUnreadMention,
        )
    }

    private companion object {
        const val EDIT_WINDOW_SECONDS = 48 * 3600
    }
}
