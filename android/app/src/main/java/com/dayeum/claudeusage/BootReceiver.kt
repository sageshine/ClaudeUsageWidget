package com.dayeum.claudeusage

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.content.ContextCompat

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED && SecureStore.hasCredentials(context)) {
            ContextCompat.startForegroundService(context, Intent(context, UsageForegroundService::class.java))
        }
    }
}
