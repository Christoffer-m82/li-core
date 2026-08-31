package com.lios.nativepoc

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.ZoneId

class CoarsePlaceProviderTest {
    @Test fun payloadContractDeclaresNoCoordinateOrIdentifierProperties() {
        val names = CoarsePlaceSubmission::class.java.declaredFields.map { it.name.lowercase() }
        assertFalse(names.any { it in setOf("latitude", "longitude", "hardwareid", "advertisingid") })
        assertTrue(names.contains("countrycode"))
    }

    @Test fun overnightIsOnlyACrossDayHint() {
        val first = Instant.parse("2026-08-30T22:00:00Z")
        assertFalse(OvernightClassifier.crossesLocalDay(first, first.plusSeconds(60), ZoneId.of("UTC")))
        assertTrue(OvernightClassifier.crossesLocalDay(first, first.plusSeconds(10_800), ZoneId.of("UTC")))
    }

    @Test fun deniedPermissionNeverSubmits() {
        assertFalse(PermissionPolicy.shouldSubmit(false))
        assertTrue(PermissionPolicy.shouldSubmit(true))
    }
}
