package com.lios.nativepoc

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Geocoder
import androidx.core.content.ContextCompat
import com.google.android.gms.location.CurrentLocationRequest
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.Priority
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.util.Locale
import java.util.UUID

data class CoarsePlace(val countryCode: String, val townCity: String?)
data class PermissionAssertion(val state: String = "granted", val checkedAt: Instant)
data class CoarsePlaceSubmission(
    val contractVersion: String = "1.0",
    val installationId: UUID,
    val updateId: UUID = UUID.randomUUID(),
    val countryCode: String,
    val townCity: String?,
    val source: String = "device_coarse",
    val observedAt: Instant,
    val permission: PermissionAssertion,
) {
    fun toWireMap(): Map<String, Any?> = mapOf(
        "contract_version" to contractVersion, "installation_id" to installationId.toString(),
        "update_id" to updateId.toString(), "country_code" to countryCode,
        "town_city" to townCity, "source" to source, "observed_at" to observedAt.toString(),
        "permission" to mapOf("state" to permission.state,
            "checked_at" to permission.checkedAt.toString()),
    )
}

interface LocalCoarseResolver {
    suspend fun resolve(latitude: Double, longitude: Double): CoarsePlace?
}

object PermissionPolicy {
    fun shouldSubmit(coarsePermissionGranted: Boolean): Boolean = coarsePermissionGranted
}

class AndroidGeocoderResolver(private val context: Context) : LocalCoarseResolver {
    @Suppress("DEPRECATION")
    override suspend fun resolve(latitude: Double, longitude: Double): CoarsePlace? =
        withContext(Dispatchers.IO) {
            val address = Geocoder(context, Locale.getDefault())
                .getFromLocation(latitude, longitude, 1)?.firstOrNull()
            address?.countryCode?.uppercase()?.let {
                CoarsePlace(it, address.locality)
            }
        }
}

class CoarsePlaceProvider(
    private val context: Context,
    private val locations: FusedLocationProviderClient,
    private val resolver: LocalCoarseResolver,
    private val installationId: UUID,
) {
    fun hasPermission(): Boolean = ContextCompat.checkSelfPermission(
        context, Manifest.permission.ACCESS_COARSE_LOCATION
    ) == PackageManager.PERMISSION_GRANTED

    @Suppress("MissingPermission")
    fun observeOnce(onManualFallback: () -> Unit, submit: suspend (CoarsePlaceSubmission) -> Unit) {
        if (!PermissionPolicy.shouldSubmit(hasPermission())) { onManualFallback(); return }
        val request = CurrentLocationRequest.Builder()
            .setPriority(Priority.PRIORITY_BALANCED_POWER_ACCURACY)
            .setMaxUpdateAgeMillis(15 * 60 * 1000)
            .build()
        locations.getCurrentLocation(request, null).addOnSuccessListener { transient ->
            if (transient == null) { onManualFallback(); return@addOnSuccessListener }
            kotlinx.coroutines.MainScope().launch {
                // Coordinates are used only by the local resolver and are never serialized or stored.
                val coarse = resolver.resolve(transient.latitude, transient.longitude)
                if (coarse == null) { onManualFallback(); return@launch }
                submit(CoarsePlaceSubmission(
                    installationId = installationId,
                    countryCode = coarse.countryCode,
                    townCity = coarse.townCity,
                    observedAt = Instant.ofEpochMilli(transient.time),
                    permission = PermissionAssertion(checkedAt = Instant.now()),
                ))
            }
        }.addOnFailureListener { onManualFallback() }
    }
}

object OvernightClassifier {
    fun crossesLocalDay(first: Instant, last: Instant, zone: ZoneId): Boolean =
        last > first && LocalDate.ofInstant(first, zone) != LocalDate.ofInstant(last, zone)
}
