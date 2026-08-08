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
import sys
from pathlib import Path

# Play requires new apps and updates to target this from 31 Aug 2026.
REQUIRED_TARGET_SDK = 36
REQUIRED_MIN_SDK = 24

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


def patch_app_gradle(version_code, version_name):
    if not APP_GRADLE.exists():
        fail(f"{APP_GRADLE} not found - did `npx cap add android` run?")

    text = APP_GRADLE.read_text()

    if "injected by scripts/patch-android.py" in text:
        print("  signing config already present, skipping")
        return

    text, n = set_property(text, "versionCode", version_code)
    if n != 1:
        fail("could not find versionCode in app/build.gradle")

    text, n = set_property(text, "versionName", version_name, quoted=True)
    if n != 1:
        fail("could not find versionName in app/build.gradle")

    text += SIGNING_BLOCK
    APP_GRADLE.write_text(text)
    print(f"  versionCode = {version_code}, versionName = \"{version_name}\"")
    print("  release signing config appended")


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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--version-code", required=True, type=int)
    p.add_argument("--version-name", required=True)
    args = p.parse_args()

    print("Checking SDK levels...")
    check_sdk_levels()
    print("Patching app/build.gradle...")
    patch_app_gradle(args.version_code, args.version_name)
    print("Done.")


if __name__ == "__main__":
    main()
