package app.foxygram.notify

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Person
import android.app.RemoteInput
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import android.os.SystemClock
import android.util.Log
import app.foxygram.MainActivity
import app.foxygram.R

private const val CHANNEL_MESSAGES = "messages"
private const val MAX_MESSAGES_SHOWN = 7
private const val MIN_SOUND_GAP_MS = 1_500L
private const val GROUP_KEY = "foxygram.messages"
private const val SUMMARY_ID = 1
private const val TAG = "FoxyNotifier"

const val EXTRA_CHAT_ID = "chat_id"
const val KEY_REPLY = "reply"

/**
 * Posts one notification per chat with its recent messages.
 * The sound is played here rather than by the channel, because some phones (Realme included)
 * show the pop-up and stay silent. The ringer mode and Do Not Disturb are still honoured.
 */
class Notifier(private val context: Context) {
    private data class Line(val id: Long, val sender: String, val text: String, val date: Int)

    private val manager = context.notifications
    private val lines = HashMap<Long, MutableList<Line>>()
    private var lastSoundAt = 0L
    @Volatile private var lastSound = "ещё не проигрывался"

    init {
        val channel = NotificationChannel(CHANNEL_MESSAGES, "Сообщения", NotificationManager.IMPORTANCE_HIGH).apply {
            setSound(null, null)
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 180, 90, 180)
            setShowBadge(true)
        }
        manager.createNotificationChannel(channel)
    }

    private fun notificationId(chatId: Long): Int = (chatId xor (chatId ushr 32)).toInt().let { if (it == SUMMARY_ID) 2 else it }

    @Synchronized
    fun post(chatId: Long, messageId: Long, title: String, sender: String, text: String, isGroup: Boolean, date: Int) {
        val history = lines.getOrPut(chatId) { ArrayList() }
        if (history.any { it.id == messageId }) return
        history += Line(messageId, sender, text, date)
        while (history.size > MAX_MESSAGES_SHOWN) history.removeAt(0)

        val me = Person.Builder().setName("Вы").build()
        val style = Notification.MessagingStyle(me).setConversationTitle(if (isGroup) title else null).setGroupConversation(isGroup)
        history.forEach { line ->
            val person = Person.Builder().setName(if (isGroup) line.sender else title).build()
            style.addMessage(line.text, line.date * 1000L, person)
        }

        val open = Intent(context, MainActivity::class.java)
            .setFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            .putExtra(EXTRA_CHAT_ID, chatId)
        val id = notificationId(chatId)
        val content = PendingIntent.getActivity(context, id, open, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

        val notification = Notification.Builder(context, CHANNEL_MESSAGES)
            .setSmallIcon(R.drawable.ic_notification)
            .setStyle(style)
            .setContentIntent(content)
            .setAutoCancel(true)
            .setCategory(Notification.CATEGORY_MESSAGE)
            .setGroup(GROUP_KEY)
            .setGroupAlertBehavior(Notification.GROUP_ALERT_CHILDREN)
            .addAction(replyAction(chatId, id))
            .addAction(markReadAction(chatId, id))
            .build()
        manager.notify(id, notification)
        postSummary()
        playSound()
    }

    private fun postSummary() {
        val summary = Notification.Builder(context, CHANNEL_MESSAGES)
            .setSmallIcon(R.drawable.ic_notification)
            .setGroup(GROUP_KEY)
            .setGroupSummary(true)
            .setGroupAlertBehavior(Notification.GROUP_ALERT_CHILDREN)
            .setAutoCancel(true)
            .build()
        manager.notify(SUMMARY_ID, summary)
    }

    private fun replyAction(chatId: Long, id: Int): Notification.Action {
        val intent = Intent(context, NotificationActionReceiver::class.java)
            .setAction(NotificationActionReceiver.ACTION_REPLY)
            .putExtra(EXTRA_CHAT_ID, chatId)
        val pending = PendingIntent.getBroadcast(context, id, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE)
        val input = RemoteInput.Builder(KEY_REPLY).setLabel("Ответить").build()
        return Notification.Action.Builder(null, "Ответить", pending).addRemoteInput(input).build()
    }

    private fun markReadAction(chatId: Long, id: Int): Notification.Action {
        val intent = Intent(context, NotificationActionReceiver::class.java)
            .setAction(NotificationActionReceiver.ACTION_MARK_READ)
            .putExtra(EXTRA_CHAT_ID, chatId)
        val pending = PendingIntent.getBroadcast(context, id + 1, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        return Notification.Action.Builder(null, "Прочитано", pending).build()
    }

    @Synchronized
    fun cancel(chatId: Long) {
        lines.remove(chatId)
        manager.cancel(notificationId(chatId))
        if (lines.isEmpty()) manager.cancel(SUMMARY_ID)
    }

    private fun playSound() {
        val now = SystemClock.elapsedRealtime()
        if (now - lastSoundAt < MIN_SOUND_GAP_MS) return
        val audio = context.getSystemService(AudioManager::class.java)
        lastSound = when {
            audio.ringerMode != AudioManager.RINGER_MODE_NORMAL -> "пропущен: беззвучный режим"
            manager.currentInterruptionFilter != NotificationManager.INTERRUPTION_FILTER_ALL -> "пропущен: режим «Не беспокоить»"
            audio.getStreamVolume(AudioManager.STREAM_NOTIFICATION) == 0 -> "пропущен: громкость уведомлений 0"
            else -> try {
                val attributes = AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_NOTIFICATION)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build()
                val player = MediaPlayer.create(context, R.raw.message, attributes, audio.generateAudioSessionId())
                player?.setOnCompletionListener(MediaPlayer::release)
                player?.start()
                lastSoundAt = now
                if (player != null) "проигран" else "ошибка плеера"
            } catch (error: Exception) {
                Log.w(TAG, "sound failed", error)
                "ошибка: ${error.message}"
            }
        }
    }

    fun diagnostics(): String {
        val audio = context.getSystemService(AudioManager::class.java)
        val ringer = when (audio.ringerMode) {
            AudioManager.RINGER_MODE_NORMAL -> "обычный"
            AudioManager.RINGER_MODE_VIBRATE -> "вибрация"
            else -> "беззвучный"
        }
        return buildString {
            appendLine("Уведомления разрешены: " + if (manager.areNotificationsEnabled()) "да" else "НЕТ")
            appendLine("Режим звонка: $ringer")
            appendLine("Громкость уведомлений: ${audio.getStreamVolume(AudioManager.STREAM_NOTIFICATION)} из ${audio.getStreamMaxVolume(AudioManager.STREAM_NOTIFICATION)}")
            appendLine("Не беспокоить: " + if (manager.currentInterruptionFilter == NotificationManager.INTERRUPTION_FILTER_ALL) "выключен" else "ВКЛЮЧЁН")
            append("Последний звук: $lastSound")
        }
    }
}
