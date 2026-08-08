# Kanta — steel weight calculator

Wraps a single self-contained HTML app into an Android APK using Capacitor,
built on GitHub Actions. No Android Studio or local toolchain needed.

## Files
- `www/index.html` — the whole app (offline, no dependencies)
- `capacitor.config.json` — app name and package ID
- `package.json` — Capacitor dependencies
- `.github/workflows/build-apk.yml` — the cloud build

## To build
Actions tab → "Build Android APK" → Run workflow.
Download `kanta-apk` from the finished run.

## Before publishing
- Verify the IS 808 sectional weight tables in `www/index.html`
  against your own mill test certificates.
- Change `appId` in `capacitor.config.json` — it is permanent once
  the app is on the Play Store.
- The workflow builds a *debug* APK, signed with a throwaway key.
  Fine for sharing and testing, not accepted by the Play Store.

## Releasing to Google Play

Signed builds come from `.github/workflows/release.yml` (manual trigger).
It regenerates the native project, then `scripts/patch-android.py`
reapplies the versionCode, versionName and release signing config, which
would otherwise be lost because `npx cap add android` recreates
`android/` from scratch on every run.

Required repository secrets:

| Secret | What it is |
|---|---|
| `KEYSTORE_BASE64` | The upload keystore, base64-encoded, single line |
| `KEYSTORE_PASSWORD` | Keystore password |
| `KEY_ALIAS` | Key alias (e.g. `kanta-upload`) |
| `KEY_PASSWORD` | Key password |

Back up the original `.jks` somewhere offline. Losing it means contacting
Google Play support to reset the upload key.

`versionCode` comes from the GitHub Actions run number, so it always
increases. Never delete and recreate the repo — the counter resets and
Play will reject the upload.

## Launcher icon

Artwork lives in `assets/icon/` as pre-rendered PNGs at every density,
plus the SVG sources. They are committed rather than generated in CI so
the build needs no image toolchain.

To change the icon, edit `scripts/make-icon.py`, then:

    pip install cairosvg pillow
    python3 scripts/make-icon.py

and commit the regenerated `assets/icon/` tree.

`scripts/patch-android.py` copies these into the native project on every
build, because `npx cap add android` regenerates `android/` from scratch
and would otherwise restore Capacitor's default icon.
