package com.telefox.app;

import android.Manifest;
import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.os.Vibrator;
import android.provider.Settings;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.net.HttpURLConnection;
import java.net.URL;

public class MainActivity extends Activity {

    public static final String EXTRA_CHAT_ID = "chat_id";
    private static final String SERVER_URL = "http://127.0.0.1:5050" /* keep in sync with config.WEB_PORT */;
    private static final int POLL_INTERVAL_MS = 500;
    private static final int POLL_ATTEMPTS = 60; // 30 s in total
    private static final int PROBE_TIMEOUT_MS = 600;
    private static final int RELOAD_DELAY_MS = 2000;
    private static final int NOTIFICATION_PERMISSION_REQUEST = 101;
    private static final int DEFAULT_VIBRATION_MS = 100;
    private static final int ERROR_BOX_HEIGHT_DP = 220;

    private static final String PREF_DARK = "dark_theme";
    private static final int DARK_SURFACE = 0xFF161B22, DARK_BG = 0xFF0D1117;
    private static final int LIGHT_SURFACE = 0xFFF6F8FA, LIGHT_BG = 0xFFFFFFFF;

    private FrameLayout root;
    private WebView webView;
    private LinearLayout splash;
    private ProgressBar spinner;
    private TextView splashTitle;
    private TextView splashStatus;
    private LinearLayout errorBox;
    private TextView errorLog;

    private final Handler main = new Handler(Looper.getMainLooper());
    private volatile boolean serverReady = false;
    private volatile boolean polling = false;
    private String pendingChatId;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        pendingChatId = getIntent().getStringExtra(EXTRA_CHAT_ID);

        buildUi();
        applySystemBars(getSharedPreferences("telefox_prefs", MODE_PRIVATE).getBoolean(PREF_DARK, true));
        initWebView();
        requestPermissions();
        startEngine();
        startServerPolling();
        UpdateChecker.checkIfDue(this, false);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        String chatId = intent.getStringExtra(EXTRA_CHAT_ID);
        if (chatId != null) {
            pendingChatId = chatId;
            openPendingChat();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        webView.onResume();
        // The page refreshes itself on visibilitychange; this just resumes JS timers.
        webView.resumeTimers();
    }

    @Override
    protected void onPause() {
        // Pausing the WebView stops its timers and SSE traffic while the screen is off.
        // Python keeps receiving messages in the foreground service.
        webView.onPause();
        webView.pauseTimers();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        polling = false;
        main.removeCallbacksAndMessages(null);
        webView.destroy();
        super.onDestroy();
    }

    /** Keeps status/navigation bars and the window background in step with the page theme. */
    private void applySystemBars(boolean dark) {
        int surface = dark ? DARK_SURFACE : LIGHT_SURFACE;
        int bg = dark ? DARK_BG : LIGHT_BG;
        getWindow().setStatusBarColor(surface);
        getWindow().setNavigationBarColor(bg);
        View decor = getWindow().getDecorView();
        int flags = decor.getSystemUiVisibility();
        int lightBars = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
        decor.setSystemUiVisibility(dark ? flags & ~lightBars : flags | lightBars);
        root.setBackgroundColor(bg);
        webView.setBackgroundColor(bg);
        splashStatus.setTextColor(dark ? 0xFF8B949E : 0xFF59636E);
        splashTitle.setTextColor(dark ? 0xFFE6EDF3 : 0xFF1F2328);
    }

    private int dp(int v) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, getResources().getDisplayMetrics());
    }

    private TextView label(String text, int sp, int color) {
        TextView t = new TextView(this);
        t.setText(text);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(color);
        t.setGravity(Gravity.CENTER);
        return t;
    }

    private void buildUi() {
        root = new FrameLayout(this);
        root.setBackgroundColor(getColor(R.color.bg));

        webView = new WebView(this);
        webView.setBackgroundColor(getColor(R.color.bg));
        webView.setVisibility(View.GONE);
        root.addView(webView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        splash = new LinearLayout(this);
        splash.setOrientation(LinearLayout.VERTICAL);
        splash.setGravity(Gravity.CENTER);
        splash.setPadding(dp(24), dp(24), dp(24), dp(24));

        splashTitle = label(getString(R.string.app_name), 24, getColor(R.color.text));
        splashTitle.setTypeface(null, Typeface.BOLD);
        spinner = new ProgressBar(this);
        splashStatus = label(getString(R.string.starting), 14, getColor(R.color.text_secondary));
        splashStatus.setPadding(0, dp(12), 0, 0);

        errorBox = new LinearLayout(this);
        errorBox.setOrientation(LinearLayout.VERTICAL);
        errorBox.setVisibility(View.GONE);

        errorLog = new TextView(this);
        errorLog.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11);
        errorLog.setTextColor(getColor(R.color.error));
        errorLog.setTypeface(Typeface.MONOSPACE);
        errorLog.setTextIsSelectable(true);
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(getColor(R.color.surface));
        scroll.setPadding(dp(12), dp(12), dp(12), dp(12));
        scroll.addView(errorLog);
        errorBox.addView(scroll, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(ERROR_BOX_HEIGHT_DP)));

        LinearLayout buttons = new LinearLayout(this);
        buttons.setGravity(Gravity.CENTER);
        buttons.setPadding(0, dp(12), 0, 0);
        Button copy = new Button(this);
        copy.setText(R.string.copy_log);
        copy.setOnClickListener(v -> {
            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            cm.setPrimaryClip(ClipData.newPlainText("TeleFox", errorLog.getText()));
            Toast.makeText(this, R.string.log_copied, Toast.LENGTH_SHORT).show();
        });
        Button restart = new Button(this);
        restart.setText(R.string.restart);
        restart.setOnClickListener(v -> {
            errorBox.setVisibility(View.GONE);
            spinner.setVisibility(View.VISIBLE);
            splashStatus.setText(R.string.starting);
            splashStatus.setTextColor(getColor(R.color.text_secondary));
            startEngine();
            startServerPolling();
        });
        buttons.addView(copy);
        buttons.addView(restart);
        errorBox.addView(buttons);

        splash.addView(splashTitle);
        splash.addView(spinner);
        splash.addView(splashStatus);
        splash.addView(errorBox);
        root.addView(splash, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        // Keep content clear of the status bar, navigation bar and keyboard.
        root.setFitsSystemWindows(true);
        setContentView(root);
    }

    private void initWebView() {
        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setAllowFileAccess(false);
        ws.setAllowContentAccess(false);
        ws.setMediaPlaybackRequiresUserGesture(true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    main.postDelayed(() -> { if (!isDestroyed()) view.loadUrl(SERVER_URL); }, RELOAD_DELAY_MS);
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                if (url != null && url.startsWith(SERVER_URL)) {
                    splash.setVisibility(View.GONE);
                    webView.setVisibility(View.VISIBLE);
                    openPendingChat();
                }
            }
        });
        webView.addJavascriptInterface(new Bridge(), "TeleFoxNative");
    }

    private void openPendingChat() {
        if (pendingChatId == null || webView.getVisibility() != View.VISIBLE) return;
        String id = pendingChatId.replaceAll("[^0-9-]", "");
        pendingChatId = null;
        webView.evaluateJavascript("if (window.openChatById) openChatById('" + id + "');", null);
    }

    private void startEngine() {
        Intent i = new Intent(this, TeleFoxService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(i);
        else startService(i);
    }

    private void startServerPolling() {
        if (polling) return;
        polling = true;
        serverReady = false;
        new Thread(() -> {
            for (int attempt = 1; attempt <= POLL_ATTEMPTS && polling && !isDestroyed(); attempt++) {
                String err = TeleFoxService.lastError;
                if (err != null) {
                    polling = false;
                    main.post(() -> showError(err));
                    return;
                }
                try {
                    HttpURLConnection c = (HttpURLConnection) new URL(SERVER_URL + "/api/status").openConnection();
                    c.setConnectTimeout(PROBE_TIMEOUT_MS);
                    c.setReadTimeout(PROBE_TIMEOUT_MS);
                    int code = c.getResponseCode();
                    c.disconnect();
                    if (code == 200) {
                        serverReady = true;
                        polling = false;
                        main.post(() -> webView.loadUrl(SERVER_URL));
                        return;
                    }
                } catch (Exception ignored) {
                    // server still starting
                }
                try { Thread.sleep(POLL_INTERVAL_MS); } catch (InterruptedException e) { return; }
            }
            polling = false;
            if (!serverReady && !isDestroyed()) {
                main.post(() -> showError("Server did not respond in " + (POLL_ATTEMPTS * POLL_INTERVAL_MS / 1000) + " s."));
            }
        }, "TeleFox-Poller").start();
    }

    private void showError(String msg) {
        spinner.setVisibility(View.GONE);
        splashStatus.setText(R.string.start_failed);
        splashStatus.setTextColor(getColor(R.color.error));
        errorLog.setText(msg);
        errorBox.setVisibility(View.VISIBLE);
    }

    private void requestPermissions() {
        SharedPreferences prefs = getSharedPreferences("telefox_prefs", MODE_PRIVATE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, NOTIFICATION_PERMISSION_REQUEST);
        }
        // Ask for the battery exemption only once, so it doesn't nag on every launch.
        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (pm != null && !pm.isIgnoringBatteryOptimizations(getPackageName())
                && !prefs.getBoolean("asked_battery", false)) {
            prefs.edit().putBoolean("asked_battery", true).apply();
            try {
                startActivity(new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                        Uri.parse("package:" + getPackageName())));
            } catch (Exception ignored) {}
        }
    }

    @Override
    public void onBackPressed() {
        if (webView.getVisibility() != View.VISIBLE) {
            super.onBackPressed();
            return;
        }
        // The page closes its own menu/chat; if it has nothing to close, leave the app.
        webView.evaluateJavascript(
                "(window.handleBack ? handleBack() : false)",
                v -> { if (!"true".equals(v)) runOnUiThread(() -> MainActivity.super.onBackPressed()); });
    }

    public class Bridge {
        @JavascriptInterface
        public void vibrate(int ms) {
            Vibrator v = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
            if (v != null) v.vibrate(ms > 0 ? ms : DEFAULT_VIBRATION_MS);
        }

        @JavascriptInterface
        public void setTheme(boolean dark) {
            getSharedPreferences("telefox_prefs", MODE_PRIVATE).edit().putBoolean(PREF_DARK, dark).apply();
            runOnUiThread(() -> applySystemBars(dark));
        }

        @JavascriptInterface
        public void checkForUpdates() {
            runOnUiThread(() -> UpdateChecker.checkIfDue(MainActivity.this, true));
        }

        @JavascriptInterface
        public void openNotificationSettings() {
            try {
                Intent i = new Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS)
                        .putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName())
                        .putExtra(Settings.EXTRA_CHANNEL_ID, Notifier.CHANNEL_LOUD);
                startActivity(i);
            } catch (Exception e) {
                openAppSettings();
            }
        }

        @JavascriptInterface
        public void openAppSettings() {
            try {
                startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                        Uri.parse("package:" + getPackageName())));
            } catch (Exception ignored) {}
        }
    }
}
