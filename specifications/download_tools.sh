#!/bin/bash
set -e

# Download the TLA+ Tools JAR
JAR_URL="https://github.com/tlaplus/tlaplus/releases/download/v1.8.0/tla2tools.jar"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
JAR_PATH="$SCRIPT_DIR/tla2tools.jar"

if [ ! -f "$JAR_PATH" ]; then
    echo "Downloading tla2tools.jar..."
    if command -v curl >/dev/null 2>&1; then
        curl -L -o "$JAR_PATH" "$JAR_URL"
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$JAR_PATH" "$JAR_URL"
    else
        echo "Error: Neither curl nor wget found."
        exit 1
    fi
    echo "Successfully downloaded tla2tools.jar"
else
    echo "tla2tools.jar already exists at $JAR_PATH"
fi
