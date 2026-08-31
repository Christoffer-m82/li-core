# Li iOS coarse Place proof of concept

This Swift package is an architecture proof, not a shipped app. A host app must add
`NSLocationWhenInUseUsageDescription`, provide explicit manual Place controls, authenticate with
the Native Gateway, and store refresh material in Keychain. Fine accuracy is not requested.

The default path makes a one-shot request at three-kilometre accuracy. Significant-change
monitoring is exposed only as a separate user opt-in for country-change/overnight hints; it costs
more battery and may wake the app in the background. The module never creates a trail, never
serializes `CLLocation`, and releases the transient coordinate after local reverse geocoding.
