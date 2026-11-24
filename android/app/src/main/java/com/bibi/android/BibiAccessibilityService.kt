package com.bibi.android

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.view.accessibility.AccessibilityEvent

class BibiAccessibilityService : AccessibilityService() {
    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    override fun onInterrupt() = Unit

    override fun onServiceConnected() {
        instance = this
    }

    override fun onDestroy() {
        if (instance === this) instance = null
        super.onDestroy()
    }

    fun tap(x: Float, y: Float): Boolean {
        val path = Path().apply { moveTo(x, y) }
        val stroke = GestureDescription.StrokeDescription(path, 0, 90)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()
        return dispatchGesture(
            gesture,
            object : GestureResultCallback() {},
            null,
        )
    }

    companion object {
        var instance: BibiAccessibilityService? = null

        fun tapIfEnabled(x: Float, y: Float): Boolean =
            instance?.tap(x, y) ?: false
    }
}
