package app.foxygram.ui

import android.app.Application
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import app.foxygram.model.MessageBody
import app.foxygram.notify.ConnectionService
import app.foxygram.td.AuthState
import app.foxygram.td.TdAudioController
import app.foxygram.td.Telegram
import app.foxygram.ui.auth.LoginScreens
import app.foxygram.ui.auth.PairScreen
import app.foxygram.ui.cases.CaseDetailScreen
import app.foxygram.ui.cases.CasesScreen
import app.foxygram.ui.chat.ChatRoute
import app.foxygram.ui.chat.LocalAudio
import app.foxygram.ui.chat.MediaViewer
import app.foxygram.ui.chats.ChatsRoute
import app.foxygram.ui.common.LocalFiles
import app.foxygram.ui.settings.AiChatsScreen
import app.foxygram.ui.settings.SettingsScreen
import app.foxygram.ui.theme.Foxy
import app.foxygram.ui.theme.FoxyTheme
import kotlinx.coroutines.flow.MutableStateFlow

sealed interface Route {
    data object Chats : Route
    data class Chat(val id: Long) : Route
    data object Cases : Route
    data class CaseDetail(val id: Long) : Route
    data object Settings : Route
    data object AiChats : Route
    data class Media(val body: MessageBody) : Route
}

@Composable
fun FoxyRoot(telegram: Telegram, openChat: MutableStateFlow<Long?>) {
    val theme by telegram.settings.theme.collectAsState()
    val paired by telegram.settings.paired.collectAsState()
    val context = LocalContext.current
    val audio = remember { TdAudioController(context.applicationContext as Application, telegram) }
    DisposableEffect(Unit) { onDispose { audio.release() } }

    FoxyTheme(theme) {
        CompositionLocalProvider(LocalFiles provides telegram.files, LocalAudio provides audio) {
            Box(Modifier.fillMaxSize().background(Foxy.colors.background)) {
                if (!paired) {
                    PairScreen { code ->
                        telegram.settings.applyPairing(code)
                        telegram.start()
                    }
                } else {
                    val auth by telegram.auth.collectAsState()
                    when (val state = auth) {
                        AuthState.Starting -> Loading("Запуск…")
                        AuthState.Ready -> MainNavigation(telegram, openChat)
                        is AuthState.Unsupported -> Loading("Этот шаг входа пока не поддерживается: ${state.state}")
                        AuthState.Closed -> Loading("Сессия закрыта. Перезапустите приложение.")
                        else -> LoginScreens(telegram, state)
                    }
                }
            }
        }
    }
}

@Composable
private fun Loading(text: String) {
    Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = androidx.compose.foundation.layout.Arrangement.Center) {
        CircularProgressIndicator(color = Foxy.colors.accent)
        Text(text, color = Foxy.colors.textSecondary, modifier = Modifier.padding(16.dp))
    }
}

@Composable
private fun MainNavigation(telegram: Telegram, openChat: MutableStateFlow<Long?>) {
    val context = LocalContext.current
    val stack = remember { mutableStateListOf<Route>(Route.Chats) }
    val navigate: (Route) -> Unit = { stack.add(it) }
    val back: () -> Unit = { if (stack.size > 1) stack.removeAt(stack.lastIndex) }

    LaunchedEffect(Unit) {
        if (telegram.settings.keepConnected) ConnectionService.start(context)
    }
    val pending by openChat.collectAsState()
    LaunchedEffect(pending) {
        pending?.let {
            if (stack.lastOrNull() != Route.Chat(it)) stack.add(Route.Chat(it))
            openChat.value = null
        }
    }
    BackHandler(stack.size > 1) { back() }

    // The chat list stays composed underneath, so its scroll position survives opening a chat.
    Box(Modifier.fillMaxSize()) {
        ChatsRoute(telegram, navigate)
        when (val top = stack.last()) {
            Route.Chats -> Unit
            is Route.Chat -> androidx.compose.runtime.key(top.id) { ChatRoute(telegram, top.id, back, navigate) }
            Route.Cases -> CasesScreen(telegram, back, navigate)
            is Route.CaseDetail -> CaseDetailScreen(telegram, top.id, back, navigate)
            Route.Settings -> SettingsScreen(telegram, back)
            Route.AiChats -> AiChatsScreen(telegram, back)
            is Route.Media -> MediaViewer(telegram, top.body, back)
        }
    }
}
