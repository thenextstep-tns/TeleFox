package app.foxygram.td

import org.drinkless.tdlib.TdApi

/** Local mirror of what TDLib has told us. Only touched from Telegram.serial. */
class TdStore {
    private val chats = HashMap<Long, TdApi.Chat>()
    private val users = HashMap<Long, TdApi.User>()
    private val supergroups = HashMap<Long, TdApi.Supergroup>()
    private val basicGroups = HashMap<Long, TdApi.BasicGroup>()
    private val scopes = HashMap<String, TdApi.ScopeNotificationSettings>()
    private val typing = HashMap<Long, MutableMap<Long, Long>>()

    var folders: List<TdApi.ChatFolderInfo> = emptyList()
    val unreadByList = HashMap<String, Int>()
    var myId: Long = 0

    fun chat(id: Long): TdApi.Chat? = chats[id]
    fun user(id: Long): TdApi.User? = users[id]
    fun supergroup(id: Long): TdApi.Supergroup? = supergroups[id]
    fun basicGroup(id: Long): TdApi.BasicGroup? = basicGroups[id]
    fun allChats(): Collection<TdApi.Chat> = chats.values

    fun hasArchive(): Boolean = chats.values.any { chat -> chat.positions.any { it.list is TdApi.ChatListArchive && it.order != 0L } }

    /** Telegram's own ordering: the server-provided order, ties broken by chat id. */
    fun ordered(listKey: String): List<TdApi.Chat> =
        chats.values
            .mapNotNull { chat -> position(chat, listKey)?.let { chat to it } }
            .sortedWith(compareByDescending<Pair<TdApi.Chat, TdApi.ChatPosition>> { it.second.order }.thenByDescending { it.first.id })
            .map { it.first }

    fun position(chat: TdApi.Chat, listKey: String): TdApi.ChatPosition? =
        chat.positions.firstOrNull { Telegram.listKey(it.list) == listKey && it.order != 0L }

    fun scopeFor(chat: TdApi.Chat): TdApi.ScopeNotificationSettings? {
        val key = when (val type = chat.type) {
            is TdApi.ChatTypePrivate, is TdApi.ChatTypeSecret -> "private"
            is TdApi.ChatTypeBasicGroup -> "group"
            is TdApi.ChatTypeSupergroup -> if (type.isChannel) "channel" else "group"
            else -> "private"
        }
        return scopes[key]
    }

    fun isMuted(chat: TdApi.Chat): Boolean {
        val settings = chat.notificationSettings
        return if (settings.useDefaultMuteFor) (scopeFor(chat)?.muteFor ?: 0) > 0 else settings.muteFor > 0
    }

    fun mentionsDisabled(chat: TdApi.Chat): Boolean {
        val settings = chat.notificationSettings
        return if (settings.useDefaultDisableMentionNotifications) {
            scopeFor(chat)?.disableMentionNotifications ?: false
        } else {
            settings.disableMentionNotifications
        }
    }

    fun typingLabel(chatId: Long, nowMs: Long, isGroup: Boolean): String? {
        val active = typing[chatId] ?: return null
        active.entries.removeAll { it.value < nowMs }
        val id = active.keys.firstOrNull() ?: return null
        if (!isGroup) return "печатает…"
        return (users[id]?.firstName ?: "Кто-то") + " печатает…"
    }

    /** Returns true when the chat list on screen needs refreshing. */
    fun onUpdate(update: TdApi.Object): Boolean {
        when (update) {
            is TdApi.UpdateNewChat -> chats[update.chat.id] = update.chat
            is TdApi.UpdateChatTitle -> chats[update.chatId]?.title = update.title
            is TdApi.UpdateChatPhoto -> chats[update.chatId]?.photo = update.photo
            is TdApi.UpdateChatLastMessage -> chats[update.chatId]?.let {
                it.lastMessage = update.lastMessage
                it.positions = mergePositions(it.positions, update.positions)
            }
            is TdApi.UpdateChatPosition -> chats[update.chatId]?.let {
                it.positions = mergePositions(it.positions, arrayOf(update.position))
            }
            is TdApi.UpdateChatReadInbox -> chats[update.chatId]?.let {
                it.lastReadInboxMessageId = update.lastReadInboxMessageId
                it.unreadCount = update.unreadCount
            }
            is TdApi.UpdateChatReadOutbox -> chats[update.chatId]?.lastReadOutboxMessageId = update.lastReadOutboxMessageId
            is TdApi.UpdateChatIsMarkedAsUnread -> chats[update.chatId]?.isMarkedAsUnread = update.isMarkedAsUnread
            is TdApi.UpdateChatUnreadMentionCount -> chats[update.chatId]?.unreadMentionCount = update.unreadMentionCount
            is TdApi.UpdateMessageMentionRead -> chats[update.chatId]?.unreadMentionCount = update.unreadMentionCount
            is TdApi.UpdateChatUnreadReactionCount -> chats[update.chatId]?.unreadReactionCount = update.unreadReactionCount
            is TdApi.UpdateMessageUnreadReactions -> chats[update.chatId]?.unreadReactionCount = update.unreadReactionCount
            is TdApi.UpdateChatNotificationSettings -> chats[update.chatId]?.notificationSettings = update.notificationSettings
            is TdApi.UpdateChatDraftMessage -> chats[update.chatId]?.let {
                it.draftMessage = update.draftMessage
                it.positions = mergePositions(it.positions, update.positions)
            }
            is TdApi.UpdateScopeNotificationSettings -> {
                val key = when (update.scope) {
                    is TdApi.NotificationSettingsScopeGroupChats -> "group"
                    is TdApi.NotificationSettingsScopeChannelChats -> "channel"
                    else -> "private"
                }
                scopes[key] = update.notificationSettings
            }
            is TdApi.UpdateUser -> users[update.user.id] = update.user
            is TdApi.UpdateUserStatus -> {
                users[update.userId]?.status = update.status
                return false
            }
            is TdApi.UpdateSupergroup -> supergroups[update.supergroup.id] = update.supergroup
            is TdApi.UpdateBasicGroup -> basicGroups[update.basicGroup.id] = update.basicGroup
            is TdApi.UpdateOption -> {
                if (update.name == "my_id") myId = (update.value as? TdApi.OptionValueInteger)?.value ?: 0
                return false
            }
            is TdApi.UpdateChatAction -> {
                val sender = update.senderId as? TdApi.MessageSenderUser ?: return false
                val active = typing.getOrPut(update.chatId) { HashMap() }
                if (update.action is TdApi.ChatActionCancel) {
                    active.remove(sender.userId)
                } else {
                    active[sender.userId] = System.currentTimeMillis() + TYPING_VISIBLE_MS
                }
            }
            else -> return false
        }
        return true
    }

    private fun mergePositions(current: Array<TdApi.ChatPosition>, changes: Array<TdApi.ChatPosition>): Array<TdApi.ChatPosition> {
        val merged = current.toMutableList()
        for (change in changes) {
            merged.removeAll { Telegram.listKey(it.list) == Telegram.listKey(change.list) }
            if (change.order != 0L) merged += change
        }
        return merged.toTypedArray()
    }

    private companion object {
        const val TYPING_VISIBLE_MS = 6_000L
    }
}
