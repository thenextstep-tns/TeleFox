package app.foxygram.td

import android.content.Context
import android.net.Uri
import androidx.annotation.OptIn
import androidx.compose.runtime.State
import androidx.compose.runtime.mutableStateOf
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackParameters
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.BaseDataSource
import androidx.media3.datasource.DataSpec
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.ProgressiveMediaSource
import app.foxygram.ui.chat.AudioController
import app.foxygram.ui.chat.PlaybackState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.drinkless.tdlib.TdApi
import java.io.RandomAccessFile

private const val STREAM_PRIORITY = 32
private const val WAIT_FOR_DATA_MS = 50L
private const val POSITION_TICK_MS = 100L
private val SPEEDS = listOf(1f, 1.5f, 2f)

fun telegramFileUri(fileId: Int): Uri = Uri.parse("td://file/$fileId")

/** Reads a Telegram file while TDLib downloads it, so playback starts before the download ends. */
@OptIn(UnstableApi::class)
class TdDataSource(private val telegram: Telegram) : BaseDataSource(true) {
    private var uri: Uri? = null
    private var fileId = 0
    private var position = 0L
    private var remaining = 0L
    private var input: RandomAccessFile? = null

    override fun open(dataSpec: DataSpec): Long {
        transferInitializing(dataSpec)
        uri = dataSpec.uri
        fileId = dataSpec.uri.lastPathSegment?.toIntOrNull() ?: throw java.io.IOException("bad file uri")
        position = dataSpec.position
        val file = runBlocking {
            telegram.call(TdApi.DownloadFile(fileId, STREAM_PRIORITY, position, 0, false))
        }
        val size = if (file.size > 0) file.size else file.expectedSize
        remaining = when {
            dataSpec.length != C.LENGTH_UNSET.toLong() -> dataSpec.length
            size > 0 -> size - position
            else -> C.LENGTH_UNSET.toLong()
        }
        transferStarted(dataSpec)
        return remaining
    }

    override fun read(buffer: ByteArray, offset: Int, length: Int): Int {
        if (length == 0) return 0
        if (remaining == 0L) return C.RESULT_END_OF_INPUT
        var available: Long
        while (true) {
            if (Thread.interrupted()) throw java.io.InterruptedIOException()
            available = runBlocking { telegram.call(TdApi.GetFileDownloadedPrefixSize(fileId, position)).size }
            if (available > 0) break
            val file = runBlocking { telegram.call(TdApi.GetFile(fileId)) }
            if (file.local.isDownloadingCompleted && file.local.downloadedSize <= position) return C.RESULT_END_OF_INPUT
            if (!file.local.isDownloadingActive) {
                runBlocking { telegram.call(TdApi.DownloadFile(fileId, STREAM_PRIORITY, position, 0, false)) }
            }
            Thread.sleep(WAIT_FOR_DATA_MS)
        }
        val stream = input ?: run {
            val path = runBlocking { telegram.call(TdApi.GetFile(fileId)).local.path }
            RandomAccessFile(path, "r").also { input = it }
        }
        stream.seek(position)
        val toRead = minOf(available, length.toLong(), if (remaining > 0) remaining else Long.MAX_VALUE).toInt()
        val count = stream.read(buffer, offset, toRead)
        if (count < 0) return C.RESULT_END_OF_INPUT
        position += count
        if (remaining > 0) remaining -= count
        bytesTransferred(count)
        return count
    }

    override fun getUri(): Uri? = uri

    override fun close() {
        input?.close()
        input = null
        if (uri != null) {
            uri = null
            transferEnded()
        }
    }
}

@OptIn(UnstableApi::class)
fun buildTelegramPlayer(context: Context): ExoPlayer = ExoPlayer.Builder(context).build().also {
    it.setHandleAudioBecomingNoisy(true)
    it.repeatMode = Player.REPEAT_MODE_OFF
}

@OptIn(UnstableApi::class)
fun ExoPlayer.playTelegramFile(telegram: Telegram, fileId: Int) {
    val source = ProgressiveMediaSource.Factory({ TdDataSource(telegram) })
        .createMediaSource(MediaItem.fromUri(telegramFileUri(fileId)))
    setMediaSource(source)
    prepare()
    playWhenReady = true
}

/** Voice messages and music. Only the UI holds it, so nothing plays or polls in the background unless audio is on. */
class TdAudioController(private val context: Context, private val telegram: Telegram) : AudioController {
    private val _state = mutableStateOf(PlaybackState())
    override val state: State<PlaybackState> = _state

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var ticker: Job? = null
    private var player: ExoPlayer? = null

    private fun player(): ExoPlayer = player ?: buildTelegramPlayer(context).also { created ->
        player = created
        created.addListener(object : Player.Listener {
            override fun onEvents(p: Player, events: Player.Events) {
                publish()
                if (p.isPlaying) startTicker() else stopTicker()
                if (p.playbackState == Player.STATE_ENDED) {
                    _state.value = _state.value.copy(playing = false, positionMs = 0)
                    p.seekTo(0)
                    p.pause()
                }
            }
        })
    }

    private fun publish() {
        val p = player ?: return
        _state.value = _state.value.copy(
            playing = p.isPlaying,
            loading = p.playbackState == Player.STATE_BUFFERING,
            positionMs = p.currentPosition.coerceAtLeast(0),
            durationMs = if (p.duration > 0) p.duration else _state.value.durationMs,
        )
    }

    private fun startTicker() {
        if (ticker?.isActive == true) return
        ticker = scope.launch {
            while (isActive) {
                publish()
                delay(POSITION_TICK_MS)
            }
        }
    }

    private fun stopTicker() {
        ticker?.cancel()
        ticker = null
    }

    override fun toggle(fileId: Int, durationSeconds: Int) {
        val p = player()
        if (_state.value.fileId == fileId) {
            if (p.isPlaying) p.pause() else p.play()
            return
        }
        _state.value = PlaybackState(fileId = fileId, durationMs = durationSeconds * 1000L, speed = _state.value.speed, loading = true)
        p.playTelegramFile(telegram, fileId)
        p.playbackParameters = PlaybackParameters(_state.value.speed)
    }

    override fun seek(fraction: Float) {
        val p = player ?: return
        if (p.duration > 0) p.seekTo((p.duration * fraction).toLong())
    }

    override fun cycleSpeed() {
        val next = SPEEDS[(SPEEDS.indexOf(_state.value.speed) + 1) % SPEEDS.size]
        _state.value = _state.value.copy(speed = next)
        player?.playbackParameters = PlaybackParameters(next)
    }

    fun release() {
        stopTicker()
        player?.release()
        player = null
    }
}
