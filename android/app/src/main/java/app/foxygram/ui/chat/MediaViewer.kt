package app.foxygram.ui.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.ui.PlayerView
import app.foxygram.model.MessageBody
import app.foxygram.td.Telegram
import app.foxygram.td.buildTelegramPlayer
import app.foxygram.td.playTelegramFile
import app.foxygram.ui.common.TelegramImage

private const val MAX_ZOOM = 5f

@Composable
fun MediaViewer(telegram: Telegram, body: MessageBody, onClose: () -> Unit) {
    Box(Modifier.fillMaxSize().background(Color.Black)) {
        when (body) {
            is MessageBody.Photo -> ZoomablePhoto(body)
            is MessageBody.Video -> VideoPlayer(telegram, body.fileId, loop = body.isGif)
            is MessageBody.Round -> VideoPlayer(telegram, body.fileId, loop = false)
            else -> Unit
        }
        IconButton(onClose, Modifier.align(Alignment.TopStart).windowInsetsPadding(WindowInsets.statusBars)) {
            Icon(Icons.Filled.Close, "Закрыть", tint = Color.White)
        }
    }
}

@Composable
private fun ZoomablePhoto(body: MessageBody.Photo) {
    var scale by remember { mutableFloatStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    val state = rememberTransformableState { zoom, pan, _ ->
        scale = (scale * zoom).coerceIn(1f, MAX_ZOOM)
        offset = if (scale > 1f) offset + pan else Offset.Zero
    }
    TelegramImage(
        body.image,
        Modifier.fillMaxSize().transformable(state).graphicsLayer {
            scaleX = scale
            scaleY = scale
            translationX = offset.x
            translationY = offset.y
        },
        ContentScale.Fit,
        priority = 32,
    )
}

@androidx.annotation.OptIn(UnstableApi::class)
@Composable
private fun VideoPlayer(telegram: Telegram, fileId: Int, loop: Boolean) {
    val context = LocalContext.current
    val player = remember(fileId) {
        buildTelegramPlayer(context).apply {
            repeatMode = if (loop) Player.REPEAT_MODE_ALL else Player.REPEAT_MODE_OFF
            playTelegramFile(telegram, fileId)
        }
    }
    DisposableEffect(player) { onDispose { player.release() } }
    AndroidView(
        factory = { PlayerView(it).apply { this.player = player; setShowNextButton(false); setShowPreviousButton(false) } },
        modifier = Modifier.fillMaxSize(),
    )
}
