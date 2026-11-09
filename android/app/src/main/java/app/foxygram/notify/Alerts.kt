package app.foxygram.notify

import android.app.Application
import android.app.NotificationManager
import android.content.Context
import android.os.PowerManager
import app.foxygram.model.ChatKind
import app.foxygram.td.Telegram
import kotlinx.coroutines.launch
import org.drinkless.tdlib.TdApi

/** How a folder alerts, loudest first. */
enum class AlertMode { All, Mentions, Off }

data class AlertFacts(
    val outgoing: Boolean,
    val pending: Boolean,
    val isService: Boolean,
    val ageSeconds: Long,
    val muted: Boolean,
    val mentionsMe: Boolean,
    val mentionAlertsOff: Boolean,
    val chatOnScreen: Boolean,
    val folderMode: AlertMode = AlertMode.All,
)

/** A chat can be in several folders. The loudest wins, so a quiet folder can't silence a chat you follow elsewhere. */
fun loudestMode(modes: List<AlertMode>): AlertMode = modes.minByOrNull { it.ordinal } ?: AlertMode.All

// After sleep or reconnect, older messages are caught up silently instead of ringing one by one.
private const val MAX_ALERT_AGE_SECONDS = 300L

/** Whether a new message should make the phone alert. Pure, so the rules are easy to test. */
fun shouldAlert(facts: AlertFacts): Boolean {
    if (facts.outgoing || facts.pending || facts.isService || facts.chatOnScreen) return false
    if (facts.ageSeconds > MAX_ALERT_AGE_SECONDS) return false
    if (facts.folderMode == AlertMode.Off) return false
    if (facts.muted || facts.folderMode == AlertMode.Mentions) return facts.mentionsMe && !facts.mentionAlertsOff
    return true
}

class Alerts(private val app: Application, private val telegram: Telegram) {
    private val notifier by lazy { Notifier(app) }
    private val power by lazy {
        app.getSystemService(PowerManager::class.java).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "foxygram:alert")
            .apply { setReferenceCounted(false) }
    }
    private val shown = HashSet<Long>()

    /** Called on the Telegram thread, in order, as messages arrive. */
    fun onNewMessage(message: TdApi.Message) {
        val store = telegram.store
        val chat = store.chat(message.chatId) ?: return
        val facts = AlertFacts(
            outgoing = message.isOutgoing,
            pending = message.sendingState != null,
            isService = telegram.mapper.isServiceContent(message.content),
            ageSeconds = System.currentTimeMillis() / 1000 - message.date,
            muted = store.isMuted(chat),
            mentionsMe = message.containsUnreadMention,
            mentionAlertsOff = store.mentionsDisabled(chat),
            chatOnScreen = telegram.appVisible && telegram.visibleChatId == message.chatId &&
                (telegram.visibleTopicId == 0 || (message.topicId as? TdApi.MessageTopicForum)?.forumTopicId == telegram.visibleTopicId),
        )
        if (!shouldAlert(facts)) return
        // Keep the CPU awake just long enough to post it and start the sound.
        power.acquire(WAKE_MS)
        telegram.scope.launch(telegram.serial) {
            // TDLib reports a new message before the chat's new list positions, so ask for them.
            val positions = runCatching { telegram.call(TdApi.GetChat(chat.id)).positions }.getOrDefault(chat.positions)
            val folders = positions.filter { it.order != 0L }.map { Telegram.listKey(it.list) }.filter { it != "main" && it != "other" }
            val settings = telegram.settings
            val mode = loudestMode(folders.map(settings::alertMode))
            if (!shouldAlert(facts.copy(folderMode = mode))) return@launch
            val mapper = telegram.mapper
            val kind = mapper.kindOf(chat)
            notifier.post(
                chatId = chat.id,
                messageId = message.id,
                title = if (kind == ChatKind.Saved) "Избранное" else chat.title,
                sender = mapper.senderName(message.senderId),
                text = mapper.previewOf(message.content).first,
                isGroup = kind == ChatKind.Group,
                date = message.date,
                sound = folders.filter { settings.alertMode(it) == mode }.firstNotNullOfOrNull(settings::alertSound),
            )
            shown += chat.id
        }
    }

    /** Read somewhere else (or here): the alert has done its job. */
    fun onRead(chatId: Long, unread: Int) {
        if (unread == 0 && shown.remove(chatId)) notifier.cancel(chatId)
    }

    fun clearChat(chatId: Long) {
        shown.remove(chatId)
        notifier.cancel(chatId)
    }

    fun diagnostics(): String = notifier.diagnostics()

    private companion object {
        const val WAKE_MS = 3_000L
    }
}

val Context.notifications: NotificationManager get() = getSystemService(NotificationManager::class.java)
