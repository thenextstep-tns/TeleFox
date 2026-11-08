package app.foxygram.notify

import android.app.Application
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.RemoteInput
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import app.foxygram.MainActivity
import app.foxygram.R
import app.foxygram.td.Telegram
import kotlinx.coroutines.launch
import org.drinkless.tdlib.TdApi

private const val CHANNEL_SERVICE = "connection"
private const val SERVICE_NOTIFICATION_ID = 7

/**
 * Keeps one Telegram connection open so messages arrive the moment they are sent, with no
 * Firebase involved. It does no polling of its own: TDLib's single socket is the only activity.
 */
class ConnectionService : Service() {
    override fun onCreate() {
        super.onCreate()
        val manager = notifications
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_SERVICE, "Фоновое соединение", NotificationManager.IMPORTANCE_MIN).apply { setShowBadge(false) }
        )
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val notification = Notification.Builder(this, CHANNEL_SERVICE)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("FoxyGram")
            .setContentText("Подключён к Telegram")
            .setContentIntent(open)
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(SERVICE_NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING)
        } else {
            startForeground(SERVICE_NOTIFICATION_ID, notification)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Telegram.get(application).start()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        fun start(context: Context) {
            context.startForegroundService(Intent(context, ConnectionService::class.java))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, ConnectionService::class.java))
        }
    }
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        val telegram = Telegram.get(context.applicationContext as Application)
        if (telegram.settings.apiId != 0 && telegram.settings.keepConnected) ConnectionService.start(context)
    }
}

class NotificationActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val telegram = Telegram.get(context.applicationContext as Application)
        telegram.start()
        val chatId = intent.getLongExtra(EXTRA_CHAT_ID, 0)
        if (chatId == 0L) return
        val pending = goAsync()
        telegram.scope.launch {
            try {
                when (intent.action) {
                    ACTION_REPLY -> {
                        val text = RemoteInput.getResultsFromIntent(intent)?.getCharSequence(KEY_REPLY)?.toString()
                        if (!text.isNullOrBlank()) {
                            telegram.call(TdApi.SendMessage(chatId, null, null, null, null,
                                TdApi.InputMessageText(TdApi.FormattedText(text, emptyArray()), null, true)))
                        }
                        app.foxygram.td.ChatCommands(telegram).markRead(chatId)
                    }
                    ACTION_MARK_READ -> app.foxygram.td.ChatCommands(telegram).markRead(chatId)
                }
                telegram.alerts.clearChat(chatId)
            } catch (_: Exception) {
                // The notification stays, so the user can still act on it.
            } finally {
                pending.finish()
            }
        }
    }

    companion object {
        const val ACTION_REPLY = "app.foxygram.REPLY"
        const val ACTION_MARK_READ = "app.foxygram.MARK_READ"
    }
}
