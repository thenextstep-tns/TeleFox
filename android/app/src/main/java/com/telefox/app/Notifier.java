package com.telefox.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

/** Shows message notifications. Called from the embedded Python engine. */
public final class Notifier {

    private static final String CHANNEL_LOUD = "messages";
    private static final String CHANNEL_QUIET = "messages_quiet";

    private Notifier() {}

    public static void createChannels(Context ctx) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = ctx.getSystemService(NotificationManager.class);
        NotificationChannel loud = new NotificationChannel(
                CHANNEL_LOUD, ctx.getString(R.string.channel_messages), NotificationManager.IMPORTANCE_HIGH);
        loud.enableVibration(true);
        NotificationChannel quiet = new NotificationChannel(
                CHANNEL_QUIET, ctx.getString(R.string.channel_messages_quiet), NotificationManager.IMPORTANCE_LOW);
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
                .setGroup("telefox_messages");
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            int defaults = 0;
            if (sound) defaults |= Notification.DEFAULT_SOUND;
            if (vibrate) defaults |= Notification.DEFAULT_VIBRATE;
            b.setDefaults(defaults).setPriority(Notification.PRIORITY_HIGH);
        }
        nm.notify(id, b.build());
    }
}
