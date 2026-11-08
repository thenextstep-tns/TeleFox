package app.foxygram

import android.Manifest
import android.app.Application
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.graphics.toArgb
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ProcessLifecycleOwner
import app.foxygram.data.PairingCode
import app.foxygram.notify.EXTRA_CHAT_ID
import app.foxygram.td.Telegram
import app.foxygram.ui.FoxyRoot
import app.foxygram.ui.theme.DarkColors
import app.foxygram.ui.theme.LightColors
import app.foxygram.ui.theme.ThemeMode
import kotlinx.coroutines.flow.MutableStateFlow

class FoxyApp : Application() {
    override fun onCreate() {
        super.onCreate()
        val telegram = Telegram.get(this)
        if (telegram.settings.apiId != 0) telegram.start()
        ProcessLifecycleOwner.get().lifecycle.addObserver(object : DefaultLifecycleObserver {
            override fun onStart(owner: LifecycleOwner) = telegram.onVisibilityChanged(true)
            override fun onStop(owner: LifecycleOwner) = telegram.onVisibilityChanged(false)
        })
    }
}

class MainActivity : ComponentActivity() {
    private val openChat = MutableStateFlow<Long?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val telegram = Telegram.get(application)
        consume(intent, telegram)
        askForNotifications()
        setContent {
            val mode by telegram.settings.theme.collectAsState()
            val dark = when (mode) {
                ThemeMode.System -> isSystemInDarkTheme()
                ThemeMode.Dark -> true
                ThemeMode.Light -> false
            }
            LaunchedEffect(dark) {
                val bar = if (dark) DarkColors.surface.toArgb() else LightColors.surface.toArgb()
                enableEdgeToEdge(
                    statusBarStyle = if (dark) SystemBarStyle.dark(bar) else SystemBarStyle.light(bar, bar),
                    navigationBarStyle = if (dark) SystemBarStyle.dark(bar) else SystemBarStyle.light(bar, bar),
                )
            }
            FoxyRoot(telegram, openChat)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        consume(intent, Telegram.get(application))
    }

    private fun consume(intent: Intent?, telegram: Telegram) {
        intent?.getLongExtra(EXTRA_CHAT_ID, 0)?.takeIf { it != 0L }?.let { openChat.value = it }
        intent?.dataString?.let(PairingCode::parse)?.let {
            telegram.settings.applyPairing(it)
            telegram.start()
        }
    }

    private fun askForNotifications() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
    }
}
