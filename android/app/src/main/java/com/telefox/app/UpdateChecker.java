package com.telefox.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.Settings;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Checks the latest GitHub release of the (public) repository and installs its APK.
 */
final class UpdateChecker {

    private static final long CHECK_INTERVAL_MS = 6L * 60 * 60 * 1000;
    private static final int CONNECT_TIMEOUT_MS = 10_000;
    private static final int READ_TIMEOUT_MS = 30_000;
    private static final int COPY_BUFFER_BYTES = 64 * 1024;
    private static final String PREFS = "telefox_prefs";
    private static final String PREF_LAST_CHECK = "last_update_check";
    private static final String API = "https://api.github.com/repos/";

    private UpdateChecker() {}

    /** Called on launch: silent unless a newer version exists. */
    static void checkIfDue(Activity activity) {
        SharedPreferences prefs = activity.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        long now = System.currentTimeMillis();
        if (now - prefs.getLong(PREF_LAST_CHECK, 0) < CHECK_INTERVAL_MS) return;
        prefs.edit().putLong(PREF_LAST_CHECK, now).apply();
        run(activity, false);
    }

    /** Called from the "check for updates" button: always reports the outcome. */
    static void checkNow(Activity activity) {
        run(activity, true);
    }

    private static void run(Activity activity, boolean manual) {
        String repo = activity.getString(R.string.github_repo);
        new Thread(() -> {
            try {
                HttpURLConnection c = open(API + repo + "/releases/latest", "application/vnd.github+json");
                if (c.getResponseCode() != 200) {
                    if (manual) toast(activity, R.string.update_failed);
                    return;
                }
                JSONObject release = new JSONObject(read(c.getInputStream()));
                String latest = release.optString("tag_name", "");
                JSONObject apk = findApk(release.optJSONArray("assets"));
                if (apk == null || !isNewer(latest, BuildConfig.VERSION_NAME)) {
                    if (manual) toast(activity, R.string.update_none);
                    return;
                }
                String notes = release.optString("body", "");
                String url = apk.getString("browser_download_url");
                activity.runOnUiThread(() -> promptInstall(activity, latest, notes, url));
            } catch (Exception e) {
                if (manual) toast(activity, R.string.update_failed);
            }
        }, "TeleFox-UpdateCheck").start();
    }

    private static JSONObject findApk(JSONArray assets) throws Exception {
        for (int i = 0; assets != null && i < assets.length(); i++) {
            JSONObject a = assets.getJSONObject(i);
            if (a.optString("name").endsWith(".apk")) return a;
        }
        return null;
    }

    private static HttpURLConnection open(String url, String accept) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(CONNECT_TIMEOUT_MS);
        c.setReadTimeout(READ_TIMEOUT_MS);
        c.setRequestProperty("Accept", accept);
        return c;
    }

    private static String read(InputStream in) throws Exception {
        StringBuilder sb = new StringBuilder();
        try (BufferedReader r = new BufferedReader(new InputStreamReader(in))) {
            String line;
            while ((line = r.readLine()) != null) sb.append(line);
        }
        return sb.toString();
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
                .setPositiveButton(R.string.update_install, (d, w) -> downloadAndInstall(activity, version, apkUrl))
                .setNegativeButton(R.string.update_later, null)
                .show();
    }

    private static void downloadAndInstall(Activity activity, String version, String apkUrl) {
        File dir = activity.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
        File apk = new File(dir, "TeleFox-" + version + ".apk");

        // Installing needs the one-time "install unknown apps" switch for this app.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                && !activity.getPackageManager().canRequestPackageInstalls()) {
            Toast.makeText(activity, R.string.update_allow_install, Toast.LENGTH_LONG).show();
            activity.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + activity.getPackageName())));
            return;
        }
        if (apk.exists() && apk.length() > 0) {
            install(activity, apk);
            return;
        }

        Toast.makeText(activity, R.string.update_downloading, Toast.LENGTH_LONG).show();
        new Thread(() -> {
            File part = new File(dir, apk.getName() + ".part");
            try {
                purgeOldDownloads(dir);
                HttpURLConnection c = open(apkUrl, "application/octet-stream");
                if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode());
                try (InputStream in = c.getInputStream(); OutputStream out = new FileOutputStream(part)) {
                    byte[] buf = new byte[COPY_BUFFER_BYTES];
                    int n;
                    while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
                }
                if (!part.renameTo(apk)) throw new Exception("rename failed");
                activity.runOnUiThread(() -> install(activity, apk));
            } catch (Exception e) {
                part.delete();
                toast(activity, R.string.update_failed);
            }
        }, "TeleFox-UpdateDownload").start();
    }

    private static void purgeOldDownloads(File dir) {
        File[] files = dir.listFiles();
        if (files == null) return;
        for (File f : files) f.delete();
    }

    private static void install(Activity activity, File apk) {
        try {
            Uri uri = FileProvider.getUriForFile(activity, activity.getPackageName() + ".files", apk);
            activity.startActivity(new Intent(Intent.ACTION_VIEW)
                    .setDataAndType(uri, "application/vnd.android.package-archive")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION));
        } catch (Exception e) {
            Toast.makeText(activity, R.string.update_failed, Toast.LENGTH_LONG).show();
        }
    }
}
