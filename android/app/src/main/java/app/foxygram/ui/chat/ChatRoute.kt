package app.foxygram.ui.chat

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.MediaRecorder
import android.net.Uri
import android.os.Build
import android.provider.OpenableColumns
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Forward
import androidx.compose.material.icons.automirrored.filled.Reply
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.InsertDriveFile
import androidx.compose.material.icons.filled.Photo
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.FileProvider
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.repeatOnLifecycle
import app.foxygram.data.BrainPanel
import app.foxygram.model.FeedRow
import app.foxygram.model.MessageBody
import app.foxygram.model.MessageItem
import app.foxygram.td.ChatSession
import app.foxygram.td.Telegram
import app.foxygram.ui.Route
import app.foxygram.ui.brain.BrainMessagePreview
import app.foxygram.ui.brain.BrainPanelContent
import app.foxygram.ui.brain.LocalBrainMarks
import app.foxygram.ui.common.Avatar
import app.foxygram.ui.common.clockTime
import app.foxygram.ui.theme.Foxy
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.drinkless.tdlib.TdApi
import java.io.File

private const val BRAIN_BUSY_MS = 4_000L
private const val BRAIN_IDLE_MS = 15_000L

private val QUICK_REACTIONS = listOf("👍", "❤", "🔥", "🥰", "👏", "😁")

private class ComposerMode(val messageId: Long, val isEdit: Boolean, val title: String, val text: String)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatRoute(telegram: Telegram, chatId: Long, onBack: () -> Unit, navigate: (Route) -> Unit, topicId: Int = 0, topicTitle: String? = null) {
    val context = LocalContext.current
    val colors = Foxy.colors
    val session = remember(chatId, topicId) { ChatSession(telegram, chatId, topicId, topicTitle) }
    val scope = rememberCoroutineScope()
    val listState = rememberLazyListState()
    val feed by session.feed.collectAsState()
    val headerState by session.header.collectAsState()
    val anchor by session.initialAnchor.collectAsState()
    var input by remember { mutableStateOf(TextFieldValue("")) }
    var mode by remember { mutableStateOf<ComposerMode?>(null) }
    var selected by remember { mutableStateOf<MessageItem?>(null) }
    var forwarding by remember { mutableStateOf<MessageItem?>(null) }
    var deleting by remember { mutableStateOf<MessageItem?>(null) }
    var showAttach by remember { mutableStateOf(false) }
    var recordingSeconds by remember { mutableStateOf<Int?>(null) }
    var recorder by remember { mutableStateOf<VoiceRecorder?>(null) }

    // Brain's side panel: only for chats in one of Brain's jobs, read through the laptop while this screen is in front.
    val api = telegram.serverApi
    val lifecycleOwner = LocalLifecycleOwner.current
    var brain by remember(chatId) { mutableStateOf<BrainPanel?>(null) }
    var brainError by remember(chatId) { mutableStateOf<String?>(null) }
    var brainOpen by remember(chatId) { mutableStateOf(false) }
    var brainMessage by remember(chatId) { mutableStateOf<MessageItem?>(null) }
    var brainRefresh by remember(chatId) { mutableIntStateOf(0) }
    LaunchedEffect(chatId, brainRefresh) {
        if (!api.configured) return@LaunchedEffect
        lifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
            while (true) {
                runCatching { api.brainPanel(chatId) }
                    .onSuccess { panel ->
                        brain = panel.takeIf { it.active }
                        brainError = null
                    }
                    .onFailure { if (brain != null) brainError = it.message }
                delay(if (brain?.busy == true) BRAIN_BUSY_MS else BRAIN_IDLE_MS)
            }
        }
    }
    val brainMarks = remember(brain) { brain?.marks() ?: emptyMap() }

    DisposableEffect(chatId) {
        session.open()
        onDispose {
            session.close()
            telegram.scope.launch { session.saveDraft(input.text) }
        }
    }
    LaunchedEffect(chatId) {
        val draft = session.initialDraft()
        if (draft.isNotEmpty()) input = TextFieldValue(draft, TextRange(draft.length))
    }
    LaunchedEffect(anchor) {
        anchor?.let {
            listState.scrollToItem(it)
            session.consumeAnchor()
        }
    }
    val newest = (feed.firstOrNull() as? FeedRow.Message)?.item?.id
    LaunchedEffect(newest) {
        if (newest != null && listState.firstVisibleItemIndex <= 1) listState.animateScrollToItem(0)
    }

    val photoPicker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) scope.launch { sendAttachment(context, session, uri, mode?.messageId) }
    }
    val filePicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) scope.launch { sendAttachment(context, session, uri, mode?.messageId, asDocument = true) }
    }
    val micPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}

    val actions = remember(session) {
        object : MessageActions {
            override fun onTap(item: MessageItem) {
                // In a chat Brain analyses, a tap shows what Brain made of the message; long press keeps the usual menu.
                if (brain != null) {
                    brainMessage = item
                    brainOpen = true
                    brainRefresh++ // fresh from Brain right away, not on the next timer
                } else {
                    selected = item
                }
            }
            override fun onLongPress(item: MessageItem) { selected = item }
            override fun onReply(item: MessageItem) { mode = replyMode(item) }
            override fun onJumpTo(messageId: Long) {
                val index = session.feed.value.indexOfFirst { it is FeedRow.Message && it.item.id == messageId }
                if (index >= 0) scope.launch { listState.animateScrollToItem(index) }
            }
            override fun onReaction(item: MessageItem, emoji: String) {
                val chosen = item.reactions.firstOrNull { it.emoji == emoji }?.chosen ?: false
                scope.launch { runCatching { session.react(item.id, emoji, chosen) } }
            }
            override fun onOpenMedia(item: MessageItem, body: MessageBody) { navigate(Route.Media(body)) }
            override fun onOpenFile(fileId: Int, name: String, mime: String) { openFile(context, telegram, fileId, name, mime) }
            override fun onLink(url: String) { openLink(context, url) }
            override fun onVote(item: MessageItem, optionIndex: Int) { scope.launch { runCatching { session.vote(item.id, optionIndex) } } }
            override fun onSender(item: MessageItem) { item.sender?.let { navigate(Route.Chat(it.id)) } }
        }
    }

    val header = headerState ?: return
    CompositionLocalProvider(LocalBrainMarks provides brainMarks) {
    ChatScreen(
        header = header,
        feed = feed,
        listState = listState,
        actions = actions,
        onBack = onBack,
        onHeader = {},
        onMenu = {},
        onLoadOlder = session::loadOlder,
        onLoadNewer = session::loadNewer,
        onVisibleMessages = session::onVisible,
        onScrollToBottom = session::jumpToLatest,
        onBrain = if (brain != null) {
            {
                brainMessage = null
                brainOpen = true
            }
        } else {
            null
        },
        composer = {
            Box(Modifier.fillMaxWidth()) {
                Composer(
                    value = input,
                    onValue = { input = it },
                    target = mode?.let { ComposerTarget(it.isEdit, it.title, it.text) },
                    recordingSeconds = recordingSeconds,
                    onCancelTarget = {
                        if (mode?.isEdit == true) input = TextFieldValue("")
                        mode = null
                    },
                    onSend = {
                        val text = input.text.trim()
                        val target = mode
                        input = TextFieldValue("")
                        mode = null
                        scope.launch {
                            runCatching {
                                if (target?.isEdit == true) session.editText(target.messageId, text) else session.sendText(text, target?.messageId)
                            }.onFailure { Toast.makeText(context, "Не удалось отправить", Toast.LENGTH_SHORT).show() }
                        }
                    },
                    onAttach = { showAttach = true },
                    onRecordStart = {
                        if (context.checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                            micPermission.launch(Manifest.permission.RECORD_AUDIO)
                        } else {
                            recorder = VoiceRecorder(context).also { it.start() }
                            recordingSeconds = 0
                        }
                    },
                    onRecordStop = { cancel ->
                        val active = recorder
                        recorder = null
                        recordingSeconds = null
                        val result = active?.stop()
                        if (result != null && !cancel && result.seconds >= 1) {
                            scope.launch {
                                runCatching {
                                    session.sendContent(
                                        TdApi.InputMessageVoiceNote(TdApi.InputVoiceNote(TdApi.InputFileLocal(result.path), result.seconds, ByteArray(0)), null, null),
                                        mode?.messageId,
                                    )
                                }
                            }
                        }
                    },
                )
            }
        },
    )
    }
    LaunchedEffect(recorder) {
        while (recorder != null) {
            delay(1000)
            recordingSeconds = (recordingSeconds ?: 0) + 1
        }
    }

    selected?.let { item ->
        ModalBottomSheet({ selected = null }, containerColor = colors.surface) {
            Column(Modifier.windowInsetsPadding(WindowInsets.navigationBars)) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    QUICK_REACTIONS.forEach { emoji ->
                        Box(
                            Modifier.size(44.dp).clip(CircleShape).clickable {
                                actions.onReaction(item, emoji)
                                selected = null
                            },
                            contentAlignment = Alignment.Center,
                        ) { Text(emoji, fontSize = 24.sp) }
                    }
                }
                ActionRow(Icons.AutoMirrored.Filled.Reply, "Ответить") {
                    mode = replyMode(item)
                    selected = null
                }
                if (brain != null) {
                    ActionRow(Icons.Filled.SmartToy, "What Brain decided") {
                        brainMessage = item
                        brainOpen = true
                        selected = null
                        brainRefresh++
                    }
                }
                val text = (item.body as? MessageBody.Text)?.text?.text ?: item.body.caption.text
                if (text.isNotEmpty()) {
                    ActionRow(Icons.Filled.ContentCopy, "Копировать") {
                        context.getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText("message", text))
                        selected = null
                    }
                }
                if (item.canEdit) {
                    ActionRow(Icons.Filled.Edit, "Изменить") {
                        mode = ComposerMode(item.id, true, "Редактирование", text)
                        input = TextFieldValue(text, TextRange(text.length))
                        selected = null
                    }
                }
                ActionRow(Icons.AutoMirrored.Filled.Forward, "Переслать") {
                    forwarding = item
                    selected = null
                }
                if (item.canDelete) {
                    ActionRow(Icons.Filled.Delete, "Удалить") {
                        deleting = item
                        selected = null
                    }
                }
            }
        }
    }

    if (brainOpen) {
        ModalBottomSheet({ brainOpen = false }, containerColor = colors.surface) {
            val message = brainMessage
            BrainPanelContent(
                panel = brain,
                error = brainError,
                selectedIds = message?.let { it.groupIds.ifEmpty { listOf(it.id) } },
                preview = message?.let { brainPreview(it, header.chat.title) },
                onShowAll = { brainMessage = null },
                onJump = { run ->
                    brainOpen = false
                    run.messageIds.firstOrNull()?.let(actions::onJumpTo)
                },
                onDecide = { action, decision, text, reason ->
                    scope.launch {
                        runCatching { api.brainDecide(action.id, decision, text, reason) }
                            .onSuccess { Toast.makeText(context, it.ifBlank { "Готово" }, Toast.LENGTH_SHORT).show() }
                            .onFailure { Toast.makeText(context, "Не удалось: ${it.message}", Toast.LENGTH_LONG).show() }
                        brainRefresh++
                    }
                },
                modifier = Modifier.verticalScroll(rememberScrollState()).windowInsetsPadding(WindowInsets.navigationBars),
                onJumpToMessage = { id ->
                    brainOpen = false
                    actions.onJumpTo(id)
                },
            )
        }
    }

    deleting?.let { item ->
        var forEveryone by remember { mutableStateOf(true) }
        AlertDialog(
            onDismissRequest = { deleting = null },
            title = { Text("Удалить сообщение?") },
            text = {
                Row(Modifier.clickable { forEveryone = !forEveryone }, verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(forEveryone, { forEveryone = it })
                    Text("Удалить у всех")
                }
            },
            confirmButton = {
                TextButton({
                    val ids = item.groupIds.ifEmpty { listOf(item.id) }
                    scope.launch { runCatching { session.delete(ids, forEveryone) } }
                    deleting = null
                }) { Text("Удалить", color = colors.danger) }
            },
            dismissButton = { TextButton({ deleting = null }) { Text("Отмена") } },
            containerColor = colors.surface,
        )
    }

    forwarding?.let { item ->
        val chats by telegram.chats.collectAsState()
        ModalBottomSheet({ forwarding = null }, containerColor = colors.surface) {
            Text("Переслать в…", color = colors.text, fontSize = 17.sp, modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp))
            LazyColumn(Modifier.heightIn(max = 480.dp)) {
                items(chats, key = { it.id }) { chat ->
                    Row(
                        Modifier.fillMaxWidth().clickable {
                            val ids = item.groupIds.ifEmpty { listOf(item.id) }.toLongArray()
                            scope.launch {
                                runCatching { telegram.call(TdApi.ForwardMessages(chat.id, null, chatId, ids, null, false, false)) }
                            }
                            forwarding = null
                        }.padding(horizontal = 16.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Avatar(chat.title, chat.photo, chat.colorIndex, 40.dp, kind = chat.kind)
                        Spacer(Modifier.width(12.dp))
                        Text(chat.title, color = colors.text, fontSize = 16.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                }
            }
        }
    }

    if (showAttach) {
        ModalBottomSheet({ showAttach = false }, containerColor = colors.surface) {
            Column(Modifier.windowInsetsPadding(WindowInsets.navigationBars)) {
                ActionRow(Icons.Filled.Photo, "Фото или видео") {
                    showAttach = false
                    photoPicker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageAndVideo))
                }
                ActionRow(Icons.Filled.InsertDriveFile, "Файл") {
                    showAttach = false
                    filePicker.launch(arrayOf("*/*"))
                }
            }
        }
    }
}

private fun replyMode(item: MessageItem): ComposerMode {
    val text = (item.body as? MessageBody.Text)?.text?.text ?: item.body.caption.text.ifEmpty { "Вложение" }
    return ComposerMode(item.id, false, item.sender?.name ?: "Ответ", text)
}

@Composable
private fun ActionRow(icon: ImageVector, title: String, onClick: () -> Unit) {
    val colors = Foxy.colors
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 20.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = colors.textSecondary)
        Spacer(Modifier.width(20.dp))
        Text(title, color = colors.text, fontSize = 16.sp)
    }
}

private fun openLink(context: Context, url: String) {
    val target = if (url.contains("://") || url.startsWith("tel:") || url.startsWith("mailto:") || url.startsWith("geo:")) url else "https://$url"
    runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(target))) }
        .onFailure { Toast.makeText(context, "Нет приложения для этой ссылки", Toast.LENGTH_SHORT).show() }
}

private fun openFile(context: Context, telegram: Telegram, fileId: Int, name: String, mime: String) {
    val path = telegram.files.observe(fileId).value.localPath ?: return
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", File(path))
    val intent = Intent(Intent.ACTION_VIEW).setDataAndType(uri, mime.ifBlank { "*/*" }).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    runCatching { context.startActivity(Intent.createChooser(intent, name)) }
}

private suspend fun sendAttachment(context: Context, session: ChatSession, uri: Uri, replyTo: Long?, asDocument: Boolean = false) {
    val file = copyToCache(context, uri) ?: return
    val mime = context.contentResolver.getType(uri).orEmpty()
    val local = TdApi.InputFileLocal(file.path)
    val content: TdApi.InputMessageContent = when {
        !asDocument && mime.startsWith("image/") ->
            TdApi.InputMessagePhoto(TdApi.InputPhoto(local, null, null, IntArray(0), 0, 0), null, false, null, false)
        !asDocument && mime.startsWith("video/") ->
            TdApi.InputMessageVideo(TdApi.InputVideo(local, null, null, 0, IntArray(0), 0, 0, 0, true), null, false, null, false)
        else -> TdApi.InputMessageDocument(TdApi.InputDocument(local, null, false), null)
    }
    runCatching { session.sendContent(content, replyTo) }
        .onFailure { Toast.makeText(context, "Не удалось отправить файл", Toast.LENGTH_SHORT).show() }
}

private fun copyToCache(context: Context, uri: Uri): File? = runCatching {
    val name = context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use {
        if (it.moveToFirst()) it.getString(0) else null
    } ?: "file"
    val directory = File(context.cacheDir, "upload/${System.currentTimeMillis()}").apply { mkdirs() }
    val target = File(directory, name.replace('/', '_'))
    context.contentResolver.openInputStream(uri)?.use { input -> target.outputStream().use { input.copyTo(it) } }
    target
}.getOrNull()

class VoiceResult(val path: String, val seconds: Int)

class VoiceRecorder(private val context: Context) {
    private var recorder: MediaRecorder? = null
    private var file: File? = null
    private var startedAt = 0L

    fun start() {
        val target = File(context.cacheDir, "voice-${System.currentTimeMillis()}.ogg")
        val media = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) MediaRecorder(context) else @Suppress("DEPRECATION") MediaRecorder()
        media.setAudioSource(MediaRecorder.AudioSource.MIC)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            media.setOutputFormat(MediaRecorder.OutputFormat.OGG)
            media.setAudioEncoder(MediaRecorder.AudioEncoder.OPUS)
        } else {
            media.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            media.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
        }
        media.setAudioEncodingBitRate(32_000)
        media.setAudioSamplingRate(48_000)
        media.setOutputFile(target.path)
        media.prepare()
        media.start()
        recorder = media
        file = target
        startedAt = System.currentTimeMillis()
    }

    fun stop(): VoiceResult? {
        val media = recorder ?: return null
        recorder = null
        val elapsed = ((System.currentTimeMillis() - startedAt) / 1000).toInt()
        return runCatching {
            media.stop()
            media.release()
            VoiceResult(file!!.path, elapsed)
        }.getOrElse {
            media.release()
            null
        }
    }
}

/** The tapped message, for the top of Brain's sheet. */
private fun brainPreview(item: MessageItem, chatTitle: String): BrainMessagePreview {
    val who = if (item.outgoing) "Вы" else item.sender?.name ?: chatTitle
    val text = (item.body as? MessageBody.Text)?.text?.text ?: item.body.caption.text
    return BrainMessagePreview(who, clockTime(item.date), text.ifBlank { "(no text)" })
}
