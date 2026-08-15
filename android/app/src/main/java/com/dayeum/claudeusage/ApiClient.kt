package com.dayeum.claudeusage

import org.json.JSONException
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant
import java.time.format.DateTimeParseException

object ApiClient {
    private const val USAGE_URL_TEMPLATE = "https://claude.ai/api/organizations/%s/usage"

    fun fetchUsage(sessionKey: String, orgId: String): FetchResult {
        val url = URL(USAGE_URL_TEMPLATE.format(orgId))
        val conn = url.openConnection() as HttpURLConnection
        return try {
            conn.requestMethod = "GET"
            conn.setRequestProperty("Cookie", "sessionKey=$sessionKey")
            conn.setRequestProperty("Accept", "application/json")
            conn.connectTimeout = 10_000
            conn.readTimeout = 10_000

            val status = conn.responseCode
            if (status == 401 || status == 403) {
                return FetchResult.AuthError("claude.ai returned $status")
            }
            if (status != 200) {
                return FetchResult.TransientError("unexpected status $status")
            }
            val body = conn.inputStream.bufferedReader().use { it.readText() }
            val data = try {
                JSONObject(body)
            } catch (e: JSONException) {
                return FetchResult.TransientError("failed to parse response body as JSON: ${e.message}")
            }
            try {
                FetchResult.Success(parseUsageResponse(data))
            } catch (e: JSONException) {
                FetchResult.TransientError("unexpected response shape: ${e.message}")
            }
        } catch (e: IOException) {
            FetchResult.TransientError(e.message ?: "network error")
        } finally {
            conn.disconnect()
        }
    }

    /** claude.ai는 utilization/percent를 10.4처럼 소수로 내려준다. */
    private fun percentOf(value: Any?): Int {
        val d = when (value) {
            is Number -> value.toDouble()
            is String -> value.toDoubleOrNull() ?: 0.0
            else -> 0.0
        }
        return Math.round(d).toInt()
    }

    /**
     * claude.ai가 아직 한 번도 안 쓴 weekly_scoped 한도에는 resets_at을 JSON null로
     * 내려준다. org.json의 optString은 JSON null 값을 "null" 문자열로 바꿔버리는
     * 함정이 있어서(데스크톱 파이썬 버전에서 실제로 겪은 크래시와 같은 원인),
     * 여기서 명시적으로 걸러낸다.
     */
    private fun parseDt(value: String?): Long? {
        if (value.isNullOrEmpty() || value == "null") return null
        return try {
            Instant.parse(value).toEpochMilli()
        } catch (e: DateTimeParseException) {
            null
        }
    }

    fun parseUsageResponse(data: JSONObject): UsageSnapshot {
        val fiveHour = data.getJSONObject("five_hour")
        val sevenDay = data.getJSONObject("seven_day")

        val session = LimitInfo(
            percent = percentOf(fiveHour.opt("utilization")),
            resetsAt = parseDt(fiveHour.optString("resets_at", ""))
        )
        val weeklyAll = LimitInfo(
            percent = percentOf(sevenDay.opt("utilization")),
            resetsAt = parseDt(sevenDay.optString("resets_at", ""))
        )

        val weeklyScoped = mutableListOf<ScopedLimit>()
        val limits = data.optJSONArray("limits")
        if (limits != null) {
            for (i in 0 until limits.length()) {
                val item = limits.optJSONObject(i) ?: continue
                if (item.optString("kind") != "weekly_scoped") continue
                val scope = item.optJSONObject("scope") ?: continue
                val model = scope.optJSONObject("model") ?: continue
                weeklyScoped.add(
                    ScopedLimit(
                        modelName = model.optString("display_name"),
                        percent = percentOf(item.opt("percent")),
                        resetsAt = parseDt(item.optString("resets_at", ""))
                    )
                )
            }
        }

        val spend = data.optJSONObject("spend") ?: JSONObject()
        val used = spend.optJSONObject("used")
        val limit = spend.optJSONObject("limit")
        val credit = CreditInfo(
            enabled = spend.optBoolean("enabled", false),
            percent = percentOf(spend.opt("percent")),
            usedDollars = minorToDollars(used),
            limitDollars = if (limit != null) minorToDollars(limit) else null
        )

        return UsageSnapshot(
            session = session,
            weeklyAll = weeklyAll,
            weeklyScoped = weeklyScoped,
            credit = credit,
            fetchedAtMillis = System.currentTimeMillis()
        )
    }

    private fun minorToDollars(amount: JSONObject?): Double {
        if (amount == null) return 0.0
        val minor = amount.optLong("amount_minor", 0)
        val exponent = amount.optInt("exponent", 2)
        return minor / Math.pow(10.0, exponent.toDouble())
    }
}
