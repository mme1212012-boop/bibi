package com.bibi.android

object BoardDetector {
    fun detectTubeCenters(
        pixels: ByteArray,
        width: Int,
        height: Int,
        pixelStride: Int,
        rowPadding: Int,
    ): List<Pair<Float, Float>> {
        val minY = (height * 0.18f).toInt()
        val maxY = (height * 0.82f).toInt()
        val histogram = IntArray(width)

        for (y in minY until maxY) {
            val rowStart = y * (width * pixelStride + rowPadding)
            for (x in 0 until width) {
                val offset = rowStart + x * pixelStride
                if (offset + 3 >= pixels.size) continue
                val r = pixels[offset].toInt() and 0xff
                val g = pixels[offset + 1].toInt() and 0xff
                val b = pixels[offset + 2].toInt() and 0xff
                val max = maxOf(r, g, b)
                val min = minOf(r, g, b)
                if (max - min >= 38 && max >= 90) histogram[x]++
            }
        }

        val threshold = (height * 0.035f).toInt()
        val peaks = mutableListOf<Int>()
        var start = -1
        for (x in width / 20 until width * 19 / 20) {
            if (histogram[x] >= threshold && start < 0) start = x
            if ((histogram[x] < threshold || x == width * 19 / 20 - 1) && start >= 0) {
                val end = x
                val center = (start + end) / 2
                peaks.add(center)
                start = -1
            }
        }

        val separated = mutableListOf<Int>()
        for (x in peaks) {
            if (separated.isEmpty() || x - separated.last() > width / 30) {
                separated.add(x)
            }
        }
        if (separated.size < 3 || separated.size > 24) return emptyList()

        val mouthY = (height * 0.72f)
        return separated.map { Pair(it.toFloat(), mouthY) }
    }
}
