#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="python3"
if [ -f "$SCRIPT_DIR/.venv/bin/python3" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3"
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

# Export JAVA_HOME and PATH if needed
if [ -d "/home/alpesh/.web2apk/jdk/jdk-17.0.10+7" ]; then
    export JAVA_HOME="/home/alpesh/.web2apk/jdk/jdk-17.0.10+7"
    export PATH="/home/alpesh/.apk_tv_converter/tools:$JAVA_HOME/bin:$PATH"
elif [ -z "$JAVA_HOME" ] && command -v java >/dev/null 2>&1; then
    JAVA_CMD=$(readlink -f "$(command -v java)")
    export JAVA_HOME="$(dirname "$(dirname "$JAVA_CMD")")"
    export PATH="/home/alpesh/.apk_tv_converter/tools:$JAVA_HOME/bin:$PATH"
else
    export PATH="/home/alpesh/.apk_tv_converter/tools:$PATH"
fi

EXIT_CODE=0
"$PYTHON_BIN" "$SCRIPT_DIR/agent.py" "$@" || EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⚠️ APK Cross-Converter Agent exited with error code $EXIT_CODE."
    echo "Press Enter to close this window..."
    read -r
fi

exit $EXIT_CODE
