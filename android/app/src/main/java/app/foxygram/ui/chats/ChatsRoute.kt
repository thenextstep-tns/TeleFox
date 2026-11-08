package app.foxygram.ui.chats

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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.foxygram.data.ProjectInfo
import app.foxygram.model.ChatItem
import app.foxygram.td.ChatCommands
import app.foxygram.td.Telegram
import app.foxygram.ui.Route
import app.foxygram.ui.theme.Foxy
import kotlinx.coroutines.launch

@Composable
fun ChatsRoute(telegram: Telegram, navigate: (Route) -> Unit) {
    val chats by telegram.chats.collectAsState()
    val folders by telegram.folders.collectAsState()
    val selected by telegram.selectedFolder.collectAsState()
    val connection by telegram.connection.collectAsState()
    val drawer = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
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
            onChat = { navigate(Route.Chat(it.id)) },
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
                Spacer(Modifier.height(12.dp))
            }
        }
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
