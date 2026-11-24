package com.dayeum.claudeusage

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class UsageForegroundService : Service() {

    private var job: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO)
    private var lastState: WidgetState = WidgetState(Mood.SETUP_NEEDED, 0, "불러오는 중...")
    private var lastSnapshot: UsageSnapshot? = null

    companion object {
        const val CHANNEL_ID = "usage_channel"
        const val NOTIFICATION_ID = 1001
        // 데스크톱 위젯과 동일한 3분 주기.
        const val REFRESH_INTERVAL_MS = 3 * 60 * 1000L
        // 일시 오류 뒤에는 3분을 기다리지 않고 빨리 다시 시도한다.
        const val RETRY_INTERVAL_MS = 30 * 1000L
        const val ACTION_STOP = "com.dayeum.claudeusage.STOP"
        // Android 13+부터는 setOngoing(true)를 걸어도 사용자가 스와이프로 지울 수 있다.
        // 지워지는 즉시(deleteIntent) 곧바로 다시 띄워서 "안 지워지는" 것처럼 만든다.
        const val ACTION_REPOST = "com.dayeum.claudeusage.REPOST"
        // 표시 지표(세션/주간) 설정을 바꾼 직후, 다음 3분 주기를 기다리지 않고
        // 마지막으로 받아온 값으로 즉시 다시 계산해서 보여준다.
        const val ACTION_REFRESH_UI = "com.dayeum.claudeusage.REFRESH_UI"
    }

    override fun onCreate() {
        super.onCreate()
        createChannel()
        // 프로세스가 죽었다 되살아난 경우에도 "?"가 아니라 마지막으로 보이던 숫자부터 띄운다.
        val cached = UsageCache.load(applicationContext)
        if (cached.mood != Mood.SETUP_NEEDED && cached.mood != Mood.AUTH_ERROR) lastState = cached
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopSelf()
                return START_NOT_STICKY
            }
            ACTION_REPOST -> {
                startForeground(NOTIFICATION_ID, buildNotification(lastState))
                updateNotification(lastState)
                return START_STICKY
            }
            ACTION_REFRESH_UI -> {
                val metric = AppSettings.headlineMetric(applicationContext)
                val snapshot = lastSnapshot
                val state = if (snapshot != null) {
                    WidgetStateCalculator.resolve(FetchResult.Success(snapshot), metric)
                } else {
                    lastState
                }
                startForeground(NOTIFICATION_ID, buildNotification(state))
                updateNotification(state)
                startLoop()
                return START_STICKY
            }
        }
        startForeground(NOTIFICATION_ID, buildNotification(lastState))
        startLoop()
        return START_STICKY
    }

    private fun startLoop() {
        if (job?.isActive == true) return
        job = scope.launch {
            while (true) {
                var nextDelay = REFRESH_INTERVAL_MS
                try {
                    val sessionKey = SecureStore.sessionKey(applicationContext)
                    val orgId = SecureStore.orgId(applicationContext)
                    val metric = AppSettings.headlineMetric(applicationContext)
                    val result = if (sessionKey.isNullOrBlank() || orgId.isNullOrBlank()) {
                        null
                    } else {
                        ApiClient.fetchUsage(sessionKey, orgId)
                    }
                    if (result is FetchResult.Success) {
                        lastSnapshot = result.snapshot
                    }
                    val state = if (result is FetchResult.TransientError && hasLastValue()) {
                        // 네트워크 일시 오류: 0%로 덮어쓰지 않고 마지막 값을 그대로 보여준다.
                        nextDelay = RETRY_INTERVAL_MS
                        lastSnapshot?.let { WidgetStateCalculator.resolve(FetchResult.Success(it), metric) } ?: lastState
                    } else {
                        if (result is FetchResult.TransientError) nextDelay = RETRY_INTERVAL_MS
                        WidgetStateCalculator.resolve(result, metric)
                    }
                    updateNotification(state)
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Throwable) {
                    // 예기치 못한 예외 하나로 갱신 루프 전체가 조용히 죽으면 알림 숫자가 영영 멈춘다.
                    nextDelay = RETRY_INTERVAL_MS
                }
                delay(nextDelay)
            }
        }
    }

    private fun hasLastValue(): Boolean =
        lastSnapshot != null || lastState.mood in setOf(Mood.CALM, Mood.WARNING, Mood.DANGER)

    private fun updateNotification(state: WidgetState) {
        lastState = state
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, buildNotification(state))
        UsageWidgetProvider.pushUpdate(applicationContext, state)
    }

    private fun buildNotification(state: WidgetState): Notification {
        val title = when (state.mood) {
            Mood.CALM -> "${state.metricLabel} ${state.headlinePercent}%"
            Mood.WARNING -> "${state.metricLabel} ${state.headlinePercent}% · 주의"
            Mood.DANGER -> "${state.metricLabel} ${state.headlinePercent}% · 위험"
            Mood.AUTH_ERROR -> "재로그인 필요"
            Mood.SETUP_NEEDED -> "설정 필요"
        }
        val color = when (state.mood) {
            Mood.CALM -> getColor(R.color.calm)
            Mood.WARNING -> getColor(R.color.warning)
            Mood.DANGER, Mood.AUTH_ERROR -> getColor(R.color.danger)
            Mood.SETUP_NEEDED -> getColor(R.color.calm)
        }

        val openIntent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val stopIntent = PendingIntent.getService(
            this, 1,
            Intent(this, UsageForegroundService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val deleteIntent = PendingIntent.getService(
            this, 2,
            Intent(this, UsageForegroundService::class.java).setAction(ACTION_REPOST),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(NotificationIconFactory.forState(state))
            .setContentTitle(title)
            .setContentText(state.tooltip)
            .setColor(color)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setContentIntent(openIntent)
            .setDeleteIntent(deleteIntent)
            .addAction(0, "중지", stopIntent)
            .build()
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.notification_channel_name),
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    override fun onDestroy() {
        job?.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
