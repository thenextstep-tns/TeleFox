package app.foxygram.td

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
    }
}
