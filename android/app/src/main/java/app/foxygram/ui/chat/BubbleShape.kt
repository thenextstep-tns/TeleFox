package app.foxygram.ui.chat

import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.RoundRect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Outline
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathOperation
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp

val BubbleLarge = 17.dp
val BubbleSmall = 6.dp
val TailWidth = 7.dp

/**
 * Message bubble with the small hooked tail on the last message of a group.
 * Corners next to a neighbour from the same sender are tightened so a run reads as one block.
 */
class BubbleShape(
    private val outgoing: Boolean,
    private val startsGroup: Boolean,
    private val endsGroup: Boolean,
    private val tail: Boolean = endsGroup,
    private val large: Dp = BubbleLarge,
    private val small: Dp = BubbleSmall,
) : Shape {
    override fun createOutline(size: Size, layoutDirection: LayoutDirection, density: Density): Outline {
        val l = with(density) { large.toPx() }
        val s = with(density) { small.toPx() }
        val tailW = if (tail) with(density) { TailWidth.toPx() } else 0f
        val left = if (!outgoing) tailW else 0f
        val right = if (outgoing) size.width - tailW else size.width

        val topInner = if (startsGroup) l else s
        val bottomInner = if (endsGroup) (if (tail) 0f else l) else s
        val rect = if (outgoing) {
            RoundRect(
                left, 0f, right, size.height,
                topLeftCornerRadius = CornerRadius(l), topRightCornerRadius = CornerRadius(topInner),
                bottomRightCornerRadius = CornerRadius(bottomInner), bottomLeftCornerRadius = CornerRadius(l),
            )
        } else {
            RoundRect(
                left, 0f, right, size.height,
                topLeftCornerRadius = CornerRadius(topInner), topRightCornerRadius = CornerRadius(l),
                bottomRightCornerRadius = CornerRadius(l), bottomLeftCornerRadius = CornerRadius(bottomInner),
            )
        }
        val body = Path().apply { addRoundRect(rect) }
        if (tail) {
            val h = size.height
            val tailH = with(density) { 12.dp.toPx() }
            val hook = Path().apply {
                if (outgoing) {
                    moveTo(right, h - tailH)
                    quadraticTo(right + 0.1f * tailW, h - 0.2f * tailH, size.width, h)
                    lineTo(right - tailH * 0.8f, h)
                    close()
                } else {
                    moveTo(left, h - tailH)
                    quadraticTo(left - 0.1f * tailW, h - 0.2f * tailH, 0f, h)
                    lineTo(left + tailH * 0.8f, h)
                    close()
                }
            }
            return Outline.Generic(Path.combine(PathOperation.Union, body, hook))
        }
        return Outline.Generic(body)
    }

    override fun equals(other: Any?) = other is BubbleShape && other.outgoing == outgoing &&
        other.startsGroup == startsGroup && other.endsGroup == endsGroup && other.tail == tail

    override fun hashCode() = listOf(outgoing, startsGroup, endsGroup, tail).hashCode()
}
