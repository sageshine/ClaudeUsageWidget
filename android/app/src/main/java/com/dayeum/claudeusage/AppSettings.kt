package com.dayeum.claudeusage

import android.content.Context

/** 세션/주간 중 어느 한도를 대표로 보여줄지 -- 민감 정보가 아니라 평문 저장. */
object AppSettings {
    private const val PREFS = "claude_usage_settings"
    private const val KEY_HEADLINE_METRIC = "headline_metric"

    fun headlineMetric(context: Context): String =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_HEADLINE_METRIC, HEADLINE_MAX) ?: HEADLINE_MAX

    fun setHeadlineMetric(context: Context, metric: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_HEADLINE_METRIC, metric)
            .apply()
    }
}
