package app.foxygram.ui.chats

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.Archive
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.MarkChatRead
import androidx.compose.material.icons.filled.MarkChatUnread
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.NotificationsOff
import androidx.compose.material.icons.filled.PushPin
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material.icons.filled.Unarchive
import androidx.compose.material.icons.filled.WorkOutline
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDrawerState
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.foxygram.data.BrainChange
import app.foxygram.data.BrainJobs
import app.foxygram.data.ProjectInfo
import app.foxygram.data.ServerApi
import app.foxygram.model.ChatItem
import app.foxygram.model.FolderTab
import app.foxygram.td.ChatCommands
import app.foxygram.td.Telegram
import app.foxygram.ui.Route
import app.foxygram.ui.theme.Foxy
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private const val FOLDER_NAME_MAX = 12

@Composable
fun ChatsRoute(telegram: Telegram, navigate: (Route) -> Unit) {
    val chats by telegram.chats.collectAsState()
    val folders by telegram.folders.collectAsState()
    val selected by telegram.selectedFolder.collectAsState()
    val connection by telegram.connection.collectAsState()
    val drawer = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var sheetChat by remember { mutableStateOf<ChatItem?>(null) }
    var results by remember { mutableStateOf<List<ChatItem>?>(null) }
    val colors = Foxy.colors

    LaunchedEffect(Unit) { telegram.refreshLabels() }

    ModalNavigationDrawer(
        drawerState = drawer,
        drawerContent = {
            ModalDrawerSheet(drawerContainerColor = colors.surface) {
                Column(Modifier.windowInsetsPadding(WindowInsets.statusBars).padding(vertical = 8.dp)) {
                    Text("FoxyGram", color = colors.text, fontSize = 20.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(16.dp))
                    HorizontalDivider(color = colors.border, thickness = 0.5.dp)
                    DrawerItem(Icons.Filled.WorkOutline, "Дела") {
                        scope.launch { drawer.close() }
                        navigate(Route.Cases)
                    }
                    DrawerItem(Icons.Filled.SmartToy, "Чаты для Claude") {
                        scope.launch { drawer.close() }
                        navigate(Route.AiChats)
                    }
                    DrawerItem(Icons.Filled.Settings, "Настройки") {
                        scope.launch { drawer.close() }
                        navigate(Route.Settings)
                    }
                }
            }
        },
    ) {
        ChatListScreen(
            chats = chats,
            folders = folders,
            selectedFolder = selected,
            connectionLabel = connection,
            onFolder = telegram::selectFolder,
            onChat = { navigate(if (it.isForum) Route.Topics(it.id, it.title) else Route.Chat(it.id)) },
            onChatLongPress = { sheetChat = it },
            onMenu = { scope.launch { drawer.open() } },
            onNearEnd = { scope.launch { telegram.loadMore() } },
            onSearch = { query ->
                if (query.isBlank()) {
                    results = null
                } else {
                    scope.launch { results = runCatching { telegram.searchChats(query) }.getOrNull() }
                }
            },
            searchResults = results,
            onMarkFolderRead = { folder ->
                scope.launch {
                    runCatching { telegram.markFolderRead(folder) }
                        .onFailure { Toast.makeText(context, "Не удалось: ${it.message}", Toast.LENGTH_LONG).show() }
                }
            },
        )
    }
    sheetChat?.let { chat -> ChatActionsSheet(telegram, chat) { sheetChat = null } }
}

@Composable
private fun DrawerItem(icon: ImageVector, title: String, onClick: () -> Unit) {
    val colors = Foxy.colors
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 16.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = colors.textSecondary)
        Spacer(Modifier.width(24.dp))
        Text(title, color = colors.text, fontSize = 16.sp)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatActionsSheet(telegram: Telegram, chat: ChatItem, onDismiss: () -> Unit) {
    val colors = Foxy.colors
    val scope = rememberCoroutineScope()
    val commands = remember { ChatCommands(telegram) }
    val api = telegram.serverApi
    var pinned by remember { mutableStateOf(chat.pinned) }
    var muted by remember { mutableStateOf(chat.muted) }
    var archived by remember { mutableStateOf(false) }
    var projects by remember { mutableStateOf<List<ProjectInfo>>(emptyList()) }
    var aiEnabled by remember { mutableStateOf(chat.label?.aiEnabled ?: false) }
    var selectedProject by remember { mutableStateOf<ProjectInfo?>(null) }
    var serverError by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf(false) }
    var folderChoices by remember { mutableStateOf<List<FolderTab>?>(null) }
    var namingFolder by remember { mutableStateOf(false) }
    val context = LocalContext.current

    LaunchedEffect(chat.id) {
        archived = runCatching { commands.isArchived(chat.id) }.getOrDefault(false)
        pinned = runCatching { commands.isPinned(chat.id) }.getOrDefault(chat.pinned)
        if (api.configured) {
            runCatching { api.projects() }.onSuccess { list ->
                projects = list
                selectedProject = list.firstOrNull { it.name == chat.label?.projectName }
            }.onFailure { serverError = true }
        }
    }

    fun act(block: suspend () -> Unit) {
        scope.launch { runCatching { block() } }
        onDismiss()
    }

    /** Outlives this sheet, so a folder limit or other refusal can still be shown after it closes. */
    fun actAndReport(block: suspend () -> Unit) {
        telegram.scope.launch {
            runCatching { block() }.onFailure { error ->
                withContext(Dispatchers.Main) { Toast.makeText(context.applicationContext, "Не удалось: ${error.message}", Toast.LENGTH_LONG).show() }
            }
        }
        onDismiss()
    }

    ModalBottomSheet(onDismiss, containerColor = colors.surface) {
        Column(Modifier.verticalScroll(rememberScrollState()).windowInsetsPadding(WindowInsets.navigationBars)) {
            Text(chat.title, color = colors.text, fontSize = 17.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp))
            SheetRow(if (chat.unread > 0) Icons.Filled.MarkChatRead else Icons.Filled.MarkChatUnread, if (chat.unread > 0) "Отметить прочитанным" else "Отметить непрочитанным") {
                act { if (chat.unread > 0) commands.markRead(chat.id) else commands.markUnread(chat.id) }
            }
            SheetRow(Icons.Filled.PushPin, if (pinned) "Открепить" else "Закрепить") { act { commands.setPinned(chat.id, !pinned) } }
            SheetRow(if (muted) Icons.Filled.NotificationsActive else Icons.Filled.NotificationsOff, if (muted) "Включить уведомления" else "Без звука") {
                muted = !muted
                act { commands.setMuted(chat.id, muted) }
            }
            SheetRow(if (archived) Icons.Filled.Unarchive else Icons.Filled.Archive, if (archived) "Вернуть из архива" else "В архив") {
                act { commands.setArchived(chat.id, !archived) }
            }
            SheetRow(Icons.Filled.Folder, "Добавить в папку") {
                scope.launch {
                    val ids = runCatching { commands.foldersToAdd(chat.id) }.getOrDefault(emptyList())
                    folderChoices = telegram.folders.value.filter { it.id in ids }
                }
            }
            SheetRow(if (chat.kind == app.foxygram.model.ChatKind.Private) Icons.Filled.Delete else Icons.AutoMirrored.Filled.ExitToApp, if (chat.kind == app.foxygram.model.ChatKind.Private) "Удалить чат" else "Покинуть", colors.danger) {
                confirmDelete = true
            }

            if (api.configured && !serverError) {
                HorizontalDivider(color = colors.border, thickness = 0.5.dp, modifier = Modifier.padding(vertical = 6.dp))
                Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.SmartToy, null, tint = colors.textSecondary)
                    Spacer(Modifier.width(20.dp))
                    Column(Modifier.weight(1f)) {
                        Text("Анализировать в Claude", color = colors.text, fontSize = 16.sp)
                        Text("Сообщения этого чата пойдут на ваш компьютер и в Claude", color = colors.textSecondary, fontSize = 13.sp)
                    }
                    Switch(aiEnabled, { value ->
                        aiEnabled = value
                        scope.launch {
                            runCatching { api.setAiEnabled(chat.id, value) }
                            telegram.applyLabel(chat.id) { it.copy(aiEnabled = value) }
                        }
                    })
                }
                PickerTitle("Проект")
                ChipRow(listOf("Без проекта") + projects.map { it.name }, selectedProject?.name ?: "Без проекта") { name ->
                    val project = projects.firstOrNull { it.name == name }
                    selectedProject = project
                    scope.launch {
                        runCatching { api.setProject(chat.id, project?.id) }
                        telegram.applyLabel(chat.id) { it.copy(projectName = project?.name, projectColor = project?.color, categoryName = null) }
                    }
                }
                selectedProject?.let { project ->
                    if (project.categories.isNotEmpty()) {
                        PickerTitle("Категория")
                        var category by remember(project.id) { mutableStateOf(chat.label?.categoryName) }
                        ChipRow(listOf("Без категории") + project.categories.map { it.second }, category ?: "Без категории") { name ->
                            val id = project.categories.firstOrNull { it.second == name }?.first
                            category = name.takeIf { id != null }
                            scope.launch {
                                runCatching { api.setCategory(chat.id, id) }
                                telegram.applyLabel(chat.id) { it.copy(categoryName = category) }
                            }
                        }
                    }
                }
                BrainJobsSection(api, chat.id)
                Spacer(Modifier.height(12.dp))
            }
        }
    }

    folderChoices?.let { choices ->
        AlertDialog(
            onDismissRequest = { folderChoices = null },
            title = { Text("Добавить в папку") },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    choices.forEach { folder ->
                        Text(
                            folder.title, color = colors.text, fontSize = 16.sp,
                            modifier = Modifier.fillMaxWidth().clickable { actAndReport { commands.addToFolder(chat.id, folder.id) } }.padding(vertical = 12.dp),
                        )
                    }
                    Text(
                        "Новая папка…", color = colors.accent, fontSize = 16.sp,
                        modifier = Modifier.fillMaxWidth().clickable {
                            folderChoices = null
                            namingFolder = true
                        }.padding(vertical = 12.dp),
                    )
                }
            },
            confirmButton = { TextButton({ folderChoices = null }) { Text("Отмена") } },
            containerColor = colors.surface,
        )
    }

    if (namingFolder) {
        var name by remember { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { namingFolder = false },
            title = { Text("Новая папка") },
            text = {
                OutlinedTextField(name, { name = it.replace("\n", "").take(FOLDER_NAME_MAX) }, singleLine = true, placeholder = { Text("Название") })
            },
            confirmButton = {
                TextButton({ actAndReport { commands.createFolder(chat.id, name.trim()) } }, enabled = name.isNotBlank()) { Text("Создать") }
            },
            dismissButton = { TextButton({ namingFolder = false }) { Text("Отмена") } },
            containerColor = colors.surface,
        )
    }

    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text(chat.title) },
            text = { Text(if (chat.kind == app.foxygram.model.ChatKind.Private) "Удалить этот чат у вас?" else "Покинуть этот чат?") },
            confirmButton = { TextButton({ act { commands.remove(chat.id) } }) { Text("Да", color = colors.danger) } },
            dismissButton = { TextButton({ confirmDelete = false }) { Text("Отмена") } },
            containerColor = colors.surface,
        )
    }
}

@Composable
private fun SheetRow(icon: ImageVector, title: String, tint: Color? = null, onClick: () -> Unit) {
    val colors = Foxy.colors
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 20.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = tint ?: colors.textSecondary)
        Spacer(Modifier.width(20.dp))
        Text(title, color = tint ?: colors.text, fontSize = 16.sp)
    }
}

@Composable
private fun PickerTitle(text: String) {
    Text(text, color = Foxy.colors.textSecondary, fontSize = 13.sp, fontWeight = FontWeight.Medium, modifier = Modifier.padding(start = 20.dp, top = 12.dp, bottom = 6.dp))
}

/**
 * Which of Brain's jobs get this chat, like Brain's own /chats page: one switch per job, a note when a Telegram
 * folder brings the chat in, and "follow folders only" once the chat has changes of its own.
 */
@Composable
private fun BrainJobsSection(api: ServerApi, chatId: Long) {
    val colors = Foxy.colors
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var state by remember(chatId) { mutableStateOf<BrainJobs?>(null) }
    var problem by remember(chatId) { mutableStateOf<String?>(null) }
    var busy by remember(chatId) { mutableStateOf(false) }

    LaunchedEffect(chatId) {
        runCatching { api.brainJobs(chatId) }
            .onSuccess { state = it }
            .onFailure { problem = it.message ?: "Brain isn't reachable" }
    }

    fun change(block: suspend () -> BrainChange) {
        if (busy) return
        busy = true
        scope.launch {
            runCatching { block() }
                .onSuccess { result ->
                    state = state?.copy(chat = result.chat)
                    if (result.text.isNotBlank()) Toast.makeText(context, result.text, Toast.LENGTH_SHORT).show()
                }
                .onFailure { failure ->
                    Toast.makeText(context, failure.message ?: "Didn't work", Toast.LENGTH_LONG).show()
                    runCatching { api.brainJobs(chatId) }.onSuccess { state = it }
                }
            busy = false
        }
    }

    HorizontalDivider(color = colors.border, thickness = 0.5.dp, modifier = Modifier.padding(top = 12.dp))
    PickerTitle("Brain jobs")
    val current = state
    val failure = problem
    when {
        failure != null -> BrainNote(failure)
        current == null -> BrainNote("Loading…")
        current.jobs.isEmpty() -> BrainNote("Brain has no jobs switched on.")
        else -> {
            current.jobs.forEach { job ->
                val on = job.id in current.chat.jobs
                val hint = when {
                    on && job.id in current.chat.viaFolder -> "from a folder"
                    job.id in current.chat.removed -> "taken out, although its folder adds it"
                    else -> null
                }
                Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(job.name, color = colors.text, fontSize = 16.sp)
                        if (hint != null) Text(hint, color = colors.textSecondary, fontSize = 13.sp)
                    }
                    Switch(on, { value -> change { api.setBrainJob(chatId, job.id, value) } }, enabled = !busy)
                }
            }
            // Sending off: Brain keeps reading the chat and shows what it would have answered, but never sends to it.
            if (current.chat.jobs.isNotEmpty() || !current.chat.sending) {
                val sending = current.chat.sending
                Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Brain may send replies", color = colors.text, fontSize = 16.sp)
                        Text(
                            if (sending) "Each reply still needs your approval" else "Off: Brain only shows what it would have answered",
                            color = if (sending) colors.textSecondary else colors.warning, fontSize = 13.sp,
                        )
                    }
                    Switch(sending, { value -> change { api.setBrainSending(chatId, value) } }, enabled = !busy)
                }
            }
            if (current.chat.added.isNotEmpty() || current.chat.removed.isNotEmpty()) {
                TextButton({ change { api.resetBrainJobs(chatId) } }, Modifier.padding(horizontal = 8.dp), enabled = !busy) {
                    Text("Follow folders only", color = colors.accent)
                }
            }
            if (!current.connected) BrainNote("Brain isn't connected to Telegram right now.")
        }
    }
}

@Composable
private fun BrainNote(text: String) {
    Text(text, color = Foxy.colors.textSecondary, fontSize = 14.sp, modifier = Modifier.padding(horizontal = 20.dp, vertical = 4.dp))
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
private fun ChipRow(options: List<String>, selected: String, onPick: (String) -> Unit) {
    val colors = Foxy.colors
    androidx.compose.foundation.layout.FlowRow(
        Modifier.padding(horizontal = 20.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        options.forEach { option ->
            val active = option == selected
            Box(
                Modifier.clip(RoundedCornerShape(16.dp))
                    .background(if (active) colors.accentSoft else colors.surfaceHigh)
                    .clickable { onPick(option) }
                    .padding(horizontal = 14.dp, vertical = 7.dp),
            ) {
                Text(option, color = if (active) colors.accent else colors.text, fontSize = 14.sp, fontWeight = if (active) FontWeight.Medium else FontWeight.Normal)
            }
        }
    }
}
