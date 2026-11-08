package app.foxygram.data

import android.content.Context
import android.util.Base64
import app.foxygram.ui.theme.ThemeMode
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONObject

data class PairingCode(val serverUrl: String, val token: String, val apiId: Int, val apiHash: String) {
    companion object {
        private const val PREFIX = "foxygram://pair?d="

        fun parse(raw: String): PairingCode? = runCatching {
            val text = raw.trim()
            if (!text.startsWith(PREFIX)) return null
            val json = JSONObject(String(Base64.decode(text.removePrefix(PREFIX), Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)))
            PairingCode(json.getString("u").trimEnd('/'), json.getString("t"), json.getInt("i"), json.getString("h"))
                .takeIf { it.apiId != 0 && it.apiHash.isNotBlank() }
        }.getOrNull()
    }
}

/** Everything lives in the app's private storage; none of it is in the APK or the repository. */
class Settings(context: Context) {
    private val prefs = context.getSharedPreferences("foxygram", Context.MODE_PRIVATE)

    private val _theme = MutableStateFlow(
        runCatching { ThemeMode.valueOf(prefs.getString(KEY_THEME, null) ?: "") }.getOrDefault(ThemeMode.Dark)
    )
    val theme: StateFlow<ThemeMode> = _theme.asStateFlow()

    private val _paired = MutableStateFlow(apiId != 0)
    val paired: StateFlow<Boolean> = _paired.asStateFlow()

    val apiId: Int get() = prefs.getInt(KEY_API_ID, 0)
    val apiHash: String get() = prefs.getString(KEY_API_HASH, "").orEmpty()
    val serverUrl: String get() = prefs.getString(KEY_SERVER_URL, "").orEmpty()
    val serverToken: String get() = prefs.getString(KEY_SERVER_TOKEN, "").orEmpty()

    var keepConnected: Boolean
        get() = prefs.getBoolean(KEY_KEEP_CONNECTED, true)
        set(value) = prefs.edit().putBoolean(KEY_KEEP_CONNECTED, value).apply()

    var lastUpdateCheck: Long
        get() = prefs.getLong(KEY_LAST_UPDATE_CHECK, 0)
        set(value) = prefs.edit().putLong(KEY_LAST_UPDATE_CHECK, value).apply()

    fun setTheme(mode: ThemeMode) {
        prefs.edit().putString(KEY_THEME, mode.name).apply()
        _theme.value = mode
    }

    fun applyPairing(code: PairingCode) {
        prefs.edit()
            .putInt(KEY_API_ID, code.apiId)
            .putString(KEY_API_HASH, code.apiHash)
            .putString(KEY_SERVER_URL, code.serverUrl)
            .putString(KEY_SERVER_TOKEN, code.token)
            .commit()
        _paired.value = true
    }

    private companion object {
        const val KEY_THEME = "theme"
        const val KEY_API_ID = "api_id"
        const val KEY_API_HASH = "api_hash"
        const val KEY_SERVER_URL = "server_url"
        const val KEY_SERVER_TOKEN = "server_token"
        const val KEY_KEEP_CONNECTED = "keep_connected"
        const val KEY_LAST_UPDATE_CHECK = "last_update_check"
    }
}
