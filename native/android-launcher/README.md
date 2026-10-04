# Li OS Android browser-launcher preview

This small, sideloadable APK gives the owner a **Li OS** launcher icon. It opens the fixed existing
Li staging HTTPS address in Chrome, or offers a browser chooser if Chrome is absent. It is **not**
a native Li client, a Trusted Web Activity, an offline app, or a Play Store release. The browser
toolbar can remain visible. The existing installable [web app](../../frontend/README.md#android-and-windows-installation)
is still the route to a standalone browser-managed installation.

## Architecture decision

Status: implemented local preview, 2026-10-04. The owner requested an Android installation file.
Use an external browser launcher rather than an embedded WebView: sign-in, cookies and Li data
remain in the established browser/BFF boundary. A native authenticated client would require a
separate design. A verified full-screen Trusted Web Activity would also require domain association
and a reviewed signing identity; no cloud deployment or OAuth change is authorized by this build.

The APK requests **no Android permissions**, contains no network client, stores no data, and ignores
incoming URLs and extras. It does not implement location, microphone, file access or native-gateway
authentication. All existing Li permissions, sign-in and governed actions remain unchanged.

## Offline build and validation

Requires existing JDK 17, Android SDK platform 35 and build tools 35.0.0. No dependencies are
downloaded. From the repository root:

```powershell
python -m unittest discover -s native/android-launcher/tests -v
pwsh -NoProfile -File native/android-launcher/build-preview.ps1
```

The build produces `dist/android-launcher/Li-OS-Android-Launcher-preview.apk`, refuses to overwrite
an existing APK, checks each tool exit code, aligns before signing and verifies the final signature.
It uses a **development-only** signing key with the Android debug password, not a production signing
credential. The key and intermediate files remain under ignored `dist/`; never commit or distribute
the keystore. A later production package needs separate secure signing/release planning. Reusing
this preview key supports local preview updates; replacing it requires uninstalling the old preview.

## Install on the owner's phone

Transfer only the APK to the phone, for example by USB file transfer. Open it in Samsung **My Files**
and use the Android installer. Android may require allowing installation from that particular source;
grant it only if comfortable with this reviewed preview and turn it off afterward. Do not disable
Play Protect or Samsung security controls to bypass a warning. If installation is blocked, use the
browser-managed web installation instead and report the warning without credentials.

Opening the Li OS icon starts the browser. An internet connection and existing Google sign-in remain
necessary. Building the launcher causes no cloud traffic; subsequent use has the same hosted/provider
dependencies as the web app. No physical Samsung installation or successful sign-in is claimed by
build, manifest, signature or synthetic tests. Owner device acceptance remains open.

## Local preview evidence — 2026-10-04

Seven offline tests passed, including Chrome launch, missing-Chrome chooser, missing-browser
bounded failure and restored activity. The real SDK-35 build passed, with APK v2/v3 signature and
alignment checks. Compiled manifest inspection confirmed zero permissions, target SDK 35 and the
single launcher activity. APK SHA-256:
`f082a195cfc77f76f6635fc09fcc43cf5720f949bc5a82947272568df19c9a96`.
No device install, sign-in, provider call, deployment or cloud change occurred.
