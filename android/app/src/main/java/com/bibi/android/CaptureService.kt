package com.bibi.android

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.IBinder
import android.provider.Settings
import android.view.Gravity
import android.view.WindowManager

class CaptureService : Service() {
    private var projection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var imageReader: ImageReader? = null
    private var overlayWindow: WindowManager? = null
    private var overlayView: GuidanceOverlay? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }

        val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, 0) ?: 0
        val data = intent?.getParcelableExtra<Intent>(EXTRA_RESULT_DATA)
        if (resultCode == 0 || data == null) {
            stopSelf()
            return START_NOT_STICKY
        }

        startForeground(1001, createNotification())
        val manager = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        projection = manager.getMediaProjection(resultCode, data)
        startCapture()
        addOverlay()
        return START_STICKY
    }

    private fun startCapture() {
        val metrics = resources.displayMetrics
        val width = metrics.widthPixels
        val height = metrics.heightPixels
        val density = metrics.densityDpi
        imageReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
        virtualDisplay = projection?.createVirtualDisplay(
            "BibiCapture",
            width,
            height,
            density,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            imageReader!!.surface,
            null,
            null,
        )
        val reader = imageReader!!
        reader.setOnImageAvailableListener({ availableReader ->
            val image = availableReader.acquireLatestImage() ?: return@setOnImageAvailableListener
            val plane = image.planes[0]
            val rowPadding = plane.rowStride - plane.pixelStride * image.width
            val buffer = plane.buffer
            val rowBytes = image.width * plane.pixelStride + rowPadding
            val pixels = ByteArray(rowBytes * image.height)
            buffer.get(pixels)
            val centers = BoardDetector.detectTubeCenters(
                pixels,
                image.width,
                image.height,
                plane.pixelStride,
                rowPadding,
            )
            overlayView?.tubeCenters = centers
            overlayView?.guidanceText =
                if (centers.isEmpty()) "Đang tìm bàn Water Sort..." else "Đã tìm thấy ${centers.size} ống"
            overlayView?.postInvalidate()
            image.close()
        }, android.os.Handler(android.os.Looper.getMainLooper()))
    }

    private fun addOverlay() {
        if (!Settings.canDrawOverlays(this)) return
        val view = GuidanceOverlay(this)
        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
        }
        overlayWindow = getSystemService(WINDOW_SERVICE) as WindowManager
        overlayWindow?.addView(view, params)
        overlayView = view
    }

    private fun createNotification(): Notification {
        val channelId = "bibi_capture"
        if (Build.VERSION.SDK_INT >= 26) {
            val channel = NotificationChannel(
                channelId,
                "Bibi đang chụp màn hình",
                NotificationManager.IMPORTANCE_LOW,
            )
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
        return Notification.Builder(this, channelId)
            .setContentTitle("Bibi đang chạy")
            .setContentText("Chế độ hướng dẫn Water Sort")
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .build()
    }

    override fun onDestroy() {
        overlayView?.let { overlayWindow?.removeView(it) }
        virtualDisplay?.release()
        imageReader?.close()
        projection?.stop()
        super.onDestroy()
    }

    companion object {
        const val ACTION_STOP = "com.bibi.android.STOP_CAPTURE"
        const val EXTRA_RESULT_CODE = "result_code"
        const val EXTRA_RESULT_DATA = "result_data"

        fun start(context: Context, resultCode: Int, data: Intent) {
            val intent = Intent(context, CaptureService::class.java).apply {
                putExtra(EXTRA_RESULT_CODE, resultCode)
                putExtra(EXTRA_RESULT_DATA, data)
            }
            if (Build.VERSION.SDK_INT >= 26) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            context.startService(
                Intent(context, CaptureService::class.java).apply { action = ACTION_STOP },
            )
        }
    }
}
