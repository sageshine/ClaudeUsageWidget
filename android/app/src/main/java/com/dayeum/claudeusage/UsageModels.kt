package com.dayeum.claudeusage

data class LimitInfo(val percent: Int, val resetsAt: Long?)

data class ScopedLimit(val modelName: String, val percent: Int, val resetsAt: Long?)

data class CreditInfo(val enabled: Boolean, val percent: Int, val usedDollars: Double, val limitDollars: Double?)

data class UsageSnapshot(
    val session: LimitInfo,
    val weeklyAll: LimitInfo,
    val weeklyScoped: List<ScopedLimit>,
    val credit: CreditInfo,
    val fetchedAtMillis: Long
)

sealed class FetchResult {
    data class Success(val snapshot: UsageSnapshot) : FetchResult()
    data class AuthError(val message: String) : FetchResult()
    data class TransientError(val message: String) : FetchResult()
}
