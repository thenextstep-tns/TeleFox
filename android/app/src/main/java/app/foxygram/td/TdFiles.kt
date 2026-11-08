package app.foxygram.td

import androidx.compose.runtime.MutableState
import androidx.compose.runtime.State
import androidx.compose.runtime.mutableStateOf
import app.foxygram.ui.common.FileProvider
import app.foxygram.ui.common.FileState
import kotlinx.coroutines.launch
import org.drinkless.tdlib.TdApi
import java.util.concurrent.ConcurrentHashMap

class TdFiles(private val telegram: Telegram) : FileProvider {
    private val states = ConcurrentHashMap<Int, MutableState<FileState>>()

    private fun stateOf(fileId: Int): MutableState<FileState> = states.getOrPut(fileId) { mutableStateOf(FileState()) }

    fun onFile(file: TdApi.File) {
        stateOf(file.id).value = FileState(
            localPath = file.local.path.ifEmpty { null },
            complete = file.local.isDownloadingCompleted,
            downloaded = file.local.downloadedSize,
            total = if (file.size > 0) file.size else file.expectedSize,
            downloading = file.local.isDownloadingActive,
        )
    }

    override fun observe(fileId: Int): State<FileState> {
        val known = states.containsKey(fileId)
        val state = stateOf(fileId)
        if (!known && fileId != 0) {
            telegram.scope.launch { runCatching { onFile(telegram.call(TdApi.GetFile(fileId))) } }
        }
        return state
    }

    override fun download(fileId: Int, priority: Int) {
        if (fileId != 0) telegram.fire(TdApi.DownloadFile(fileId, priority, 0, 0, false))
    }

    override fun cancel(fileId: Int) {
        telegram.fire(TdApi.CancelDownloadFile(fileId, false))
    }
}
