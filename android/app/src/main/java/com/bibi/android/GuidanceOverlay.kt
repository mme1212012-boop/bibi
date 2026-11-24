package com.bibi.android

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.view.View

class GuidanceOverlay(context: Context) : View(context) {
    var sourceIndex = -1
    var targetIndex = -1
    var tubeCenters = emptyList<Pair<Float, Float>>()
    var guidanceText = "Đang chờ dữ liệu bàn..."

    private val redPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 8f
        color = Color.RED
    }
    private val greenPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 8f
        color = Color.GREEN
    }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        textSize = 48f
        color = Color.WHITE
        setShadowLayer(8f, 0f, 0f, Color.BLACK)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        tubeCenters.forEachIndexed { index, point ->
            val paint = when (index) {
                sourceIndex -> redPaint
                targetIndex -> greenPaint
                else -> return@forEachIndexed
            }
            canvas.drawCircle(point.first, point.second, 34f, paint)
        }
        canvas.drawText(guidanceText, 40f, 80f, textPaint)
    }
}
