package com.lios.nativepoc

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

interface NativeTokenStore {
    fun saveRefreshToken(value: String)
    fun loadRefreshToken(): String?
    fun clear()
}

class KeystoreBackedNativeTokenStore(context: Context) : NativeTokenStore {
    private val preferences = EncryptedSharedPreferences.create(
        context,
        "li_native_credentials",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    override fun saveRefreshToken(value: String) {
        preferences.edit().putString("refresh_token", value).apply()
    }

    override fun loadRefreshToken(): String? = preferences.getString("refresh_token", null)

    override fun clear() {
        preferences.edit().remove("refresh_token").apply()
    }
}
