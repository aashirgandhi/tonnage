# Tonnage — steel weight calculator

Wraps a single self-contained HTML app into an Android APK using Capacitor,
built on GitHub Actions. No Android Studio or local toolchain needed.

## Files
- `www/index.html` — the whole app (offline, no dependencies)
- `capacitor.config.json` — app name and package ID
- `package.json` — Capacitor dependencies
- `.github/workflows/build-apk.yml` — the cloud build

## To build
Actions tab → "Build Android APK" → Run workflow.
Download `tonnage-apk` from the finished run.

## Before publishing
- Verify the IS 808 sectional weight tables in `www/index.html`
  against your own mill test certificates.
- Change `appId` in `capacitor.config.json` — it is permanent once
  the app is on the Play Store.
- The workflow builds a *debug* APK, signed with a throwaway key.
  Fine for sharing and testing, not accepted by the Play Store.
