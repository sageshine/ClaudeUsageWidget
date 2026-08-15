package com.dayeum.claudeusage

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import androidx.core.content.ContextCompat

class UsageWidgetProvider : AppWidgetProvider() {

    override fun onUpdate(context: Context, appWidgetManager: AppWidgetManager, appWidgetIds: IntArray) {
        val state = UsageCache.load(context)
        for (id in appWidgetIds) {
            appWidgetManager.updateAppWidget(id, buildViews(context, state))
        }
    }

    companion object {
        fun buildViews(context: Context, state: WidgetState): RemoteViews {
            val views = RemoteViews(context.packageName, R.layout.widget_usage)

            val percentText = when (state.mood) {
                Mood.AUTH_ERROR -> "!"
                Mood.SETUP_NEEDED -> "?"
                else -> "${state.headlinePercent}%"
            }
            views.setTextViewText(R.id.widgetPercent, percentText)

            val label = when (state.mood) {
                Mood.AUTH_ERROR -> "재로그인 필요"
                Mood.SETUP_NEEDED -> "설정 필요"
                else -> "Claude 사용량"
            }
            views.setTextViewText(R.id.widgetLabel, label)

            val color = when (state.mood) {
                Mood.CALM -> ContextCompat.getColor(context, R.color.calm)
                Mood.WARNING -> ContextCompat.getColor(context, R.color.warning)
                Mood.DANGER, Mood.AUTH_ERROR -> ContextCompat.getColor(context, R.color.danger)
                Mood.SETUP_NEEDED -> ContextCompat.getColor(context, R.color.calm)
            }
            views.setTextColor(R.id.widgetPercent, color)

            val openIntent = PendingIntent.getActivity(
                context, 0,
                Intent(context, MainActivity::class.java),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
            )
            views.setOnClickPendingIntent(R.id.widgetRoot, openIntent)
            return views
        }

        /** 포그라운드 서비스가 새 값을 받아올 때마다 호출해서 홈화면 위젯도 같이 갱신한다. */
        fun pushUpdate(context: Context, state: WidgetState) {
            UsageCache.save(context, state)
            val manager = AppWidgetManager.getInstance(context)
            val ids = manager.getAppWidgetIds(ComponentName(context, UsageWidgetProvider::class.java))
            if (ids.isNotEmpty()) {
                manager.updateAppWidget(ids, buildViews(context, state))
            }
        }
    }
}
