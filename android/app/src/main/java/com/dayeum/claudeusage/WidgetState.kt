package com.dayeum.claudeusage

import java.time.Duration
import java.time.Instant

enum class Mood { CALM, WARNING, DANGER, AUTH_ERROR, SETUP_NEEDED }

const val HEADLINE_MAX = "max"
const val HEADLINE_SESSION = "session"
const val HEADLINE_WEEKLY = "weekly"

data class WidgetState(
    val mood: Mood,
    val headlinePercent: Int,
    val tooltip: String,
    val metricLabel: String = "사용량"
)

object WidgetStateCalculator {
    private const val WARNING_THRESHOLD = 60
    private const val DANGER_THRESHOLD = 85

    fun resolve(result: FetchResult?, headlineMetric: String = HEADLINE_MAX): WidgetState {
        if (result == null) {
            return WidgetState(Mood.SETUP_NEEDED, 0, "설정에서 sessionKey를 입력하세요", "설정 필요")
        }
        return when (result) {
            is FetchResult.AuthError -> WidgetState(Mood.AUTH_ERROR, 0, "재로그인이 필요해요 (sessionKey 만료)", "재로그인 필요")
            is FetchResult.TransientError -> WidgetState(Mood.WARNING, 0, "일시적으로 갱신에 실패했어요 (마지막 값 유지)", "갱신 실패")
            is FetchResult.Success -> compute(result.snapshot, headlineMetric)
        }
    }

    /** 데스크톱 위젯의 headline_metric 설정과 동일한 규칙: "max"는 더 높은 쪽을 자동 선택. */
    private fun compute(snapshot: UsageSnapshot, headlineMetric: String): WidgetState {
        val useSession = when (headlineMetric) {
            HEADLINE_SESSION -> true
            HEADLINE_WEEKLY -> false
            else -> snapshot.session.percent >= snapshot.weeklyAll.percent
        }
        val headline = if (useSession) snapshot.session.percent else snapshot.weeklyAll.percent
        val mood = when {
            headline >= DANGER_THRESHOLD -> Mood.DANGER
            headline >= WARNING_THRESHOLD -> Mood.WARNING
            else -> Mood.CALM
        }
        val countdown = formatCountdown(snapshot.session.resetsAt)
        val tooltip = "세션 ${snapshot.session.percent}% ($countdown) · 주간 ${snapshot.weeklyAll.percent}%"
        val metricLabel = if (useSession) "세션 한도" else "주간 한도"
        return WidgetState(mood, headline, tooltip, metricLabel)
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
