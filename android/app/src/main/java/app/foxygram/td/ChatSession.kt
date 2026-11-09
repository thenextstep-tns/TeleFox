package app.foxygram.td

import app.foxygram.model.ChatKind
import app.foxygram.model.FeedRow
import app.foxygram.model.MessageItem
import app.foxygram.model.buildFeed
import app.foxygram.ui.chat.ChatHeaderState
import app.foxygram.ui.common.pluralRu
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.drinkless.tdlib.TdApi
import java.util.TreeMap

private const val PAGE_SIZE = 50
private const val AROUND_UNREAD_NEWER = 30

private class ReadState(val unread: Int, val lastRead: Long, val lastMessageId: Long?)

/** One open conversation, or one topic of it when topicId isn't 0. Mutated only on Telegram.serial. */
class ChatSession(
    private val telegram: Telegram,
    val chatId: Long,
    private val topicId: Int = 0,
    private val topicTitle: String? = null,
) {
    private val sendTopic: TdApi.MessageTopic? get() = if (topicId == 0) null else TdApi.MessageTopicForum(topicId)
    private val store get() = telegram.store
    private val mapper get() = telegram.mapper

    private val messages = TreeMap<Long, TdApi.Message>(reverseOrder())
    private val replied = HashMap<Long, TdApi.Message>()
    private val replyRequested = HashSet<Long>()
    private val itemCache = HashMap<Long, MessageItem>()

    private var firstUnreadId: Long? = null
    private var loadingOlder = false
    private var loadingNewer = false
    private var reachedOldest = false
    private var reachedNewest = false
    private val pendingViews = HashSet<Long>()

    private val _feed = MutableStateFlow<List<FeedRow>>(emptyList())
    val feed: StateFlow<List<FeedRow>> = _feed.asStateFlow()

    private val _header = MutableStateFlow<ChatHeaderState?>(null)
    val header: StateFlow<ChatHeaderState?> = _header.asStateFlow()

    /** Index in the feed to scroll to when the chat first opens; consumed once. */
    private val _initialAnchor = MutableStateFlow<Int?>(null)
    val initialAnchor: StateFlow<Int?> = _initialAnchor.asStateFlow()

    private val kind: ChatKind get() = store.chat(chatId)?.let(mapper::kindOf) ?: ChatKind.Private

    fun open() {
        telegram.scope.launch(telegram.serial) {
            telegram.activeSession = this@ChatSession
            telegram.visibleChatId = chatId
            telegram.visibleTopicId = topicId
            telegram.alerts.clearChat(chatId)
            telegram.fire(TdApi.OpenChat(chatId))
            refreshHeader()
            initialLoad()
        }
    }

    fun close() {
        telegram.fire(TdApi.CloseChat(chatId))
        if (telegram.activeSession === this) telegram.activeSession = null
        if (telegram.visibleChatId == chatId) {
            telegram.visibleChatId = 0
            telegram.visibleTopicId = 0
        }
    }

    private suspend fun readState(): ReadState {
        if (topicId == 0) {
            val chat = store.chat(chatId)
            return ReadState(chat?.unreadCount ?: 0, chat?.lastReadInboxMessageId ?: 0, chat?.lastMessage?.id)
        }
        val topic = runCatching { telegram.call(TdApi.GetForumTopic(chatId, topicId)) }.getOrNull()
        return ReadState(topic?.unreadCount ?: 0, topic?.lastReadInboxMessageId ?: 0, topic?.lastMessage?.id)
    }

    private fun belongsHere(message: TdApi.Message): Boolean =
        message.chatId == chatId && (topicId == 0 || (message.topicId as? TdApi.MessageTopicForum)?.forumTopicId == topicId)

    private suspend fun initialLoad() {
        val read = readState()
        if (read.unread > 0 && read.lastRead > 0) {
            val around = fetch(read.lastRead, -AROUND_UNREAD_NEWER, PAGE_SIZE)
            add(around)
            firstUnreadId = messages.keys.filter { it > read.lastRead }.minOrNull()
            reachedNewest = messages.isEmpty() || messages.firstKey() == read.lastMessageId
        } else {
            add(fetch(0, 0, PAGE_SIZE))
            reachedNewest = true
        }
        rebuild()
        firstUnreadId?.let { unread ->
            val index = _feed.value.indexOfFirst { it is FeedRow.Message && (it.item.id == unread || unread in it.item.groupIds) }
            if (index >= 0) _initialAnchor.value = index + 1
        }
    }

    fun consumeAnchor() {
        _initialAnchor.value = null
    }

    /** TDLib may return only a few messages at a time from its cache, so keep asking. */
    private suspend fun fetch(from: Long, offset: Int, limit: Int): List<TdApi.Message> {
        val result = LinkedHashMap<Long, TdApi.Message>()
        var cursor = from
        var currentOffset = offset
        repeat(MAX_FETCH_ROUNDS) {
            val batch = runCatching {
                if (topicId == 0) {
                    telegram.call(TdApi.GetChatHistory(chatId, cursor, currentOffset, limit, false)).messages
                } else {
                    telegram.call(TdApi.GetForumTopicHistory(chatId, topicId, cursor, currentOffset, limit)).messages
                }
            }.getOrNull().orEmpty().filterNotNull()
            val fresh = batch.filter { it.id !in result }
            if (fresh.isEmpty()) return result.values.toList()
            fresh.forEach { result[it.id] = it }
            if (result.size >= limit) return result.values.toList()
            cursor = result.keys.min()
            currentOffset = 0
        }
        return result.values.toList()
    }

    private fun add(batch: List<TdApi.Message>) {
        batch.forEach { messages[it.id] = it }
    }

    fun loadOlder() {
        telegram.scope.launch(telegram.serial) {
            if (loadingOlder || reachedOldest || messages.isEmpty()) return@launch
            loadingOlder = true
            val batch = fetch(messages.lastKey(), 0, PAGE_SIZE).filter { it.id !in messages }
            if (batch.isEmpty()) reachedOldest = true else add(batch)
            loadingOlder = false
            rebuild()
        }
    }

    fun loadNewer() {
        telegram.scope.launch(telegram.serial) {
            if (loadingNewer || reachedNewest || messages.isEmpty()) return@launch
            loadingNewer = true
            val batch = fetch(messages.firstKey(), -PAGE_SIZE + 1, PAGE_SIZE).filter { it.id !in messages }
            if (batch.isEmpty()) reachedNewest = true else add(batch)
            if (messages.firstKey() == store.chat(chatId)?.lastMessage?.id) reachedNewest = true
            loadingNewer = false
            rebuild()
        }
    }

    /** Jump to the live end, for the scroll-to-bottom button when history was opened mid-way. */
    fun jumpToLatest() {
        telegram.scope.launch(telegram.serial) {
            if (reachedNewest) return@launch
            messages.clear()
            itemCache.clear()
            firstUnreadId = null
            add(fetch(0, 0, PAGE_SIZE))
            reachedNewest = true
            rebuild()
        }
    }

    fun onVisible(ids: List<Long>) {
        telegram.scope.launch(telegram.serial) {
            val unseen = ids.filter { it !in pendingViews && it > 0 }
            if (unseen.isEmpty()) return@launch
            pendingViews += unseen
            val source: TdApi.MessageSource = if (topicId == 0) TdApi.MessageSourceChatHistory() else TdApi.MessageSourceForumTopicHistory()
            telegram.fire(TdApi.ViewMessages(chatId, unseen.toLongArray(), source, true))
        }
    }

    private fun invalidate(id: Long) {
        itemCache.remove(id)
    }

    fun onUpdate(update: TdApi.Object) {
        when (update) {
            is TdApi.UpdateNewMessage -> if (belongsHere(update.message) && reachedNewest) {
                messages[update.message.id] = update.message
                rebuild()
            }
            is TdApi.UpdateMessageSendSucceeded -> if (belongsHere(update.message)) {
                messages.remove(update.oldMessageId)
                invalidate(update.oldMessageId)
                messages[update.message.id] = update.message
                rebuild()
            }
            is TdApi.UpdateMessageSendFailed -> if (belongsHere(update.message)) {
                messages.remove(update.oldMessageId)
                invalidate(update.oldMessageId)
                messages[update.message.id] = update.message
                rebuild()
            }
            is TdApi.UpdateMessageContent -> if (update.chatId == chatId) {
                messages[update.messageId]?.let {
                    it.content = update.newContent
                    invalidate(update.messageId)
                    rebuild()
                }
            }
            is TdApi.UpdateMessageEdited -> if (update.chatId == chatId) {
                messages[update.messageId]?.let {
                    it.editDate = update.editDate
                    invalidate(update.messageId)
                    rebuild()
                }
            }
            is TdApi.UpdateMessageInteractionInfo -> if (update.chatId == chatId) {
                messages[update.messageId]?.let {
                    it.interactionInfo = update.interactionInfo
                    invalidate(update.messageId)
                    rebuild()
                }
            }
            is TdApi.UpdateMessageContentOpened -> if (update.chatId == chatId) {
                val message = messages[update.messageId]
                (message?.content as? TdApi.MessageVoiceNote)?.isListened = true
                invalidate(update.messageId)
                rebuild()
            }
            is TdApi.UpdateDeleteMessages -> if (update.chatId == chatId && update.isPermanent) {
                update.messageIds.forEach {
                    messages.remove(it)
                    invalidate(it)
                }
                rebuild()
            }
            is TdApi.UpdateChatReadOutbox -> if (update.chatId == chatId) {
                itemCache.keys.filter { messages[it]?.isOutgoing == true }.forEach(::invalidate)
                rebuild()
            }
            is TdApi.UpdateChatTitle, is TdApi.UpdateChatPhoto, is TdApi.UpdateChatReadInbox, is TdApi.UpdateChatLastMessage ->
                refreshHeader()
            is TdApi.UpdateUserStatus -> {
                val type = store.chat(chatId)?.type
                if (type is TdApi.ChatTypePrivate && type.userId == update.userId) refreshHeader()
            }
            is TdApi.UpdateChatAction -> if (update.chatId == chatId) refreshHeader()
            is TdApi.UpdateUser -> {
                // A name that arrived late can change how existing messages are drawn.
                val sender = update.user.id
                val stale = messages.values.filter { (it.senderId as? TdApi.MessageSenderUser)?.userId == sender }
                if (stale.isNotEmpty()) {
                    stale.forEach { invalidate(it.id) }
                    rebuild()
                }
            }
        }
    }

    private fun repliedTo(message: TdApi.Message): TdApi.Message? {
        val reply = message.replyTo as? TdApi.MessageReplyToMessage ?: return null
        val id = reply.messageId
        if (id == 0L || (reply.chatId != 0L && reply.chatId != chatId)) return null
        messages[id]?.let { return it }
        replied[id]?.let { return it }
        if (replyRequested.add(id)) {
            telegram.scope.launch(telegram.serial) {
                val found = runCatching { telegram.call(TdApi.GetRepliedMessage(chatId, message.id)) }.getOrNull()
                if (found != null) {
                    replied[id] = found
                    messages.values.filter { (it.replyTo as? TdApi.MessageReplyToMessage)?.messageId == id }.forEach { invalidate(it.id) }
                    rebuild()
                }
            }
        }
        return null
    }

    private fun rebuild() {
        val chat = store.chat(chatId)
        val items = messages.values.map { message ->
            val quoted = repliedTo(message)
            itemCache[message.id]?.takeIf { it.reply != null || quoted == null }
                ?: mapper.toItem(message, chat, quoted).also { itemCache[message.id] = it }
        }
        _feed.value = buildFeed(items, kind, firstUnreadId)
    }

    private fun refreshHeader() {
        val chat = store.chat(chatId) ?: return
        val item = mapper.toChatItem(chat, Telegram.listKey(TdApi.ChatListMain()), telegram.labels.value[chatId])
        _header.value = if (topicTitle != null) {
            ChatHeaderState(item.copy(title = topicTitle), item.title)
        } else {
            ChatHeaderState(item, item.typing ?: subtitle(chat, item.kind))
        }
    }

    private fun subtitle(chat: TdApi.Chat, kind: ChatKind): String = when (val type = chat.type) {
        is TdApi.ChatTypePrivate -> if (kind == ChatKind.Saved) "" else status(type.userId)
        is TdApi.ChatTypeBasicGroup -> members(store.basicGroup(type.basicGroupId)?.memberCount ?: 0, false)
        is TdApi.ChatTypeSupergroup -> members(store.supergroup(type.supergroupId)?.memberCount ?: 0, type.isChannel)
        else -> ""
    }

    private fun members(count: Int, channel: Boolean): String = when {
        count == 0 -> if (channel) "канал" else "группа"
        channel -> "$count " + pluralRu(count, "подписчик", "подписчика", "подписчиков")
        else -> "$count " + pluralRu(count, "участник", "участника", "участников")
    }

    private fun status(userId: Long): String {
        val user = store.user(userId) ?: return ""
        if (user.type is TdApi.UserTypeBot) return "бот"
        return when (val value = user.status) {
            is TdApi.UserStatusOnline -> "в сети"
            is TdApi.UserStatusOffline -> "был(а) " + app.foxygram.ui.common.listTime(value.wasOnline)
            is TdApi.UserStatusRecently -> "был(а) недавно"
            is TdApi.UserStatusLastWeek -> "был(а) на этой неделе"
            is TdApi.UserStatusLastMonth -> "был(а) в этом месяце"
            else -> "был(а) давно"
        }
    }

    suspend fun sendText(text: String, replyTo: Long?) {
        telegram.call(TdApi.SendMessage(chatId, sendTopic, replyTarget(replyTo), null, null,
            TdApi.InputMessageText(TdApi.FormattedText(text, emptyArray()), null, true)))
    }

    suspend fun editText(messageId: Long, text: String) {
        telegram.call(TdApi.EditMessageText(chatId, messageId, null,
            TdApi.InputMessageText(TdApi.FormattedText(text, emptyArray()), null, true)))
    }

    suspend fun sendContent(content: TdApi.InputMessageContent, replyTo: Long?) {
        telegram.call(TdApi.SendMessage(chatId, sendTopic, replyTarget(replyTo), null, null, content))
    }

    private fun replyTarget(replyTo: Long?): TdApi.InputMessageReplyTo? =
        replyTo?.let { TdApi.InputMessageReplyToMessage(it, null, 0, "") }

    suspend fun delete(ids: List<Long>, forEveryone: Boolean) {
        telegram.call(TdApi.DeleteMessages(chatId, ids.toLongArray(), forEveryone))
    }

    suspend fun react(messageId: Long, emoji: String, chosen: Boolean) {
        val type = TdApi.ReactionTypeEmoji(emoji)
        if (chosen) {
            telegram.call(TdApi.RemoveMessageReaction(chatId, messageId, type))
        } else {
            telegram.call(TdApi.AddMessageReaction(chatId, messageId, type, false, false))
        }
    }

    suspend fun vote(messageId: Long, option: Int) {
        telegram.call(TdApi.SetPollAnswer(chatId, messageId, intArrayOf(option)))
    }

    suspend fun saveDraft(text: String) {
        val draft = text.takeIf { it.isNotBlank() }?.let {
            TdApi.DraftMessage(null, 0, TdApi.DraftMessageContentText(TdApi.FormattedText(it, emptyArray()), null), 0, null)
        }
        runCatching { telegram.call(TdApi.SetChatDraftMessage(chatId, sendTopic, draft)) }
    }

    suspend fun initialDraft(): String = withContext(telegram.serial) {
        val draft = if (topicId == 0) {
            store.chat(chatId)?.draftMessage
        } else {
            runCatching { telegram.call(TdApi.GetForumTopic(chatId, topicId)).draftMessage }.getOrNull()
        }
        (draft?.content as? TdApi.DraftMessageContentText)?.text?.text.orEmpty()
    }

    private companion object {
        const val MAX_FETCH_ROUNDS = 6
    }
}
