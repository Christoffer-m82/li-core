# Li Android coarse Place proof of concept

This library module is an architecture proof, not a shipped app. The host activity must request
`ACCESS_COARSE_LOCATION` with the Android runtime permission API, keep manual Place available,
authenticate through the Native Gateway, and use `KeystoreBackedNativeTokenStore` for encrypted
refresh-token storage backed by Android Keystore. Access tokens should remain in memory.
`ACCESS_FINE_LOCATION` and background location are intentionally absent.

The provider makes one balanced-power observation and passes the transient coordinate only to the
on-device `Geocoder`. It submits country and optional locality, creates no trail, and schedules no
continuous or background work. Background country-change or overnight support is a later, separate
opt-in capability requiring its own permission, battery, and privacy review.

Repository CI compiles the library and runs its unit tests with the toolchain documented in
[`docs/TESTING_AND_AUDIT.md`](../../docs/TESTING_AND_AUDIT.md#native-checks).
