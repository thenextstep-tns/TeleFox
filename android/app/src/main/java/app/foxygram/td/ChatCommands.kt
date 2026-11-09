package app.foxygram.td

import app.foxygram.model.TopicItem
import kotlinx.coroutines.withContext
import org.drinkless.tdlib.TdApi

/** Actions on a whole chat, used by the long-press menu. */
class ChatCommands(private val telegram: Telegram) {
    private suspend fun chat(id: Long): TdApi.Chat? = withContext(telegram.serial) { telegram.store.chat(id) }

    suspend fun setPinned(chatId: Long, pinned: Boolean) {
        telegram.call(TdApi.ToggleChatIsPinned(TdApi.ChatListMain(), chatId, pinned))
    }

    suspend fun setMuted(chatId: Long, muted: Boolean) {
        val settings = chat(chatId)?.notificationSettings ?: return
        settings.useDefaultMuteFor = false
        settings.muteFor = if (muted) MUTE_FOREVER_SECONDS else 0
        telegram.call(TdApi.SetChatNotificationSettings(chatId, settings))
    }

    suspend fun setArchived(chatId: Long, archived: Boolean) {
        val list: TdApi.ChatList = if (archived) TdApi.ChatListArchive() else TdApi.ChatListMain()
        telegram.call(TdApi.AddChatToList(chatId, list))
    }

    /** Every topic of a group with topics, pinned first, then by latest activity. */
    suspend fun forumTopics(chatId: Long): List<TopicItem> = withContext(telegram.serial) {
        val found = LinkedHashMap<Int, TdApi.ForumTopic>()
        var offsetDate = 0
        var offsetMessage = 0L
        var offsetTopic = 0
        for (round in 0 until MAX_TOPIC_PAGES) {
            val page = telegram.call(TdApi.GetForumTopics(chatId, "", offsetDate, offsetMessage, offsetTopic, TOPIC_PAGE))
            val fresh = page.topics.filter { it.info.forumTopicId !in found }
            fresh.forEach { found[it.info.forumTopicId] = it }
            if (fresh.isEmpty() || (page.nextOffsetDate == 0 && page.nextOffsetMessageId == 0L && page.nextOffsetForumTopicId == 0)) break
            offsetDate = page.nextOffsetDate
            offsetMessage = page.nextOffsetMessageId
            offsetTopic = page.nextOffsetForumTopicId
        }
        found.values.sortedWith(compareByDescending<TdApi.ForumTopic> { it.isPinned }.thenByDescending { it.order }).map { topic ->
            TopicItem(
                id = topic.info.forumTopicId,
                title = topic.info.name,
                preview = topic.lastMessage?.let { telegram.mapper.previewOf(it.content).first }.orEmpty(),
                date = topic.lastMessage?.date ?: 0,
                unread = topic.unreadCount,
                mentions = topic.unreadMentionCount,
                color = OPAQUE or topic.info.icon.color.toLong(),
            )
        }
    }

    /** The folders this chat isn't in yet and can be added to. */
    suspend fun foldersToAdd(chatId: Long): List<Int> =
        telegram.call(TdApi.GetChatListsToAddChat(chatId)).chatLists.filterIsInstance<TdApi.ChatListFolder>().map { it.chatFolderId }

    suspend fun addToFolder(chatId: Long, folderId: Int) {
        telegram.call(TdApi.AddChatToList(chatId, TdApi.ChatListFolder(folderId)))
    }

    suspend fun createFolder(chatId: Long, name: String) {
        val folder = TdApi.ChatFolder().apply {
            this.name = TdApi.ChatFolderName(TdApi.FormattedText(name, emptyArray()), false)
            colorId = NO_FOLDER_COLOR
            pinnedChatIds = LongArray(0)
            includedChatIds = longArrayOf(chatId)
            excludedChatIds = LongArray(0)
        }
        telegram.call(TdApi.CreateChatFolder(folder))
    }

    suspend fun markRead(chatId: Long) {
        val chat = chat(chatId) ?: return
        val last = chat.lastMessage?.id
        if (chat.isMarkedAsUnread) telegram.call(TdApi.ToggleChatIsMarkedAsUnread(chatId, false))
        if (last != null) {
            telegram.call(TdApi.OpenChat(chatId))
            telegram.call(TdApi.ViewMessages(chatId, longArrayOf(last), null, true))
            telegram.call(TdApi.CloseChat(chatId))
        }
    }

    suspend fun markUnread(chatId: Long) {
        telegram.call(TdApi.ToggleChatIsMarkedAsUnread(chatId, true))
    }

    suspend fun remove(chatId: Long) {
        val type = chat(chatId)?.type
        if (type is TdApi.ChatTypeSupergroup || type is TdApi.ChatTypeBasicGroup) {
            telegram.call(TdApi.LeaveChat(chatId))
        } else {
            telegram.call(TdApi.DeleteChatHistory(chatId, true, false))
        }
    }

    suspend fun isPinned(chatId: Long): Boolean = withContext(telegram.serial) {
        val store = telegram.store
        store.chat(chatId)?.let { store.position(it, "main")?.isPinned } ?: false
    }

    suspend fun isMuted(chatId: Long): Boolean = withContext(telegram.serial) {
        val store = telegram.store
        store.chat(chatId)?.let(store::isMuted) ?: false
    }

    suspend fun isArchived(chatId: Long): Boolean = withContext(telegram.serial) {
        val store = telegram.store
        store.chat(chatId)?.let { store.position(it, "archive") != null } ?: false
    }

    private companion object {
        const val MUTE_FOREVER_SECONDS = 366 * 24 * 3600
        const val NO_FOLDER_COLOR = -1
        const val TOPIC_PAGE = 100
        const val MAX_TOPIC_PAGES = 10
        const val OPAQUE = 0xFF000000L
    }
}
