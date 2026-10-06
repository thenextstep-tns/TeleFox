package com.telefox.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.media.AudioAttributes;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.os.Build;
import android.os.SystemClock;
import android.util.Log;

/**
 * Shows message notifications. Called from the embedded Python engine.
 *
 * Sound is played by the app itself instead of relying on the notification channel: several
 * OEM skins (including Realme/ColorOS) show the pop-up but stay silent, whatever the channel says.
 * The channel is therefore silent and {@link #playSound} makes the noise, honouring the ringer
 * mode and Do Not Disturb. The reason for every skipped sound is kept for the diagnostics screen.
 */
public final class Notifier {

    // Channel settings are frozen by Android after creation, so changes need a new channel id.
    public static final String CHANNEL_LOUD = "messages_v3";
    private static final String CHANNEL_QUIET = "messages_quiet_v3";
    private static final String[] OLD_CHANNELS = {"messages", "messages_quiet", "messages_v2", "messages_quiet_v2"};
    private static final long[] VIBRATION_PATTERN = {0, 200, 100, 200};
    private static final long MIN_SOUND_GAP_MS = 1500;
    private static final String TAG = "TeleFoxNotifier";

    private static volatile String lastSoundStatus = "ещё не проигрывался";
    private static long lastSoundAt = 0;

    private Notifier() {}

    public static void createChannels(Context ctx) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = ctx.getSystemService(NotificationManager.class);
        for (String old : OLD_CHANNELS) nm.deleteNotificationChannel(old);

        NotificationChannel loud = new NotificationChannel(
                CHANNEL_LOUD, ctx.getString(R.string.channel_messages), NotificationManager.IMPORTANCE_HIGH);
        loud.setSound(null, null); // played by playSound()
        loud.enableVibration(true);
        loud.setVibrationPattern(VIBRATION_PATTERN);
        loud.enableLights(true);
        NotificationChannel quiet = new NotificationChannel(
                CHANNEL_QUIET, ctx.getString(R.string.channel_messages_quiet), NotificationManager.IMPORTANCE_LOW);
        quiet.setSound(null, null);
        nm.createNotificationChannel(loud);
        nm.createNotificationChannel(quiet);
    }

    public static void notifyMessage(String title, String text, String chatId, boolean sound, boolean vibrate) {
        Context ctx = TeleFoxService.appContext;
        if (ctx == null) return;
        NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;

        Intent open = new Intent(ctx, MainActivity.class)
                .setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP)
                .putExtra(MainActivity.EXTRA_CHAT_ID, chatId);
        int id = chatId.hashCode();
        PendingIntent pi = PendingIntent.getActivity(
                ctx, id, open, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        boolean loud = sound || vibrate;
        Notification.Builder b = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(ctx, loud ? CHANNEL_LOUD : CHANNEL_QUIET)
                : new Notification.Builder(ctx);
        b.setSmallIcon(R.drawable.ic_notification)
                .setContentTitle(title)
                .setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text))
                .setContentIntent(pi)
                .setAutoCancel(true)
                .setCategory(Notification.CATEGORY_MESSAGE)
                .setOnlyAlertOnce(false);
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            b.setDefaults(vibrate ? Notification.DEFAULT_VIBRATE : 0).setPriority(Notification.PRIORITY_HIGH);
        }
        nm.notify(id, b.build());

        if (sound) playSound(ctx, nm);
        else lastSoundStatus = "выключен в настройках TeleFox";
    }

    /** Plays the bundled tone on the notification stream unless the phone is silenced. */
    private static synchronized void playSound(Context ctx, NotificationManager nm) {
        long now = SystemClock.elapsedRealtime();
        if (now - lastSoundAt < MIN_SOUND_GAP_MS) {
            lastSoundStatus = "пропущен: слишком часто";
            return;
        }
        AudioManager am = (AudioManager) ctx.getSystemService(Context.AUDIO_SERVICE);
        if (am.getRingerMode() != AudioManager.RINGER_MODE_NORMAL) {
            lastSoundStatus = "пропущен: телефон в беззвучном режиме / вибрации";
            return;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
                && nm.getCurrentInterruptionFilter() != NotificationManager.INTERRUPTION_FILTER_ALL) {
            lastSoundStatus = "пропущен: включён режим «Не беспокоить»";
            return;
        }
        if (am.getStreamVolume(AudioManager.STREAM_NOTIFICATION) == 0) {
            lastSoundStatus = "пропущен: громкость уведомлений = 0";
            return;
        }
        try {
            AudioAttributes attrs = new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_NOTIFICATION)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build();
            MediaPlayer mp = MediaPlayer.create(ctx, R.raw.message, attrs, am.generateAudioSessionId());
            if (mp == null) {
                lastSoundStatus = "ошибка: не удалось создать плеер";
                return;
            }
            mp.setOnCompletionListener(MediaPlayer::release);
            mp.setOnErrorListener((p, what, extra) -> { p.release(); return true; });
            mp.start();
            lastSoundAt = now;
            lastSoundStatus = "проигран";
        } catch (Exception e) {
            Log.w(TAG, "Sound failed", e);
            lastSoundStatus = "ошибка: " + e.getMessage();
        }
    }

    /** Human-readable state of everything that can silence a notification. */
    public static String diagnostics(Context ctx) {
        NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
        AudioManager am = (AudioManager) ctx.getSystemService(Context.AUDIO_SERVICE);
        StringBuilder sb = new StringBuilder();
        sb.append("Уведомления разрешены: ").append(nm.areNotificationsEnabled() ? "да" : "НЕТ").append('\n');
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel ch = nm.getNotificationChannel(CHANNEL_LOUD);
            sb.append("Канал сообщений: ");
            if (ch == null) sb.append("не создан");
            else sb.append(ch.getImportance() >= NotificationManager.IMPORTANCE_HIGH ? "всплывающие" : "приглушён (важность " + ch.getImportance() + ")");
            sb.append('\n');
        }
        String ringer;
        switch (am.getRingerMode()) {
            case AudioManager.RINGER_MODE_NORMAL: ringer = "обычный"; break;
            case AudioManager.RINGER_MODE_VIBRATE: ringer = "только вибрация"; break;
            default: ringer = "беззвучный";
        }
        sb.append("Режим звонка: ").append(ringer).append('\n');
        sb.append("Громкость уведомлений: ").append(am.getStreamVolume(AudioManager.STREAM_NOTIFICATION))
                .append(" из ").append(am.getStreamMaxVolume(AudioManager.STREAM_NOTIFICATION)).append('\n');
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            sb.append("Не беспокоить: ")
                    .append(nm.getCurrentInterruptionFilter() == NotificationManager.INTERRUPTION_FILTER_ALL ? "выключен" : "ВКЛЮЧЁН")
                    .append('\n');
        }
        sb.append("Последний звук: ").append(lastSoundStatus);
        return sb.toString();
    }
}
