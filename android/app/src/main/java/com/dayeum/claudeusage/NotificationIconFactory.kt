package com.dayeum.claudeusage

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import androidx.core.graphics.drawable.IconCompat

/**
 * 상태바 작은 아이콘은 시스템이 항상 흰색 실루엣으로만 그린다(색은 못 씀).
 * 그래서 퍼센트 숫자를 직접 비트맵으로 그려서 아이콘으로 쓴다 -- 배터리/신호
 * 표시줄의 숫자 배지와 같은 방식.
 */
object NotificationIconFactory {
    private const val SIZE = 96

    private fun textIcon(text: String): IconCompat {
        val bitmap = Bitmap.createBitmap(SIZE, SIZE, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            typeface = Typeface.DEFAULT_BOLD
            textAlign = Paint.Align.CENTER
            textSize = when (text.length) {
                1 -> SIZE * 0.62f
                2 -> SIZE * 0.52f
                else -> SIZE * 0.40f
            }
        }
        val y = SIZE / 2f - (paint.descent() + paint.ascent()) / 2f
        canvas.drawText(text, SIZE / 2f, y, paint)
        return IconCompat.createWithBitmap(bitmap)
    }

    fun forState(state: WidgetState): IconCompat = when (state.mood) {
        Mood.CALM, Mood.WARNING, Mood.DANGER -> textIcon(state.headlinePercent.coerceIn(0, 99).toString())
        Mood.AUTH_ERROR -> textIcon("!")
        Mood.SETUP_NEEDED -> textIcon("?")
    }
}
