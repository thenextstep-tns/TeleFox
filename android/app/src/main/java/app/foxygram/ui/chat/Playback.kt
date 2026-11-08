package app.foxygram.ui.chat

import androidx.compose.runtime.State
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.mutableStateOf

data class PlaybackState(
    val fileId: Int = 0,
    val playing: Boolean = false,
    val positionMs: Long = 0,
    val durationMs: Long = 0,
    val speed: Float = 1f,
    val loading: Boolean = false,
)

/** Audio in the chat. An interface so bubbles can be drawn in tests without a real player. */
interface AudioController {
    val state: State<PlaybackState>
    fun toggle(fileId: Int, durationSeconds: Int)
    fun seek(fraction: Float)
    fun cycleSpeed()
}

object NoAudio : AudioController {
    override val state = mutableStateOf(PlaybackState())
    override fun toggle(fileId: Int, durationSeconds: Int) = Unit
    override fun seek(fraction: Float) = Unit
    override fun cycleSpeed() = Unit
}

val LocalAudio = compositionLocalOf<AudioController> { NoAudio }
