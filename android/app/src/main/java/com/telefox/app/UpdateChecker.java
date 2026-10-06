package com.telefox.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.widget.Toast;


import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
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

    /**
     * Hands the APK link to the browser. The browser downloads it and Android's own installer
     * takes over, so the app never needs the "install unknown apps" permission, which Play Protect
     * treats as a strong malware signal.
     */
    private static void openDownload(Activity activity, String apkUrl) {
        try {
            activity.startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(apkUrl)));
        } catch (Exception e) {
            Toast.makeText(activity, R.string.update_failed, Toast.LENGTH_LONG).show();
        }
    }

    private static void promptInstall(Activity activity, String version, String notes, String apkUrl) {
        if (activity.isFinishing() || activity.isDestroyed()) return;
        new AlertDialog.Builder(activity)
                .setTitle(activity.getString(R.string.update_title, version))
                .setMessage(notes.isEmpty() ? activity.getString(R.string.update_message) : notes)
                .setPositiveButton(R.string.update_install, (d, w) -> openDownload(activity, apkUrl))
                .setNegativeButton(R.string.update_later, null)
                .show();
    }
}
