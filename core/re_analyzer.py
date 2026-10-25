"""
Reverse Engineering & Architecture Analyzer Engine
Integrates the SimoneAvogadro/android-reverse-engineering-skill toolchain.
Performs rapid architectural triage, framework fingerprinting (Flutter, React Native,
Cordova/Capacitor, Jetpack Compose, Native Kotlin/Java), R8/ProGuard obfuscation auditing,
HTTP stack detection, and generates framework-specific Android TV conversion strategies.
"""

import os
import re
import json
import zipfile
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

DEFAULT_FINGERPRINT_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "tools" / "fingerprint.sh",
    Path.home() / ".gemini/config/plugins/android-reverse-engineering-plugin/skills/android-reverse-engineering/scripts/fingerprint.sh",
    Path.home() / ".gemini/config/plugins/android-reverse-engineering-plugin/plugins/android-reverse-engineering/skills/android-reverse-engineering/scripts/fingerprint.sh",
    Path.home() / ".apk_tv_converter/tools/fingerprint.sh",
]

class ReverseEngineeringAnalyzer:
    """
    Reverse engineers and fingerprints APKs to identify runtime architecture,
    obfuscation level, and third-party components before TV conversion.
    """

    def __init__(self, script_path: Optional[Path] = None):
        self.script_path = None
        if script_path and Path(script_path).is_file():
            self.script_path = Path(script_path)
        else:
            for candidate in DEFAULT_FINGERPRINT_CANDIDATES:
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    self.script_path = candidate
                    break

    @classmethod
    def get_jadx_binary(cls) -> Optional[Path]:
        """Locates the jadx decompiler executable."""
        candidates = [
            shutil.which("jadx"),
            Path.home() / ".local/bin/jadx",
            Path.home() / ".local/share/jadx/bin/jadx",
            Path.home() / ".apk_tv_converter/tools/jadx/bin/jadx",
            Path.home() / ".apk_tv_converter/tools/jadx"
        ]
        for c in candidates:
            if c:
                p = Path(c)
                if p.is_file() and os.access(p, os.X_OK):
                    return p
        return None

    def check_tools(self) -> Dict[str, Any]:
        """Reports status of reverse-engineering toolchain."""
        jadx_bin = self.get_jadx_binary()
        jadx_version = ""
        if jadx_bin:
            try:
                res = subprocess.run([str(jadx_bin), "--version"], stdout=subprocess.PIPE, text=True, timeout=5)
                if res.returncode == 0:
                    jadx_version = res.stdout.strip()
            except Exception:
                pass

        return {
            "fingerprint_ready": self.script_path is not None,
            "fingerprint_path": str(self.script_path) if self.script_path else None,
            "jadx_ready": jadx_bin is not None,
            "jadx_path": str(jadx_bin) if jadx_bin else None,
            "jadx_version": jadx_version,
            "plugin_installed": (Path.home() / ".gemini/config/plugins/android-reverse-engineering-plugin").is_dir()
        }

    def decompile(self, apk_path: Path | str, output_dir: Path | str, timeout: int = 180, log_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """Decompiles APK to Java/Kotlin source code using jadx."""
        jadx_bin = self.get_jadx_binary()
        if not jadx_bin:
            return {"success": False, "error": "jadx decompiler executable not found."}

        in_path = Path(apk_path).resolve()
        out_path = Path(output_dir).resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        cmd = [str(jadx_bin), "-d", str(out_path), "--no-imports", "--show-bad-code", str(in_path)]
        if log_callback:
            log_callback(f"Executing jadx decompilation: {' '.join(cmd)}")

        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
            return {"success": proc.returncode == 0, "output_dir": str(out_path), "log": proc.stdout}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze(self, apk_path: Path | str, log_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """
        Runs deep APK architectural triage.
        Uses fingerprint.sh if available, with pure-Python ZIP/DEX analysis fallback.
        """
        apk_path = Path(apk_path).resolve()
        if not apk_path.is_file():
            raise FileNotFoundError(f"APK file not found for analysis: {apk_path}")

        def _log(msg: str):
            if log_callback:
                log_callback(msg)

        _log(f"[Reverse Engineering] Fingerprinting {apk_path.name}...")

        # 1. Attempt using the official android-reverse-engineering fingerprint.sh script
        script_output = None
        if self.script_path and self.script_path.is_file() and os.access(self.script_path, os.X_OK):
            try:
                env = os.environ.copy()
                env["PATH"] = f"/home/alpesh/.apk_tv_converter/tools:/home/alpesh/.local/bin:{env.get('PATH', '')}"
                res = subprocess.run(
                    ["bash", str(self.script_path), str(apk_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30,
                    env=env
                )
                if res.returncode == 0:
                    script_output = res.stdout
            except Exception as e:
                _log(f"[Reverse Engineering] Notice: fingerprint.sh fallback to native analyzer ({e})")

        # 2. Parse script output or run pure-Python inspection
        if script_output:
            report = self._parse_script_output(script_output, apk_path)
        else:
            report = self._analyze_native_python(apk_path)

        # 3. Derive Framework-Specific TV Conversion Strategy
        strategy = self._derive_strategy(report)
        report["conversion_strategy"] = strategy

        _log(f"[Reverse Engineering] Framework: {report['framework']} | Obfuscation: {report['obfuscation_level']}")
        _log(f"[Reverse Engineering] Recommended Strategy: {strategy['name']}")

        return report

    def _parse_script_output(self, text: str, apk_path: Path) -> Dict[str, Any]:
        """Parses the text output of fingerprint.sh into structured data."""
        lines = text.splitlines()
        framework = "Unknown"
        rationale = ""
        obfuscation = "LOW"
        http_stack = []
        di_stack = []
        ser_stack = []
        sdks = []
        native_libs = []
        in_native = False

        for line in lines:
            line_str = line.strip()
            if line_str.startswith("Framework:"):
                framework = line_str.replace("Framework:", "").strip()
            elif line_str.startswith("Rationale:"):
                rationale = line_str.replace("Rationale:", "").strip()
            elif line_str.startswith("Obfuscation:"):
                obfuscation = line_str.replace("Obfuscation:", "").strip()
            elif line_str.startswith("HTTP stack:"):
                val = line_str.replace("HTTP stack:", "").strip()
                if val and val != "none detected":
                    http_stack = val.split()
            elif line_str.startswith("DI:"):
                val = line_str.replace("DI:", "").strip()
                if val and val != "none detected":
                    di_stack = val.split()
            elif line_str.startswith("Serialization:"):
                val = line_str.replace("Serialization:", "").strip()
                if val and val != "none detected":
                    ser_stack = val.split()
            elif line_str.startswith("Third-party SDKs:"):
                val = line_str.replace("Third-party SDKs:", "").strip()
                if val and val != "none detected":
                    sdks = [s.strip() for s in val.split("  ") if s.strip()] or val.split()
            elif "Native libraries" in line_str:
                in_native = True
                continue
            elif in_native:
                if line_str.startswith("Recommended") or line_str.startswith("==="):
                    in_native = False
                elif line_str and line_str != "(none)":
                    native_libs.append(line_str)

        obf_level = "LOW"
        if "HIGH" in obfuscation.upper():
            obf_level = "HIGH"
        elif "MODERATE" in obfuscation.upper():
            obf_level = "MODERATE"

        return {
            "apk_name": apk_path.name,
            "framework": framework,
            "framework_rationale": rationale,
            "obfuscation_level": obf_level,
            "obfuscation_raw": obfuscation,
            "http_stack": http_stack,
            "dependency_injection": di_stack,
            "serialization": ser_stack,
            "third_party_sdks": sdks,
            "native_libraries": native_libs,
            "source": "android-reverse-engineering-skill"
        }

    def _analyze_native_python(self, apk_path: Path) -> Dict[str, Any]:
        """Pure Python fallback analyzer inspecting APK zip entries and DEX string tables."""
        file_list = []
        dex_strings = set()

        with zipfile.ZipFile(apk_path, "r") as z:
            file_list = z.namelist()
            # Extract basic DEX descriptors from classes*.dex
            for name in file_list:
                if re.match(r"^classes\d*\.dex$", name):
                    try:
                        data = z.read(name)
                        # Extract ASCII strings with length >= 8
                        matches = re.findall(b"L[a-zA-Z0-9_/]{8,};", data)
                        for m in matches[:2000]:  # sample representative types
                            clean = m.decode("ascii", errors="ignore").lstrip("L").rstrip(";")
                            dex_strings.add(clean)
                    except Exception:
                        pass

        def has(pattern: str) -> bool:
            rgx = re.compile(pattern)
            return any(rgx.search(f) for f in file_list) or any(rgx.search(s) for s in dex_strings)

        # Framework detection
        framework = "Native Android (Java/Kotlin)"
        rationale = "Standard Android bytecode and resources"

        if has(r"^lib/[^/]+/libflutter\.so$") or has(r"^assets/flutter_assets/"):
            framework = "Flutter"
            rationale = "libflutter.so engine and flutter_assets present"
        elif has(r"^lib/[^/]+/libhermes\.so$") or has(r"^assets/index\.android\.bundle$") or has(r"^lib/[^/]+/libreactnativejni\.so$"):
            framework = "React Native"
            rationale = "React Native bundle / libhermes detected"
        elif has(r"^assets/www/index\.html$") or has(r"^assets/public/index\.html$") or has(r"^assets/index\.html$"):
            framework = "Cordova / Capacitor (WebView hybrid)"
            rationale = "HTML5 web application bundle in assets/"
        elif has(r"^lib/[^/]+/libmonodroid\.so$") or has(r"^assemblies/"):
            framework = "Xamarin / .NET MAUI"
            rationale = ".NET assemblies / libmonodroid present"
        elif has(r"androidx/compose"):
            framework = "Native Android (Kotlin + Jetpack Compose)"
            rationale = "Jetpack Compose runtime libraries detected"

        # HTTP
        http = []
        if has(r"retrofit2"): http.append("Retrofit")
        if has(r"okhttp3"): http.append("OkHttp")
        if has(r"io/ktor"): http.append("Ktor")
        if has(r"com/android/volley"): http.append("Volley")

        # DI
        di = []
        if has(r"dagger/hilt"): di.append("Hilt")
        elif has(r"dagger"): di.append("Dagger")
        if has(r"org/koin"): di.append("Koin")
        if has(r"javax/inject") and not di: di.append("javax.inject")

        # Serialization
        ser = []
        if has(r"kotlinx/serialization"): ser.append("kotlinx.serialization")
        if has(r"com/google/gson"): ser.append("Gson")
        if has(r"com/squareup/moshi"): ser.append("Moshi")
        if has(r"com/fasterxml/jackson"): ser.append("Jackson")

        # Obfuscation estimation
        short_dirs = len(set(f.split("/")[0] for f in file_list if len(f.split("/")[0]) <= 2 and "/" in f))
        if short_dirs > 30:
            obf_level = "HIGH"
        elif short_dirs > 10:
            obf_level = "MODERATE"
        else:
            obf_level = "LOW"

        # Native libs
        native_libs = sorted(list(set(f for f in file_list if f.startswith("lib/") and f.endswith(".so"))))

        # SDKs
        sdks = []
        if has(r"com/google/firebase"): sdks.append("Firebase")
        if has(r"com/google/android/gms"): sdks.append("Google Play Services")
        if has(r"com/facebook"): sdks.append("Facebook SDK")
        if has(r"io/sentry"): sdks.append("Sentry")
        if has(r"com/datadog"): sdks.append("Datadog")
        if has(r"com/appsflyer"): sdks.append("AppsFlyer")

        return {
            "apk_name": apk_path.name,
            "framework": framework,
            "framework_rationale": rationale,
            "obfuscation_level": obf_level,
            "obfuscation_raw": f"{obf_level} ({short_dirs} short namespaces)",
            "http_stack": http,
            "dependency_injection": di,
            "serialization": ser,
            "third_party_sdks": sdks,
            "native_libraries": native_libs,
            "source": "native-python-triage"
        }

    def _derive_strategy(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Selects the targeted conversion strategy according to the architectural fingerprint."""
        framework = report.get("framework", "")
        obf = report.get("obfuscation_level", "LOW")

        if "Flutter" in framework:
            return {
                "name": "Flutter Surface & Window Cursor Strategy",
                "code": "STRATEGY_FLUTTER",
                "preserve_dex": True,  # Dart logic in libapp.so; avoid breaking R8 smali
                "layout_cursor_overlay": True,
                "web_cursor_injection": False,
                "enforce_landscape": True,
                "hardware_accelerate": True,
                "notes": "Dart engine renders to SurfaceView/Impeller. Enforce horizontal 16:9 configChanges & manifest landscape."
            }
        elif "React Native" in framework:
            return {
                "name": "React Native Touch Emulation Strategy",
                "code": "STRATEGY_REACT_NATIVE",
                "preserve_dex": True,
                "layout_cursor_overlay": True,
                "web_cursor_injection": False,
                "enforce_landscape": True,
                "hardware_accelerate": True,
                "notes": "ReactRootView UI. Enforce full 16:9 widescreen resizeableActivity & remote focus marker."
            }
        elif "Cordova" in framework or "WebView" in framework:
            return {
                "name": "Hybrid Web Assets Desktop Cursor Strategy",
                "code": "STRATEGY_HYBRID_WEB",
                "preserve_dex": True,
                "layout_cursor_overlay": True,
                "web_cursor_injection": True,
                "enforce_landscape": True,
                "hardware_accelerate": True,
                "notes": "Inject tv_desktop_cursor.js recursively into all HTML files in assets/ for instant D-Pad mouse navigation."
            }
        elif "Compose" in framework:
            return {
                "name": "Jetpack Compose Big-Screen Focus Strategy",
                "code": "STRATEGY_NATIVE_COMPOSE",
                "preserve_dex": obf == "HIGH",
                "layout_cursor_overlay": True,
                "web_cursor_injection": False,
                "enforce_landscape": True,
                "hardware_accelerate": True,
                "notes": "ComposeView rendering. Enforce defaultFocusHighlightEnabled & landscape window bounds."
            }
        else:
            return {
                "name": "Native Android XML & Remote Marker Strategy",
                "code": "STRATEGY_NATIVE_XML",
                "preserve_dex": obf == "HIGH",
                "layout_cursor_overlay": True,
                "web_cursor_injection": True,  # also check if assets contain web views
                "enforce_landscape": True,
                "hardware_accelerate": True,
                "notes": "Inject @drawable/ic_tv_mouse_cursor overlay, Neon Cyan remote marker, and focusability attributes."
            }

    def save_report(self, report: Dict[str, Any], output_path: Path | str):
        """Persists the reverse engineering report as JSON."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
