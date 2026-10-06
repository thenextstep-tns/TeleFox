package com.telefox.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

/**
 * Keeps the embedded Python engine (Telethon + local web server) alive.
 * No wake lock: Telegram's socket wakes the CPU when data arrives, and the
 * foreground service plus battery-optimisation exemption keep the process alive.
 */
public class TeleFoxService extends Service {

    private static final String CHANNEL_ID = "service";
    private static final int NOTIFICATION_ID = 1001;
    private static final String TAG = "TeleFoxService";

    public static volatile android.content.Context appContext;
    public static volatile String lastError = null;

    private static Thread pythonThread = null;

    @Override
    public void onCreate() {
        super.onCreate();
        appContext = getApplicationContext();
        Notifier.createChannels(this);
        startInForeground();
    }

    private void startInForeground() {
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel ch = new NotificationChannel(
                    CHANNEL_ID, getString(R.string.channel_service), NotificationManager.IMPORTANCE_MIN);
            ch.setShowBadge(false);
            nm.createNotificationChannel(ch);
        }

        PendingIntent pi = PendingIntent.getActivity(
                this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this).setPriority(Notification.PRIORITY_MIN);
        Notification n = b.setContentTitle(getString(R.string.service_title))
                .setContentText(getString(R.string.service_text))
                .setSmallIcon(R.drawable.ic_notification)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        } else {
            startForeground(NOTIFICATION_ID, n);
        }
    }

    private static synchronized void startPythonEngine(android.content.Context ctx) {
        if (pythonThread != null && pythonThread.isAlive()) return;

        pythonThread = new Thread(() -> {
            try {
                lastError = null;
                if (!Python.isStarted()) {
                    Python.start(new AndroidPlatform(ctx));
                }
                Python py = Python.getInstance();
                String dataDir = ctx.getFilesDir().getAbsolutePath();
                py.getModule("os").get("environ").callAttr("__setitem__", "TELEFOX_DATA_DIR", dataDir);
                py.getModule("main").callAttr("run_embedded", dataDir);
            } catch (Throwable t) {
                java.io.StringWriter sw = new java.io.StringWriter();
                t.printStackTrace(new java.io.PrintWriter(sw));
                lastError = sw.toString();
                Log.e(TAG, "Python engine crashed:\n" + lastError);
            }
        }, "TeleFox-Python");
        pythonThread.start();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startPythonEngine(getApplicationContext());
        return START_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
