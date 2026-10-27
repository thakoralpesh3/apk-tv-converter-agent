# APK Cross-Converter AI Agent (Smartphone ⇋ Android TV)

[![24/7 TV Simulator](https://img.shields.io/badge/24%2F7%20Simulator-Live%20on%20GitHub-brightgreen?logo=googlechrome&logoColor=white)](https://thakoralpesh3.github.io/apk-tv-converter-agent/)
[![CI Tests](https://github.com/thakoralpesh3/apk-tv-converter-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/thakoralpesh3/apk-tv-converter-agent/actions/workflows/ci.yml)
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/thakoralpesh3/apk-tv-converter-agent)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](Dockerfile)
[![Gemini 4 Argon](https://img.shields.io/badge/Gemini_4-Argon_Tier--1-purple.svg)](core/ai_content_engine.py)

An autonomous AI agent engineered for bi-directional conversion between Smartphone/Tablet APKs and Android TV / Google TV / Fire TV APKs, upgraded with the **Gemini 4 Argon AI Content Engine** and the **Android Reverse Engineering Triage Toolchain**.

---

## 🌐 Run Directly from GitHub

You can run this agent in multiple ways without manual configuration:

### 0. 📺 24/7 Android TV Live Simulator (Instant in Your Browser)
Run, test, and interact with Android TV apps, the virtual desktop mouse cursor, and the interactive TV remote control 24/7 without installing anything:
➡️ **[Launch 24/7 Android TV Simulator](https://thakoralpesh3.github.io/apk-tv-converter-agent/)**

- **Live 16:9 Cinema TV Screen**: Experience Leanback Launcher and In-App TV playback.
- **Virtual Desktop Mouse Pointer**: Test D-Pad cursor movement and synthetic touch clicks.
- **Interactive D-Pad Remote**: Full direction pad, OK click, volume control, and sound synthesis.
- **Client-Side APK Testing**: Drag & drop any converted APK to test directly in your browser.

### 1. ⚡ Convert via GitHub Actions (Zero Local Setup)
1. Go to the **[Actions Tab](https://github.com/thakoralpesh3/apk-tv-converter-agent/actions/workflows/convert.yml)**.
2. Select **"Convert APK to Android TV / Mobile"**.
3. Click **"Run workflow"**, enter an APK direct download URL (or leave blank to test with bundled sample), and choose target mode (`tv`, `mobile`, `universal`).
4. GitHub Actions builds the converted APK in the cloud and provides it as a downloadable release artifact!

### 2. 💻 Run in GitHub Codespaces (1-Click Cloud Browser Studio)
Click the badge above or navigate to **Code ➔ Codespaces ➔ Create codespace on main**.
- Pre-configured with OpenJDK 17, Python 3.12, and Apktool.
- Port `8877` automatically forwards to your browser with the live Web Studio Dashboard!

### 3. 🚀 One-Command Remote Installer
On any Linux / macOS machine:
```bash
curl -fsSL https://raw.githubusercontent.com/thakoralpesh3/apk-tv-converter-agent/main/install_and_run.sh | bash
```

### 4. 🐳 Docker & Docker Compose
```bash
docker compose up -d
# Open http://localhost:8877 in your browser
```

---

## 🔄 Automated Antigravity GitHub Sync

Whenever changes or improvements are made by Antigravity or yourself, they can be synchronized to GitHub effortlessly:

1. **One-Command Shell Sync**:
   ```bash
   ./sync_to_github.sh "feat: describe your change"
   ```
2. **CLI Agent Flag**:
   ```bash
   ./launch_agent.sh --sync-github "feat: update conversion rules"
   ```
3. **Background Auto-Sync Watcher**:
   ```bash
   ./launch_agent.sh --watch-sync
   ```
   Monitors filesystem events and automatically pushes to GitHub origin main.
4. **Web Studio Button**: Click the **"Sync GitHub"** button in the Web Studio header for instant 1-click cloud sync.
5. **Systemd Autonomous Sync Service**: Runs automatically in the background via `apk-tv-converter-sync.service` to push any changes made by Antigravity or the user to GitHub in real time.

---

## 🚀 Key Features

1. **🖱️ Native Android TV Desktop Mouse Cursor Engine (`core/cursor_builder.py`)**:
   - **Bytecode-Level Multidex Injection (`classesN.dex`)**: Automatically compiles Java sources (`TvDesktopCursorOverlay.java` and `TvCursorInitProvider.java`) with D8 and injects `classes2.dex` and ContentProvider declaration with zero smali decompilation overhead.
   - **Hardware TV Remote Interception**: Wraps window callbacks on resumed activities. D-Pad keys smoothly move a desktop arrow cursor on 16:9 screens with acceleration.
   - **Synthetic Touch Event Dispatch**: D-Pad Center / OK synthesizes real hardware `MotionEvent.ACTION_DOWN` and `ACTION_UP` touch events directly at the cursor tip coordinates, making non-TV apps (Flutter, React Native, Jetpack Compose, WebViews, Canvas) fully operable with a standard TV remote control.
   - **Pure TV Default**: Converted apps automatically launch directly into Android TV mode (`pure_tv=True`), removing phone launcher duplicates.

1. **🔬 Android Reverse Engineering Triage (`core/re_analyzer.py`)**:
   - Zero-dependency Phase 0 architecture fingerprinting (`fingerprint.sh`).
   - Identifies frameworks: Jetpack Compose, Flutter, React Native, Unity, Cordova/Web.
   - Detects R8/ProGuard obfuscation, HTTP stacks (Retrofit, OkHttp, Volley), and native ABIs.
   - Tailors TV conversion strategies (e.g., protecting Flutter Dart bundles, synthesizing Compose focus rings).

2. **✨ Gemini 4 Argon AI Content Engine (`core/ai_content_engine.py`)**:
   - **Primary Model Target**: `gemini-4-argon` (Tier-1) with automatic cascade fallback.
   - **AI Smart TV Banner Synthesizer**: Generates 16:9 Leanback promotional banners with color harmonies.
   - **AI Big-Screen TV Audit**: Evaluates couch ergonomics, D-pad readiness, and platform compatibility.
   - **AI Play Store Copywriter**: Creates Google Play Store and Leanback listing copy.

3. **Smartphone ➔ Android TV (`--mode tv`)**:
   - Injects `android.intent.category.LEANBACK_LAUNCHER`.
   - Declares `android.software.leanback` and sets `android.hardware.touchscreen` to `required="false"`.
   - Relaxes mobile hardware requirements and applies landscape/remote marker configurations.

4. **Android TV ➔ Smartphone (`--mode mobile`)**:
   - Injects standard `LAUNCHER` and synthesizes mobile icon densities.

5. **Universal Dual-Mode (`--mode universal`)**:
   - Dual-launcher support across Phones, Foldables, Tablets, and Android TV.

---

## 🛠️ Quick Commands

```bash
# Open Interactive Terminal Wizard
./launch_agent.sh --wizard

# Open Web Studio Dashboard
./launch_agent.sh --gui

# Run Phase 0 Reverse Engineering Architecture Fingerprint
./launch_agent.sh --fingerprint /path/to/app.apk

# Convert Smartphone APK to Android TV
./launch_agent.sh --convert /path/to/app.apk --mode tv

# Run Gemini 4 Argon Big-Screen Compatibility Audit
./launch_agent.sh --ai-audit /path/to/app.apk

# Generate Play Store & TV Listing Copy
./launch_agent.sh --ai-copy /path/to/app.apk --mode tv

# Sync Antigravity updates to GitHub
./launch_agent.sh --sync-github

# Run Toolchain Diagnostics
./launch_agent.sh --check-env
```

---

## 📂 Project Structure

```
apk-tv-converter-agent/
├── .github/workflows/       # GitHub Actions Cloud Convert & CI workflows
├── .devcontainer/           # GitHub Codespaces 1-click cloud environment
├── core/                    # Conversion, AI content & Reverse Engineering engines
│   ├── converter.py         # Bi-directional APK Cross-Converter
│   ├── re_analyzer.py       # Architecture & Reverse-Engineering Triage
│   ├── reverse_engineering_bridge.py # Bridge to fingerprint.sh & JADX
│   ├── ai_content_engine.py # Gemini 4 Argon Content Engine
│   └── apk_engine.py        # Low-level apktool / java / signer engine
├── web/                     # FastAPI Web Studio & TV Live Preview Modal
├── scripts/                 # Auto-sync daemon and automation helpers
├── tests/                   # Automated unit test suite
├── sync_to_github.sh        # Standalone Antigravity GitHub sync tool
├── setup_tools.sh           # Automatic build toolchain installer
├── launch_agent.sh          # Universal agent launcher
└── agent.py                 # Multi-interface master agent CLI
```
