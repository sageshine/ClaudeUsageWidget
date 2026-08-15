package com.dayeum.claudeusage

import java.time.Duration
import java.time.Instant

enum class Mood { CALM, WARNING, DANGER, AUTH_ERROR, SETUP_NEEDED }

data class WidgetState(val mood: Mood, val headlinePercent: Int, val tooltip: String)

object WidgetStateCalculator {
    private const val WARNING_THRESHOLD = 60
    private const val DANGER_THRESHOLD = 85

    fun resolve(result: FetchResult?): WidgetState {
        if (result == null) {
            return WidgetState(Mood.SETUP_NEEDED, 0, "설정에서 sessionKey를 입력하세요")
        }
        return when (result) {
            is FetchResult.AuthError -> WidgetState(Mood.AUTH_ERROR, 0, "재로그인이 필요해요 (sessionKey 만료)")
            is FetchResult.TransientError -> WidgetState(Mood.WARNING, 0, "일시적으로 갱신에 실패했어요 (마지막 값 유지)")
            is FetchResult.Success -> compute(result.snapshot)
        }
    }

    private fun compute(snapshot: UsageSnapshot): WidgetState {
        val headline = maxOf(snapshot.session.percent, snapshot.weeklyAll.percent)
        val mood = when {
            headline >= DANGER_THRESHOLD -> Mood.DANGER
            headline >= WARNING_THRESHOLD -> Mood.WARNING
            else -> Mood.CALM
        }
        val countdown = formatCountdown(snapshot.session.resetsAt)
        val tooltip = "세션 ${snapshot.session.percent}% ($countdown) · 주간 ${snapshot.weeklyAll.percent}%"
        return WidgetState(mood, headline, tooltip)
    }

    /** resetsAt이 null인 경우(아직 안 쓴 한도) 날짜 뺄셈 대신 안내 문구로 대체한다. */
    private fun formatCountdown(resetsAtMillis: Long?): String {
        if (resetsAtMillis == null) return "재설정 시간 확인 중"
        val totalSeconds = Duration.between(Instant.now(), Instant.ofEpochMilli(resetsAtMillis)).seconds
        if (totalSeconds <= 0) return "재설정 대기 중"
        val hours = totalSeconds / 3600
        val minutes = (totalSeconds % 3600) / 60
        return if (hours > 0) "${hours}시간 ${minutes}분 후 재설정" else "${minutes}분 후 재설정"
    }
}
