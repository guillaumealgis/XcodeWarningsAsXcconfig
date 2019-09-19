#!/bin/bash

set -euo pipefail

# This will dump all settings styles to a folder named as the selected Xcode
# version.
# You probably don't need to run this. This is only used to update the
# Github repo for each Xcode version settings.

cd "$(dirname "$0")"

XCODE_VERSION="$(xcrun xcodebuild -version | head -n1 | awk '{ print $2 }')"
XCODE_FOLDER="Xcode-$XCODE_VERSION"

mkdir -p "$XCODE_FOLDER"

function export_settings_with_defaults {
    OPTION=$1
    NAME="$(tr '[:lower:]' '[:upper:]' <<< "${OPTION:0:1}")${OPTION:1}"
    echo "Exporting settings for $NAME"
    ./warnings2xcconfig.py --new-syntax --defaults "$OPTION" > "$XCODE_FOLDER/Warnings-${NAME}Defaults.xcconfig" || {
        rm -r "$XCODE_FOLDER"
        exit 1
    }
}

export_settings_with_defaults clang
export_settings_with_defaults xcode
export_settings_with_defaults strict
export_settings_with_defaults aggressive
