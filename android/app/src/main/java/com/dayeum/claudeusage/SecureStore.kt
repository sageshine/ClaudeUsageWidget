package com.dayeum.claudeusage

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/** sessionKey는 평문으로 저장하지 않는다 -- Android Keystore 기반 EncryptedSharedPreferences만 사용. */
object SecureStore {
    private const val PREFS_NAME = "claude_usage_secure_prefs"
    private const val KEY_SESSION_KEY = "session_key"
    private const val KEY_ORG_ID = "org_id"
    private const val KEY_DISCLAIMER_ACKED = "disclaimer_acked"

    private fun prefs(context: Context): SharedPreferences {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        return EncryptedSharedPreferences.create(
            context,
            PREFS_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    fun saveCredentials(context: Context, sessionKey: String, orgId: String) {
        prefs(context).edit()
            .putString(KEY_SESSION_KEY, sessionKey)
            .putString(KEY_ORG_ID, orgId)
            .apply()
    }

    fun sessionKey(context: Context): String? = prefs(context).getString(KEY_SESSION_KEY, null)
    fun orgId(context: Context): String? = prefs(context).getString(KEY_ORG_ID, null)

    fun hasCredentials(context: Context): Boolean =
        !sessionKey(context).isNullOrBlank() && !orgId(context).isNullOrBlank()

    fun clearCredentials(context: Context) {
        prefs(context).edit().remove(KEY_SESSION_KEY).remove(KEY_ORG_ID).apply()
    }

    fun isDisclaimerAcked(context: Context): Boolean = prefs(context).getBoolean(KEY_DISCLAIMER_ACKED, false)

    fun setDisclaimerAcked(context: Context) {
        prefs(context).edit().putBoolean(KEY_DISCLAIMER_ACKED, true).apply()
    }
}
