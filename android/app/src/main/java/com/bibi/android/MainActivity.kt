package com.bibi.android

import android.app.Activity
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    private lateinit var statusText: TextView

    private val projectionLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode == Activity.RESULT_OK && result.data != null) {
                statusText.text = "Đang chụp và phân tích màn hình..."
                CaptureService.start(this, result.resultCode, result.data!!)
            } else {
                statusText.text = "Người dùng đã hủy quyền chụp màn hình"
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusText = findViewById(R.id.statusText)
        findViewById<Button>(R.id.overlayButton).setOnClickListener {
            startActivity(
                Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:$packageName"),
                ),
            )
        }
        findViewById<Button>(R.id.accessibilityButton).setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }
        findViewById<Button>(R.id.captureButton).setOnClickListener {
            val manager = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
            projectionLauncher.launch(manager.createScreenCaptureIntent())
        }
        findViewById<Button>(R.id.stopButton).setOnClickListener {
            CaptureService.stop(this)
            statusText.text = "Đã dừng"
        }
    }

    override fun onResume() {
        super.onResume()
        statusText.text =
            if (BibiAccessibilityService.instance != null) {
                "Accessibility đã sẵn sàng"
            } else {
                "Chưa bắt đầu"
            }
    }
}
