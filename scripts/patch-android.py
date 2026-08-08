#!/usr/bin/env python3
"""
Patch the Android project that `npx cap add android` regenerates on every
CI run.

Because the native project is thrown away and recreated each build, nothing
we change by hand survives. This script reapplies the three things that must
be true for a Play-eligible release, and fails loudly if the generated
project does not look the way we expect:

  1. versionCode / versionName  - Play rejects a duplicate versionCode, and
                                  the regenerated project always says 1.
  2. release signing config     - reads the keystore from env vars so no
                                  secret is ever written into a file.
  3. SDK levels                 - asserts targetSdk is at least the level
                                  Play currently requires.

Usage:
    python3 scripts/patch-android.py --version-code 42 --version-name 1.2.0
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

# Play requires new apps and updates to target this from 31 Aug 2026.
REQUIRED_TARGET_SDK = 36
REQUIRED_MIN_SDK = 24
ICON_BG = "#12171C"          # must match --ink in www/index.html

APP_GRADLE = Path("android/app/build.gradle")
VARIABLES_GRADLE = Path("android/variables.gradle")

# Appended rather than spliced in. Gradle's `android { }` is an extension
# object, so a second block reconfigures the existing one instead of
# replacing it - which means we never have to do surgery on Capacitor's
# generated text and this keeps working when their template changes.
SIGNING_BLOCK = """

// ---- injected by scripts/patch-android.py, do not edit by hand ----
android {
    signingConfigs {
        release {
            storeFile = file(System.getenv("KEYSTORE_PATH"))
            storePassword = System.getenv("KEYSTORE_PASSWORD")
            keyAlias = System.getenv("KEY_ALIAS")
            keyPassword = System.getenv("KEY_PASSWORD")
        }
    }
    buildTypes {
        release {
            signingConfig = signingConfigs.release
        }
    }
}
"""


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def set_property(text, name, value, quoted=False):
    """
    Replace a Gradle property assignment, tolerating both the legacy
    space-assignment form (`versionCode 1`) and the `=` form that Capacitor 8
    and AGP 8.13 require. Returns (new_text, count).
    """
    replacement = f'{name} = {chr(34) + str(value) + chr(34) if quoted else value}'
    pattern = re.compile(rf'^\s*{name}\s*=?\s*.+$', re.MULTILINE)
    new_text, count = pattern.subn(
        lambda m: m.group(0)[: len(m.group(0)) - len(m.group(0).lstrip())] + replacement,
        text,
        count=1,
    )
    return new_text, count


def patch_app_gradle(version_code, version_name, signing):
    if not APP_GRADLE.exists():
        fail(f"{APP_GRADLE} not found - did `npx cap add android` run?")

    text = APP_GRADLE.read_text()

    if version_code is not None:
        text, n = set_property(text, "versionCode", version_code)
        if n != 1:
            fail("could not find versionCode in app/build.gradle")

        text, n = set_property(text, "versionName", version_name, quoted=True)
        if n != 1:
            fail("could not find versionName in app/build.gradle")
        print(f"  versionCode = {version_code}, versionName = \"{version_name}\"")

    if signing:
        if "injected by scripts/patch-android.py" in text:
            print("  signing config already present, skipping")
        else:
            text += SIGNING_BLOCK
            print("  release signing config appended")

    APP_GRADLE.write_text(text)


def check_sdk_levels():
    if not VARIABLES_GRADLE.exists():
        fail(f"{VARIABLES_GRADLE} not found")

    text = VARIABLES_GRADLE.read_text()

    def read(name):
        m = re.search(rf'{name}\s*=?\s*(\d+)', text)
        return int(m.group(1)) if m else None

    target, minimum = read("targetSdkVersion"), read("minSdkVersion")

    if target is None:
        fail("could not read targetSdkVersion from variables.gradle")

    if target < REQUIRED_TARGET_SDK:
        fail(
            f"targetSdkVersion is {target}, but Google Play requires "
            f"{REQUIRED_TARGET_SDK}.\n"
            f"       Capacitor pins this to its major version and does not "
            f"support overriding it.\n"
            f"       Upgrade @capacitor/* to the major version that targets "
            f"SDK {REQUIRED_TARGET_SDK}."
        )

    print(f"  targetSdkVersion = {target}, minSdkVersion = {minimum} (ok)")


def install_icons():
    """
    Copy the launcher icons into the regenerated native project.

    The PNGs are pre-rendered and committed under assets/icon/ rather than
    built here, so CI needs no image toolchain. Run scripts/make-icon.py
    locally if the artwork changes.
    """
    src = Path("assets/icon")
    if not src.exists():
        fail(f"{src} not found - run scripts/make-icon.py and commit the output")

    res = Path("android/app/src/main/res")
    if not res.exists():
        fail(f"{res} not found - did `npx cap add android` run?")

    copied = 0
    for d in sorted(src.glob("mipmap-*")):
        target = res / d.name
        target.mkdir(parents=True, exist_ok=True)
        for png in d.glob("*.png"):
            shutil.copy2(png, target / png.name)
            copied += 1
    if copied == 0:
        fail("no icon PNGs found under assets/icon/mipmap-*/")

    # Capacitor ships a default adaptive icon whose background is a vector
    # drawable of the same name we use for our colour. Remove it so the
    # reference is unambiguous.
    for stale in ("drawable/ic_launcher_background.xml",
                  "drawable-v24/ic_launcher_foreground.xml"):
        p = res / stale
        if p.exists():
            p.unlink()

    (res / "values").mkdir(parents=True, exist_ok=True)
    (res / "values" / "ic_launcher_background.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<resources>\n'
        f'    <color name="ic_launcher_background">{ICON_BG}</color>\n'
        '</resources>\n'
    )

    (res / "mipmap-anydpi-v26").mkdir(parents=True, exist_ok=True)
    adaptive = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <background android:drawable="@color/ic_launcher_background"/>\n'
        '    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>\n'
        '</adaptive-icon>\n'
    )
    for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
        (res / "mipmap-anydpi-v26" / name).write_text(adaptive)

    print(f"  {copied} icon files copied, adaptive icon written")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--version-code", type=int,
                   help="sets versionCode; omit to leave the generated value")
    p.add_argument("--version-name",
                   help="sets versionName; omit to leave the generated value")
    p.add_argument("--signing", action="store_true",
                   help="inject the release signing config (needs the keystore env vars)")
    args = p.parse_args()

    if bool(args.version_code) != bool(args.version_name):
        fail("--version-code and --version-name must be given together")

    print("Checking SDK levels...")
    check_sdk_levels()

    print("Installing launcher icons...")
    install_icons()

    if args.version_code or args.signing:
        print("Patching app/build.gradle...")
        patch_app_gradle(args.version_code, args.version_name, args.signing)

    print("Done.")


if __name__ == "__main__":
    main()
