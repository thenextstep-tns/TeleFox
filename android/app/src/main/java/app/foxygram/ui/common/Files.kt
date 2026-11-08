package app.foxygram.ui.common

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import app.foxygram.model.ImageRef
import app.foxygram.ui.theme.Foxy
import coil.compose.AsyncImage
import coil.request.ImageRequest
import java.io.File

/** Download state of one Telegram file. */
data class FileState(
    val localPath: String? = null,
    val complete: Boolean = false,
    val downloaded: Long = 0,
    val total: Long = 0,
    val downloading: Boolean = false,
) {
    val progress: Float get() = if (total > 0) (downloaded.toFloat() / total).coerceIn(0f, 1f) else 0f
}

/** Lets screens ask for files without knowing about TDLib, so they can be drawn in tests. */
interface FileProvider {
    fun observe(fileId: Int): State<FileState>
    fun download(fileId: Int, priority: Int)
    fun cancel(fileId: Int)
}

object NoFiles : FileProvider {
    private val empty = mutableStateOf(FileState())
    override fun observe(fileId: Int): State<FileState> = empty
    override fun download(fileId: Int, priority: Int) = Unit
    override fun cancel(fileId: Int) = Unit
}

val LocalFiles = compositionLocalOf<FileProvider> { NoFiles }

/** The tiny embedded preview first, swapped for the real picture once it is on disk. */
@Composable
fun TelegramImage(
    image: ImageRef,
    modifier: Modifier = Modifier,
    contentScale: ContentScale = ContentScale.Crop,
    autoDownload: Boolean = true,
    priority: Int = 8,
) {
    val files = LocalFiles.current
    val state by files.observe(image.fileId)
    if (autoDownload && image.fileId != 0 && !state.complete) {
        androidx.compose.runtime.LaunchedEffect(image.fileId) { files.download(image.fileId, priority) }
    }
    val mini = remember(image.fileId) {
        image.mini?.let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() }
    }
    Box(modifier.background(Foxy.colors.surfaceHigh)) {
        if (mini != null && !state.complete) {
            Image(mini, null, Modifier.fillMaxSize().blur(8.dp), contentScale = ContentScale.Crop)
        }
        val path = state.localPath
        if (state.complete && path != null) {
            val context = LocalContext.current
            val request = remember(path) {
                ImageRequest.Builder(context).data(File(path)).crossfade(120).build()
            }
            AsyncImage(request, null, Modifier.fillMaxSize(), contentScale = contentScale)
        }
    }
}
