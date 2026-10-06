package com.telefox.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

/** Checks the latest GitHub release and offers to install its APK. */
final class UpdateChecker {

    private static final long CHECK_INTERVAL_MS = 6L * 60 * 60 * 1000;

    private UpdateChecker() {}

    static void checkIfDue(Activity activity, boolean force) {
        String repo = activity.getString(R.string.github_repo);
        if (repo.isEmpty() || repo.startsWith("OWNER/")) return;

        SharedPreferences prefs = activity.getSharedPreferences("telefox_prefs", Context.MODE_PRIVATE);
        long now = System.currentTimeMillis();
        if (!force && now - prefs.getLong("last_update_check", 0) < CHECK_INTERVAL_MS) return;
        prefs.edit().putLong("last_update_check", now).apply();

        new Thread(() -> {
            try {
                HttpURLConnection c = (HttpURLConnection)
                        new URL("https://api.github.com/repos/" + repo + "/releases/latest").openConnection();
                c.setConnectTimeout(10000);
                c.setReadTimeout(10000);
                c.setRequestProperty("Accept", "application/vnd.github+json");
                if (c.getResponseCode() != 200) {
                    if (force) toast(activity, R.string.update_failed);
                    return;
                }
                StringBuilder sb = new StringBuilder();
                try (BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream()))) {
                    String line;
                    while ((line = r.readLine()) != null) sb.append(line);
                }
                JSONObject release = new JSONObject(sb.toString());
                String latest = release.optString("tag_name", "");
                String apkUrl = null;
                JSONArray assets = release.optJSONArray("assets");
                for (int i = 0; assets != null && i < assets.length(); i++) {
                    JSONObject a = assets.getJSONObject(i);
                    if (a.optString("name").endsWith(".apk")) {
                        apkUrl = a.getString("browser_download_url");
                        break;
                    }
                }
                if (apkUrl == null || !isNewer(latest, BuildConfig.VERSION_NAME)) {
                    if (force) toast(activity, R.string.update_none);
                    return;
                }
                final String url = apkUrl;
                final String notes = release.optString("body", "");
                activity.runOnUiThread(() -> promptInstall(activity, latest, notes, url));
            } catch (Exception e) {
                if (force) toast(activity, R.string.update_failed);
            }
        }, "TeleFox-UpdateCheck").start();
    }

    private static void toast(Activity a, int res) {
        a.runOnUiThread(() -> Toast.makeText(a, res, Toast.LENGTH_SHORT).show());
    }

    /** Compares dotted versions, ignoring a leading "v". */
    static boolean isNewer(String latest, String current) {
        int[] l = parse(latest), c = parse(current);
        for (int i = 0; i < Math.max(l.length, c.length); i++) {
            int a = i < l.length ? l[i] : 0, b = i < c.length ? c[i] : 0;
            if (a != b) return a > b;
        }
        return false;
    }

    private static int[] parse(String v) {
        String[] parts = v.replaceFirst("^[vV]", "").split("[^0-9]+");
        int[] out = new int[parts.length];
        for (int i = 0; i < parts.length; i++) {
            try { out[i] = Integer.parseInt(parts[i]); } catch (NumberFormatException ignored) {}
        }
        return out;
    }

    private static void promptInstall(Activity activity, String version, String notes, String apkUrl) {
        if (activity.isFinishing() || activity.isDestroyed()) return;
        new AlertDialog.Builder(activity)
                .setTitle(activity.getString(R.string.update_title, version))
                .setMessage(notes.isEmpty() ? activity.getString(R.string.update_message) : notes)
                .setPositiveButton(R.string.update_install, (d, w) -> download(activity, apkUrl, version))
                .setNegativeButton(R.string.update_later, null)
                .show();
    }

    private static void download(Context ctx, String apkUrl, String version) {
        DownloadManager dm = (DownloadManager) ctx.getSystemService(Context.DOWNLOAD_SERVICE);
        String name = "TeleFox-" + version + ".apk";
        File target = new File(ctx.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), name);
        if (target.exists()) target.delete();

        DownloadManager.Request req = new DownloadManager.Request(Uri.parse(apkUrl))
                .setTitle(name)
                .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                .setDestinationUri(Uri.fromFile(target));
        final long id = dm.enqueue(req);
        Toast.makeText(ctx, R.string.update_downloading, Toast.LENGTH_SHORT).show();

        BroadcastReceiver done = new BroadcastReceiver() {
            @Override public void onReceive(Context c, Intent i) {
                if (i.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1) != id) return;
                c.unregisterReceiver(this);
                Uri uri = FileProvider.getUriForFile(c, c.getPackageName() + ".files", target);
                Intent install = new Intent(Intent.ACTION_VIEW)
                        .setDataAndType(uri, "application/vnd.android.package-archive")
                        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                try { c.startActivity(install); }
                catch (Exception e) { Toast.makeText(c, R.string.update_failed, Toast.LENGTH_LONG).show(); }
            }
        };
        IntentFilter f = new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE);
        if (Build.VERSION.SDK_INT >= 33) ctx.registerReceiver(done, f, Context.RECEIVER_EXPORTED);
        else ctx.registerReceiver(done, f);
    }
}
