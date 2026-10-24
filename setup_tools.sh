#!/usr/bin/env bash
set -e

TOOLS_DIR="${HOME}/.apk_tv_converter/tools"
mkdir -p "$TOOLS_DIR"

echo "=== Setting up APK TV Converter Toolchain ==="

# Check Java
if command -v java >/dev/null 2>&1; then
    JAVA_CMD=$(which java)
    ln -sf "$JAVA_CMD" "$TOOLS_DIR/java"
    echo "✓ Java detected: $JAVA_CMD"
else
    echo "⚠️ Warning: Java not found on PATH. Please install OpenJDK 17."
fi

# Apktool
if [ ! -f "$TOOLS_DIR/apktool.jar" ]; then
    echo "Downloading Apktool 2.9.3..."
    curl -fsSL https://github.com/iBotPeaches/Apktool/releases/download/v2.9.3/apktool_2.9.3.jar -o "$TOOLS_DIR/apktool.jar"
fi
echo "✓ Apktool ready: $TOOLS_DIR/apktool.jar"

# Uber-APK-Signer
if [ ! -f "$TOOLS_DIR/uber-apk-signer.jar" ]; then
    echo "Downloading Uber-APK-Signer 1.3.0..."
    curl -fsSL https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar -o "$TOOLS_DIR/uber-apk-signer.jar"
fi
echo "✓ Uber-APK-Signer ready: $TOOLS_DIR/uber-apk-signer.jar"

# Android SDK Platform Jar (optional framework fallback)
if [ ! -f "$TOOLS_DIR/android.jar" ]; then
    echo "Downloading Android framework jar..."
    curl -fsSL https://github.com/Sable/android-platforms/raw/master/android-34/android.jar -o "$TOOLS_DIR/android.jar" || true
fi

chmod +x "$TOOLS_DIR"/* 2>/dev/null || true
echo "=== Toolchain Setup Complete! ==="
