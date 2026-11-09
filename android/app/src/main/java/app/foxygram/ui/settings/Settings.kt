package app.foxygram.ui.settings

import android.app.Activity
import android.content.Intent
import android.media.RingtoneManager
import android.net.Uri
import android.os.PowerManager
import android.provider.Settings
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.foxygram.BuildConfig
import app.foxygram.data.AiChat
import app.foxygram.data.ServerHealth
import app.foxygram.notify.AlertMode
import app.foxygram.notify.ConnectionService
import app.foxygram.td.Telegram
import app.foxygram.ui.cases.EmptyNote
import app.foxygram.ui.cases.ScreenBar
import app.foxygram.ui.theme.Foxy
import app.foxygram.ui.theme.ThemeMode
import app.foxygram.update.AppUpdater
import app.foxygram.update.Release
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(telegram: Telegram, onBack: () -> Unit) {
    val colors = Foxy.colors
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val theme by telegram.settings.theme.collectAsState()
    var keep by remember { mutableStateOf(telegram.settings.keepConnected) }
    var health by remember { mutableStateOf<ServerHealth?>(null) }
    var diagnostics by remember { mutableStateOf(telegram.alerts.diagnostics()) }
    var update by remember { mutableStateOf<Release?>(null) }
    var progress by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        if (telegram.serverApi.configured) health = runCatching { telegram.serverApi.health() }.getOrNull()
    }

    Column(Modifier.fillMaxSize().background(colors.background)) {
        ScreenBar("Настройки", onBack)
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).windowInsetsPadding(WindowInsets.navigationBars)) {
            Section("Оформление")
            listOf(ThemeMode.Dark to "Тёмная", ThemeMode.Light to "Светлая", ThemeMode.System to "Как в системе").forEach { (mode, label) ->
                Row(Modifier.fillMaxWidth().clickable { telegram.settings.setTheme(mode) }.padding(horizontal = 16.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(theme == mode, { telegram.settings.setTheme(mode) })
                    Text(label, color = colors.text, fontSize = 16.sp)
                }
            }

            Section("Уведомления")
            Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Получать сообщения в фоне", color = colors.text, fontSize = 16.sp)
                    Text("Держит одно соединение с Telegram, пока приложение закрыто", color = colors.textSecondary, fontSize = 13.sp)
                }
                Switch(keep, { value ->
                    keep = value
                    telegram.settings.keepConnected = value
                    if (value) ConnectionService.start(context) else ConnectionService.stop(context)
                })
            }
            Row1("Разрешить работу в фоне", "Системный экран настроек батареи для FoxyGram") {
                val power = context.getSystemService(PowerManager::class.java)
                val intent = if (power.isIgnoringBatteryOptimizations(context.packageName)) {
                    Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}"))
                } else {
                    Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${context.packageName}"))
                }
                runCatching { context.startActivity(intent) }
            }
            Text(diagnostics, color = colors.textSecondary, fontSize = 13.sp, modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp).clickable { diagnostics = telegram.alerts.diagnostics() })

            FolderAlerts(telegram)

            Section("Сервер")
            val state = health
            Text(
                when {
                    !telegram.serverApi.configured -> "Сервер не подключён"
                    state == null -> "Компьютер с сервером недоступен"
                    else -> "Claude: ${claudeState(state.claudeState)}. Вызовов за сутки: ${state.callsToday}. В очереди: ${state.pending}."
                },
                color = colors.textSecondary, fontSize = 14.sp, modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp),
            )
            if (state != null && state.claudeDetail.isNotBlank()) {
                Text(state.claudeDetail, color = colors.warning, fontSize = 14.sp, modifier = Modifier.padding(horizontal = 16.dp, vertical = 2.dp))
            }

            Section("О приложении")
            Row1("Проверить обновления", "Версия ${BuildConfig.VERSION_NAME}") {
                scope.launch {
                    val found = AppUpdater.latest()
                    if (found == null) Toast.makeText(context, "Установлена последняя версия", Toast.LENGTH_SHORT).show() else update = found
                }
            }
            Row1("Выйти из аккаунта", "") { scope.launch { runCatching { telegram.logOut() } } }
            Spacer(Modifier.height(24.dp))
        }
    }

    update?.let { release ->
        AlertDialog(
            onDismissRequest = { update = null },
            title = { Text("Версия ${release.version}") },
            text = { Text(progress ?: release.notes.ifBlank { "Вышла новая версия FoxyGram." }) },
            confirmButton = {
                TextButton({
                    progress = "Загрузка…"
                    scope.launch {
                        runCatching { AppUpdater.install(context, release) { progress = "Загрузка $it%" } }
                            .onFailure { progress = "Не удалось: ${it.message}" }
                    }
                }) { Text("Обновить") }
            },
            dismissButton = { TextButton({ update = null }) { Text("Позже") } },
            containerColor = colors.surface,
        )
    }
}

private data class FolderAlert(val key: String, val title: String, val mode: AlertMode, val sound: String?)

private fun modeLabel(mode: AlertMode) = when (mode) {
    AlertMode.All -> "Все сообщения"
    AlertMode.Mentions -> "Только упоминания"
    AlertMode.Off -> "Выключены"
}

/** Each folder, and the archive, can alert differently. */
@Composable
private fun FolderAlerts(telegram: Telegram) {
    val colors = Foxy.colors
    val settings = telegram.settings
    val folders by telegram.folders.collectAsState()
    var revision by remember { mutableStateOf(0) }
    var editing by remember { mutableStateOf<String?>(null) }
    val rows = remember(folders, revision) {
        telegram.alertFolders(folders).map { (key, title) -> FolderAlert(key, title, settings.alertMode(key), settings.alertSound(key)) }
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val key = editing
        if (key != null && result.resultCode == Activity.RESULT_OK) {
            @Suppress("DEPRECATION")
            val picked = result.data?.getParcelableExtra<Uri>(RingtoneManager.EXTRA_RINGTONE_PICKED_URI)
            settings.setAlertSound(key, picked?.toString())
            revision++
        }
    }

    Section("Уведомления по папкам")
    Text("Если чат в нескольких папках, действует самая громкая настройка.", color = colors.textSecondary, fontSize = 13.sp, modifier = Modifier.padding(horizontal = 16.dp, vertical = 2.dp))
    rows.forEach { row ->
        Row1(row.title, modeLabel(row.mode) + if (row.sound != null) " · свой звук" else "") { editing = row.key }
    }

    rows.firstOrNull { it.key == editing }?.let { row ->
        fun choose(mode: AlertMode) {
            settings.setAlertMode(row.key, mode)
            revision++
        }
        AlertDialog(
            onDismissRequest = { editing = null },
            title = { Text(row.title) },
            text = {
                Column {
                    listOf(AlertMode.All, AlertMode.Mentions, AlertMode.Off).forEach { mode ->
                        Row(Modifier.fillMaxWidth().clickable { choose(mode) }.padding(vertical = 2.dp), verticalAlignment = Alignment.CenterVertically) {
                            RadioButton(row.mode == mode, { choose(mode) })
                            Text(modeLabel(mode), color = colors.text, fontSize = 16.sp)
                        }
                    }
                    TextButton({
                        runCatching {
                            picker.launch(
                                Intent(RingtoneManager.ACTION_RINGTONE_PICKER)
                                    .putExtra(RingtoneManager.EXTRA_RINGTONE_TYPE, RingtoneManager.TYPE_NOTIFICATION)
                                    .putExtra(RingtoneManager.EXTRA_RINGTONE_SHOW_DEFAULT, false)
                                    .putExtra(RingtoneManager.EXTRA_RINGTONE_SHOW_SILENT, false)
                                    .putExtra(RingtoneManager.EXTRA_RINGTONE_EXISTING_URI, row.sound?.let { Uri.parse(it) })
                            )
                        }
                    }) { Text("Выбрать звук") }
                    if (row.sound != null) {
                        TextButton({
                            settings.setAlertSound(row.key, null)
                            revision++
                        }) { Text("Вернуть стандартный звук") }
                    }
                }
            },
            confirmButton = { TextButton({ editing = null }) { Text("Готово") } },
            containerColor = colors.surface,
        )
    }
}

private fun claudeState(state: String) = when (state) {
    "ok" -> "работает"
    "quota" -> "лимит исчерпан"
    "capped" -> "пауза"
    "login_needed" -> "нужен вход"
    "missing" -> "не установлен"
    else -> state
}

@Composable
private fun Section(title: String) {
    Text(title, color = Foxy.colors.accent, fontSize = 14.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(start = 16.dp, top = 20.dp, bottom = 6.dp))
}

@Composable
private fun Row1(title: String, subtitle: String, onClick: () -> Unit) {
    val colors = Foxy.colors
    Column(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 16.dp, vertical = 12.dp)) {
        Text(title, color = colors.text, fontSize = 16.sp)
        if (subtitle.isNotBlank()) Text(subtitle, color = colors.textSecondary, fontSize = 13.sp)
    }
}

/** You decide which chats are stored on your computer and analysed. Nothing is selected by default. */
@Composable
fun AiChatsScreen(telegram: Telegram, onBack: () -> Unit) {
    val colors = Foxy.colors
    val scope = rememberCoroutineScope()
    var chats by remember { mutableStateOf<List<AiChat>?>(null) }
    var failed by remember { mutableStateOf(false) }
    var query by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        if (!telegram.serverApi.configured) {
            failed = true
            return@LaunchedEffect
        }
        runCatching { telegram.serverApi.chats() }.onSuccess { chats = it }.onFailure { failed = true }
    }

    Column(Modifier.fillMaxSize().background(colors.background)) {
        ScreenBar("Чаты для Claude", onBack)
        val list = chats
        if (failed) {
            EmptyNote("Компьютер с сервером сейчас недоступен.")
            return@Column
        }
        Text("Только отмеченные чаты сохраняются на вашем компьютере и отправляются в Claude.", color = colors.textSecondary, fontSize = 13.sp, modifier = Modifier.padding(16.dp))
        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp)) {
            BasicTextField(
                query, { query = it },
                singleLine = true,
                textStyle = TextStyle(color = colors.text, fontSize = 16.sp),
                cursorBrush = SolidColor(colors.accent),
                modifier = Modifier.fillMaxWidth(),
                decorationBox = { inner ->
                    if (query.isEmpty()) Text("Поиск чата", color = colors.textSecondary, fontSize = 16.sp)
                    inner()
                },
            )
        }
        HorizontalDivider(color = colors.border, thickness = 0.5.dp)
        if (list != null) {
            val shown = list.filter { it.title.contains(query, ignoreCase = true) }
            LazyColumn(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.navigationBars)) {
                items(shown, key = { it.chatId }) { chat ->
                    Row(
                        Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(chat.title.ifBlank { "Без названия" }, color = colors.text, fontSize = 16.sp, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                        Spacer(Modifier.width(12.dp))
                        Switch(chat.enabled, { value ->
                            chats = chats?.map { if (it.chatId == chat.chatId) it.copy(enabled = value) else it }
                            scope.launch {
                                runCatching { telegram.serverApi.setAiEnabled(chat.chatId, value) }
                                telegram.applyLabel(chat.chatId) { it.copy(aiEnabled = value) }
                            }
                        })
                    }
                }
            }
        }
    }
}
