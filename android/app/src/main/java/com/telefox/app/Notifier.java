package com.telefox.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.media.AudioAttributes;
import android.os.Build;
import android.provider.Settings;
import android.util.Log;

/** Shows message notifications. Called from the embedded Python engine. */
public final class Notifier {

    // Channel settings are frozen by Android after creation, so a fix to sound/vibration
    // needs a new channel id. The old ids are removed in createChannels().
    public static final String CHANNEL_LOUD = "messages_v2";
    private static final String CHANNEL_QUIET = "messages_quiet_v2";
    private static final String[] OLD_CHANNELS = {"messages", "messages_quiet"};
    private static final long[] VIBRATION_PATTERN = {0, 200, 100, 200};
    private static final String TAG = "TeleFoxNotifier";

    private Notifier() {}

    public static void createChannels(Context ctx) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = ctx.getSystemService(NotificationManager.class);
        for (String old : OLD_CHANNELS) nm.deleteNotificationChannel(old);

        AudioAttributes audio = new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_NOTIFICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build();
        NotificationChannel loud = new NotificationChannel(
                CHANNEL_LOUD, ctx.getString(R.string.channel_messages), NotificationManager.IMPORTANCE_HIGH);
        loud.setSound(Settings.System.DEFAULT_NOTIFICATION_URI, audio);
        loud.enableVibration(true);
        loud.setVibrationPattern(VIBRATION_PATTERN);
        loud.enableLights(true);
        NotificationChannel quiet = new NotificationChannel(
                CHANNEL_QUIET, ctx.getString(R.string.channel_messages_quiet), NotificationManager.IMPORTANCE_LOW);
        quiet.setSound(null, null);
        nm.createNotificationChannel(loud);
        nm.createNotificationChannel(quiet);
    }

    /** True when Android itself will not make a sound for this channel (user muted it, DND, ...). */
    private static boolean channelIsSilent(NotificationManager nm) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return false;
        NotificationChannel ch = nm.getNotificationChannel(CHANNEL_LOUD);
        return ch == null || ch.getImportance() < NotificationManager.IMPORTANCE_DEFAULT || ch.getSound() == null;
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
            int defaults = 0;
            if (sound) defaults |= Notification.DEFAULT_SOUND;
            if (vibrate) defaults |= Notification.DEFAULT_VIBRATE;
            b.setDefaults(defaults).setPriority(Notification.PRIORITY_HIGH);
        }
        nm.notify(id, b.build());

        // If the channel was silenced in system settings, log it so it is easy to diagnose.
        if (loud && sound && channelIsSilent(nm)) {
            Log.w(TAG, "Notification channel is silent in system settings; no sound will play");
        }
    }
}
