package com.dayeum.claudeusage

import android.content.Context

/** 홈화면 위젯이 sessionKey 없이도 읽을 수 있도록 최근 계산 결과만 평문으로 캐싱한다. */
object UsageCache {
    private const val PREFS = "claude_usage_cache"
    private const val KEY_PERCENT = "percent"
    private const val KEY_MOOD = "mood"
    private const val KEY_SUBTEXT = "subtext"
    private const val KEY_METRIC_LABEL = "metric_label"

    fun save(context: Context, state: WidgetState) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putInt(KEY_PERCENT, state.headlinePercent)
            .putString(KEY_MOOD, state.mood.name)
            .putString(KEY_SUBTEXT, state.tooltip)
            .putString(KEY_METRIC_LABEL, state.metricLabel)
            .apply()
    }

    fun load(context: Context): WidgetState {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val mood = try {
            Mood.valueOf(prefs.getString(KEY_MOOD, Mood.SETUP_NEEDED.name)!!)
        } catch (e: IllegalArgumentException) {
            Mood.SETUP_NEEDED
        }
        return WidgetState(
            mood = mood,
            headlinePercent = prefs.getInt(KEY_PERCENT, 0),
            tooltip = prefs.getString(KEY_SUBTEXT, "") ?: "",
            metricLabel = prefs.getString(KEY_METRIC_LABEL, "사용량") ?: "사용량"
        )
    }
}
