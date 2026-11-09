package app.foxygram.ui.chats

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.foxygram.model.ChatItem
import app.foxygram.model.FolderTab
import app.foxygram.ui.common.CountBadge
import app.foxygram.ui.theme.Foxy
import kotlinx.coroutines.flow.distinctUntilChanged

const val FOLDER_ALL = 0
const val FOLDER_ARCHIVE = -1

@Composable
fun ChatListScreen(
    chats: List<ChatItem>,
    folders: List<FolderTab>,
    selectedFolder: Int,
    connectionLabel: String?,
    onFolder: (Int) -> Unit,
    onChat: (ChatItem) -> Unit,
    onChatLongPress: (ChatItem) -> Unit,
    onMenu: () -> Unit,
    onNearEnd: () -> Unit,
    onSearch: (String) -> Unit,
    searchResults: List<ChatItem>?,
    modifier: Modifier = Modifier,
    onMarkFolderRead: (Int) -> Unit = {},
) {
    val colors = Foxy.colors
    var searching by remember { mutableStateOf(false) }
    Column(modifier.fillMaxSize().background(colors.background).windowInsetsPadding(WindowInsets.navigationBars).imePadding()) {
        Column(Modifier.fillMaxWidth().background(colors.surface).windowInsetsPadding(WindowInsets.statusBars)) {
            if (searching) {
                SearchBar(onSearch) {
                    searching = false
                    onSearch("")
                }
            } else {
                TopBar(connectionLabel, onMenu) { searching = true }
                if (folders.size > 1) FolderBar(folders, selectedFolder, onFolder, onMarkFolderRead)
            }
        }
        val list = if (searching && searchResults != null) searchResults else chats
        val state = rememberLazyListState()
        LaunchedEffect(selectedFolder) { state.scrollToItem(0) }
        val nearEnd by remember {
            derivedStateOf {
                val last = state.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
                last >= state.layoutInfo.totalItemsCount - 15
            }
        }
        LaunchedEffect(state) {
            snapshotFlow { nearEnd }.distinctUntilChanged().collect { if (it) onNearEnd() }
        }
        LazyColumn(Modifier.fillMaxSize(), state = state) {
            items(list, key = { it.id }, contentType = { "chat" }) { chat ->
                ChatRow(chat, onClick = { onChat(chat) }, onLongClick = { onChatLongPress(chat) })
            }
        }
    }
}

@Composable
private fun TopBar(connectionLabel: String?, onMenu: () -> Unit, onSearch: () -> Unit) {
    val colors = Foxy.colors
    Row(Modifier.fillMaxWidth().height(56.dp), verticalAlignment = Alignment.CenterVertically) {
        IconButton(onMenu) { Icon(Icons.Filled.Menu, "Меню", tint = colors.text) }
        Text(
            connectionLabel ?: "FoxyGram",
            color = colors.text,
            fontSize = 20.sp,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.weight(1f).padding(start = 8.dp),
            maxLines = 1,
        )
        IconButton(onSearch) { Icon(Icons.Filled.Search, "Поиск", tint = colors.text) }
    }
}

@Composable
private fun SearchBar(onQuery: (String) -> Unit, onClose: () -> Unit) {
    val colors = Foxy.colors
    var query by remember { mutableStateOf("") }
    val focus = remember { FocusRequester() }
    LaunchedEffect(Unit) { focus.requestFocus() }
    Row(Modifier.fillMaxWidth().height(56.dp), verticalAlignment = Alignment.CenterVertically) {
        IconButton(onClose) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Назад", tint = colors.text) }
        Box(Modifier.weight(1f), contentAlignment = Alignment.CenterStart) {
            if (query.isEmpty()) Text("Поиск", color = colors.textSecondary, fontSize = 17.sp)
            BasicTextField(
                query,
                {
                    query = it
                    onQuery(it)
                },
                singleLine = true,
                textStyle = TextStyle(color = colors.text, fontSize = 17.sp),
                cursorBrush = SolidColor(colors.accent),
                modifier = Modifier.fillMaxWidth().focusRequester(focus),
            )
        }
        if (query.isNotEmpty()) {
            IconButton({
                query = ""
                onQuery("")
            }) { Icon(Icons.Filled.Close, "Очистить", tint = colors.textSecondary) }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun FolderBar(folders: List<FolderTab>, selected: Int, onFolder: (Int) -> Unit, onMarkRead: (Int) -> Unit) {
    val colors = Foxy.colors
    LazyRow(Modifier.fillMaxWidth().height(44.dp), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
        items(folders, key = { it.id }) { folder ->
            val active = folder.id == selected
            var menuOpen by remember { mutableStateOf(false) }
            Box(
                Modifier.height(44.dp).combinedClickable(onClick = { onFolder(folder.id) }, onLongClick = { menuOpen = true }).padding(horizontal = 12.dp),
                contentAlignment = Alignment.Center,
            ) {
                DropdownMenu(menuOpen, { menuOpen = false }, Modifier.background(colors.surface)) {
                    DropdownMenuItem(
                        text = { Text("Прочитать всё", color = colors.text) },
                        onClick = {
                            menuOpen = false
                            onMarkRead(folder.id)
                        },
                    )
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        folder.title,
                        color = if (active) colors.accent else colors.textSecondary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Medium,
                        maxLines = 1,
                    )
                    if (folder.unread > 0) {
                        Spacer(Modifier.width(5.dp))
                        CountBadge(folder.unread, if (active) colors.accent else colors.mutedBadge, fontSize = 12.sp)
                    }
                }
                if (active) {
                    Box(
                        Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(3.dp)
                            .clip(RoundedCornerShape(topStart = 3.dp, topEnd = 3.dp)).background(colors.accent),
                    )
                }
            }
        }
    }
}
