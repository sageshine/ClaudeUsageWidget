package com.dayeum.claudeusage

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.RadioGroup
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputEditText

class MainActivity : AppCompatActivity() {

    private lateinit var sessionKeyInput: TextInputEditText
    private lateinit var orgIdInput: TextInputEditText
    private lateinit var statusText: TextView
    private lateinit var headlineMetricGroup: RadioGroup

    private val notificationPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) startServiceIfReady()
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        sessionKeyInput = findViewById(R.id.sessionKeyInput)
        orgIdInput = findViewById(R.id.orgIdInput)
        statusText = findViewById(R.id.statusText)
        headlineMetricGroup = findViewById(R.id.headlineMetricGroup)

        SecureStore.sessionKey(this)?.let { sessionKeyInput.setText(it) }
        SecureStore.orgId(this)?.let { orgIdInput.setText(it) }

        headlineMetricGroup.check(idForMetric(AppSettings.headlineMetric(this)))
        headlineMetricGroup.setOnCheckedChangeListener { _, checkedId ->
            AppSettings.setHeadlineMetric(this, metricForId(checkedId))
            requestImmediateRefresh()
        }

        findViewById<MaterialButton>(R.id.startButton).setOnClickListener {
            val sessionKey = sessionKeyInput.text?.toString()?.trim().orEmpty()
            val orgId = orgIdInput.text?.toString()?.trim().orEmpty()
            if (sessionKey.isEmpty() || orgId.isEmpty()) {
                statusText.text = "sessionKey와 Organization ID를 모두 입력하세요"
                return@setOnClickListener
            }
            SecureStore.saveCredentials(this, sessionKey, orgId)
            if (SecureStore.isDisclaimerAcked(this)) {
                requestPermissionAndStart()
            } else {
                showDisclaimer { requestPermissionAndStart() }
            }
        }

        findViewById<MaterialButton>(R.id.stopButton).setOnClickListener {
            stopService(Intent(this, UsageForegroundService::class.java))
            statusText.text = getString(R.string.status_stopped)
        }

        if (!SecureStore.isDisclaimerAcked(this)) {
            showDisclaimer { }
        }
    }

    private fun idForMetric(metric: String): Int = when (metric) {
        HEADLINE_SESSION -> R.id.metricSession
        HEADLINE_WEEKLY -> R.id.metricWeekly
        else -> R.id.metricMax
    }

    private fun metricForId(id: Int): String = when (id) {
        R.id.metricSession -> HEADLINE_SESSION
        R.id.metricWeekly -> HEADLINE_WEEKLY
        else -> HEADLINE_MAX
    }

    /** 이미 실행 중인 서비스가 있다면 3분을 기다리지 않고 바로 새 설정으로 다시 그리게 한다. */
    private fun requestImmediateRefresh() {
        if (!SecureStore.hasCredentials(this)) return
        val intent = Intent(this, UsageForegroundService::class.java).setAction(UsageForegroundService.ACTION_REFRESH_UI)
        ContextCompat.startForegroundService(this, intent)
    }

    private fun showDisclaimer(onAck: () -> Unit) {
        AlertDialog.Builder(this)
            .setTitle(R.string.disclaimer_title)
            .setMessage(R.string.disclaimer_body)
            .setCancelable(false)
            .setPositiveButton(R.string.disclaimer_confirm) { _, _ ->
                SecureStore.setDisclaimerAcked(this)
                onAck()
            }
            .show()
    }

    private fun requestPermissionAndStart() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            startServiceIfReady()
        }
    }

    private fun startServiceIfReady() {
        if (!SecureStore.hasCredentials(this)) return
        ContextCompat.startForegroundService(this, Intent(this, UsageForegroundService::class.java))
        statusText.text = getString(R.string.status_running)
    }
}
