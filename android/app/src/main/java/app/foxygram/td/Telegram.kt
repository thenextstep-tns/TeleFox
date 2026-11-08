package app.foxygram.td

import android.app.Application
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.os.Build
import app.foxygram.BuildConfig
import app.foxygram.data.ServerApi
import app.foxygram.data.Settings
import app.foxygram.model.ChatItem
import app.foxygram.model.ChatLabel
import app.foxygram.model.FolderTab
import app.foxygram.notify.Alerts
import app.foxygram.ui.chats.FOLDER_ALL
import app.foxygram.ui.chats.FOLDER_ARCHIVE
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import org.drinkless.tdlib.Client
import org.drinkless.tdlib.TdApi
import java.io.File
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

class TdException(val code: Int, override val message: String) : Exception("$code: $message")

sealed interface AuthState {
    data object Starting : AuthState
    data object WaitPhone : AuthState
    data class WaitQr(val link: String) : AuthState
    data class WaitCode(val phone: String) : AuthState
    data class WaitPassword(val hint: String) : AuthState
    data object Ready : AuthState
    data class Unsupported(val state: String) : AuthState
    data object Closed : AuthState
}

/** The single TDLib instance for the whole process, including the background connection. */
@OptIn(ExperimentalCoroutinesApi::class, FlowPreview::class)
class Telegram private constructor(private val app: Application, val settings: Settings) {
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    /** All state below is touched only here, in the order TDLib produced it. */
    val serial = Dispatchers.Default.limitedParallelism(1)

    private val incoming = Channel<TdApi.Object>(Channel.UNLIMITED)
    private val started = AtomicBoolean(false)
    private lateinit var client: Client

    val store = TdStore()
    val files = TdFiles(this)
    val mapper = TdMapper(store, files)
    val alerts = Alerts(app, this)

    private val _auth = MutableStateFlow<AuthState>(AuthState.Starting)
    val auth: StateFlow<AuthState> = _auth.asStateFlow()

    private val _connection = MutableStateFlow<String?>(null)
    val connection: StateFlow<String?> = _connection.asStateFlow()

    private val _chats = MutableStateFlow<List<ChatItem>>(emptyList())
    val chats: StateFlow<List<ChatItem>> = _chats.asStateFlow()

    private val _folders = MutableStateFlow(listOf(FolderTab(FOLDER_ALL, "Все")))
    val folders: StateFlow<List<FolderTab>> = _folders.asStateFlow()

    private val _selectedFolder = MutableStateFlow(FOLDER_ALL)
    val selectedFolder: StateFlow<Int> = _selectedFolder.asStateFlow()

    private val _labels = MutableStateFlow<Map<Long, ChatLabel>>(emptyMap())
    val labels: StateFlow<Map<Long, ChatLabel>> = _labels.asStateFlow()

    private val listDirty = MutableStateFlow(0L)
    private val exhausted = HashSet<String>()

    @Volatile var activeSession: ChatSession? = null

    @Volatile var visibleChatId: Long = 0

    @Volatile var appVisible: Boolean = false

    fun start() {
        if (!started.compareAndSet(false, true)) return
        Client.execute(TdApi.SetLogVerbosityLevel(1))
        client = Client.create({ incoming.trySend(it) }, null, null)
        scope.launch(serial) { for (update in incoming) handle(update) }
        scope.launch { listDirty.debounce(LIST_DEBOUNCE_MS).collect { withContext(serial) { publishLists() } } }
        watchNetwork()
    }

    @Suppress("UNCHECKED_CAST")
    suspend fun <R : TdApi.Object> call(function: TdApi.Function<R>): R = suspendCancellableCoroutine { continuation ->
        client.send(function, { result ->
            if (result is TdApi.Error) {
                continuation.resumeWithException(TdException(result.code, result.message))
            } else {
                continuation.resume(result as R)
            }
        }, { continuation.resumeWithException(it) })
    }

    fun fire(function: TdApi.Function<*>) {
        if (started.get()) client.send(function, null, null)
    }

    private fun markListDirty() {
        listDirty.value = listDirty.value + 1
    }

    fun onVisibilityChanged(visible: Boolean) {
        appVisible = visible
        if (!started.get()) return
        fire(TdApi.SetOption("online", TdApi.OptionValueBoolean(visible)))
    }

    private fun watchNetwork() {
        val manager = app.getSystemService(ConnectivityManager::class.java)
        manager.registerDefaultNetworkCallback(object : ConnectivityManager.NetworkCallback() {
            override fun onCapabilitiesChanged(network: Network, capabilities: NetworkCapabilities) {
                val type: TdApi.NetworkType = when {
                    capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> TdApi.NetworkTypeWiFi()
                    capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> TdApi.NetworkTypeMobile()
                    else -> TdApi.NetworkTypeOther()
                }
                fire(TdApi.SetNetworkType(type))
            }

            override fun onLost(network: Network) {
                fire(TdApi.SetNetworkType(TdApi.NetworkTypeNone()))
            }
        })
    }

    private fun handle(update: TdApi.Object) {
        when (update) {
            is TdApi.UpdateAuthorizationState -> onAuth(update.authorizationState)
            is TdApi.UpdateConnectionState -> _connection.value = when (update.state) {
                is TdApi.ConnectionStateWaitingForNetwork -> "Ожидание сети…"
                is TdApi.ConnectionStateConnecting, is TdApi.ConnectionStateConnectingToProxy -> "Соединение…"
                is TdApi.ConnectionStateUpdating -> "Обновление…"
                else -> null
            }
            is TdApi.UpdateFile -> files.onFile(update.file)
            is TdApi.UpdateChatFolders -> {
                store.folders = update.chatFolders.toList()
                markListDirty()
            }
            is TdApi.UpdateUnreadChatCount -> {
                store.unreadByList[listKey(update.chatList)] = update.unreadUnmutedCount
                markListDirty()
            }
            is TdApi.UpdateNewMessage -> {
                store.onUpdate(update)
                alerts.onNewMessage(update.message)
            }
            is TdApi.UpdateChatReadInbox -> {
                store.onUpdate(update)
                alerts.onRead(update.chatId, update.unreadCount)
            }
            else -> if (store.onUpdate(update)) markListDirty()
        }
        if (update is TdApi.UpdateNewMessage || update is TdApi.UpdateChatLastMessage || update is TdApi.UpdateChatReadInbox) markListDirty()
        activeSession?.onUpdate(update)
    }

    private fun onAuth(state: TdApi.AuthorizationState) {
        when (state) {
            is TdApi.AuthorizationStateWaitTdlibParameters -> sendParameters()
            is TdApi.AuthorizationStateWaitPhoneNumber -> _auth.value = AuthState.WaitPhone
            is TdApi.AuthorizationStateWaitOtherDeviceConfirmation -> _auth.value = AuthState.WaitQr(state.link)
            is TdApi.AuthorizationStateWaitCode -> _auth.value = AuthState.WaitCode(state.codeInfo.phoneNumber)
            is TdApi.AuthorizationStateWaitPassword -> _auth.value = AuthState.WaitPassword(state.passwordHint)
            is TdApi.AuthorizationStateReady -> {
                _auth.value = AuthState.Ready
                fire(TdApi.SetOption("online", TdApi.OptionValueBoolean(appVisible)))
                fire(TdApi.SetOption("use_storage_optimizer", TdApi.OptionValueBoolean(true)))
                scope.launch { loadMore(force = true) }
                refreshLabels()
            }
            is TdApi.AuthorizationStateClosed -> _auth.value = AuthState.Closed
            is TdApi.AuthorizationStateLoggingOut, is TdApi.AuthorizationStateClosing -> Unit
            else -> _auth.value = AuthState.Unsupported(state.javaClass.simpleName)
        }
    }

    private fun sendParameters() {
        val root = File(app.filesDir, "td").apply { mkdirs() }
        fire(TdApi.SetTdlibParameters(
            false,
            root.absolutePath,
            File(root, "files").absolutePath,
            ByteArray(0),
            true, true, true, false,
            settings.apiId,
            settings.apiHash,
            "ru",
            "${Build.MANUFACTURER} ${Build.MODEL}",
            Build.VERSION.RELEASE,
            BuildConfig.VERSION_NAME,
        ))
    }

    suspend fun submitPhone(phone: String) {
        call(TdApi.SetAuthenticationPhoneNumber(phone, null))
    }

    suspend fun requestQr() {
        call(TdApi.RequestQrCodeAuthentication(LongArray(0)))
    }

    suspend fun submitCode(code: String) {
        call(TdApi.CheckAuthenticationCode(code))
    }

    suspend fun submitPassword(password: String) {
        call(TdApi.CheckAuthenticationPassword(password))
    }

    suspend fun logOut() {
        call(TdApi.LogOut())
    }

    private fun currentList(): TdApi.ChatList = listFor(_selectedFolder.value)

    private fun listFor(folder: Int): TdApi.ChatList = when (folder) {
        FOLDER_ALL -> TdApi.ChatListMain()
        FOLDER_ARCHIVE -> TdApi.ChatListArchive()
        else -> TdApi.ChatListFolder(folder)
    }

    fun selectFolder(folder: Int) {
        _selectedFolder.value = folder
        markListDirty()
        scope.launch { loadMore(force = true) }
    }

    suspend fun loadMore(force: Boolean = false) {
        val list = currentList()
        val key = listKey(list)
        if (key in exhausted && !force) return
        try {
            call(TdApi.LoadChats(list, CHAT_PAGE))
        } catch (error: TdException) {
            if (error.code == 404) exhausted += key
        }
    }

    private fun publishLists() {
        val list = currentList()
        val key = listKey(list)
        val labels = _labels.value
        _chats.value = store.ordered(key).map { mapper.toChatItem(it, key, labels[it.id]) }
        val tabs = ArrayList<FolderTab>()
        tabs += FolderTab(FOLDER_ALL, "Все", store.unreadByList[listKey(TdApi.ChatListMain())] ?: 0)
        store.folders.forEach { folder ->
            tabs += FolderTab(folder.id, folder.name.text.text, store.unreadByList[listKey(TdApi.ChatListFolder(folder.id))] ?: 0)
        }
        if (store.hasArchive()) tabs += FolderTab(FOLDER_ARCHIVE, "Архив", store.unreadByList[listKey(TdApi.ChatListArchive())] ?: 0)
        _folders.value = tabs
    }

    /** Asks the laptop for labels. Called on demand only, never on a timer in the background. */
    fun refreshLabels() {
        val api = serverApi
        if (!api.configured) return
        scope.launch {
            runCatching { api.labels() }.onSuccess {
                _labels.value = it
                markListDirty()
            }
        }
    }

    fun applyLabel(chatId: Long, change: (ChatLabel) -> ChatLabel) {
        _labels.value = _labels.value + (chatId to change(_labels.value[chatId] ?: ChatLabel()))
        markListDirty()
    }

    val serverApi by lazy { ServerApi(settings) }

    suspend fun searchChats(query: String): List<ChatItem> {
        if (query.isBlank()) return emptyList()
        val local = call(TdApi.SearchChats(query, null, SEARCH_LIMIT)).chatIds
        val remote = runCatching { call(TdApi.SearchChatsOnServer(query, null, SEARCH_LIMIT)).chatIds }.getOrDefault(LongArray(0))
        return withContext(serial) {
            (local + remote).distinct().mapNotNull { id ->
                store.chat(id)?.let { mapper.toChatItem(it, listKey(TdApi.ChatListMain()), _labels.value[id]) }
            }
        }
    }

    companion object {
        private const val CHAT_PAGE = 100
        private const val SEARCH_LIMIT = 50
        private const val LIST_DEBOUNCE_MS = 50L

        @Volatile private var instance: Telegram? = null

        fun get(app: Application): Telegram = instance ?: synchronized(this) {
            instance ?: Telegram(app, Settings(app)).also { instance = it }
        }

        fun listKey(list: TdApi.ChatList): String = when (list) {
            is TdApi.ChatListMain -> "main"
            is TdApi.ChatListArchive -> "archive"
            is TdApi.ChatListFolder -> "folder${list.chatFolderId}"
            else -> "other"
        }
    }
}
