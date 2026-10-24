"""
Android Reverse Engineering Bridge
Integrates the android-reverse-engineering toolchain into the APK conversion pipeline.
Provides Phase 0 fast architectural triage (fingerprinting) and jadx decompilation.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

DEFAULT_SKILL_SCRIPT = Path("/home/alpesh/.gemini/config/plugins/android-reverse-engineering-plugin/skills/android-reverse-engineering/scripts/fingerprint.sh")

class ReverseEngineeringBridge:
    @classmethod
    def get_fingerprint_script(cls) -> Optional[Path]:
        """Locates the fingerprint.sh script from the android-reverse-engineering skill."""
        candidates = [
            DEFAULT_SKILL_SCRIPT,
            Path("/home/alpesh/.apk_tv_converter/tools/fingerprint.sh"),
            Path(__file__).resolve().parent.parent / "tools" / "fingerprint.sh"
        ]
        for candidate in candidates:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate
        return None

    @classmethod
    def get_jadx_binary(cls) -> Optional[Path]:
        """Locates the jadx decompiler executable."""
        candidates = [
            shutil.which("jadx"),
            Path.home() / ".local/bin/jadx",
            Path.home() / ".local/share/jadx/bin/jadx",
            Path("/home/alpesh/.apk_tv_converter/tools/jadx/bin/jadx"),
            Path("/home/alpesh/.apk_tv_converter/tools/jadx")
        ]
        for c in candidates:
            if c:
                p = Path(c)
                if p.is_file() and os.access(p, os.X_OK):
                    return p
        return None

    @classmethod
    def check_tools(cls) -> Dict[str, Any]:
        """Checks availability of reverse-engineering tools."""
        fp_script = cls.get_fingerprint_script()
        jadx_bin = cls.get_jadx_binary()
        
        jadx_version = ""
        if jadx_bin:
            try:
                res = subprocess.run([str(jadx_bin), "--version"], stdout=subprocess.PIPE, text=True, timeout=5)
                if res.returncode == 0:
                    jadx_version = res.stdout.strip()
            except Exception:
                pass

        return {
            "fingerprint_ready": fp_script is not None,
            "fingerprint_path": str(fp_script) if fp_script else None,
            "jadx_ready": jadx_bin is not None,
            "jadx_path": str(jadx_bin) if jadx_bin else None,
            "jadx_version": jadx_version,
            "skill_plugin_installed": Path("/home/alpesh/.gemini/config/plugins/android-reverse-engineering-plugin").is_dir()
        }

    @classmethod
    def fingerprint(
        cls,
        apk_path: Path | str,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes Phase 0 Reverse-Engineering Triage on the APK.
        Detects framework, obfuscation level, HTTP stack, DI, and native libraries.
        """
        path = Path(apk_path).resolve()
        if not path.is_file():
            return {
                "success": False,
                "error": f"APK not found: {path}",
                "framework": "Unknown",
                "obfuscation": "Unknown"
            }

        fp_script = cls.get_fingerprint_script()
        if not fp_script:
            # Fallback to internal heuristic
            return cls._fallback_fingerprint(path, log_callback=log_callback)

        try:
            if log_callback:
                log_callback("Running Phase 0 Reverse Engineering Architecture Fingerprint...")

            res = subprocess.run(
                ["/usr/bin/env", "bash", str(fp_script), str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=45
            )

            if res.returncode != 0:
                if log_callback:
                    log_callback(f"[ReverseEngineering] Warning: fingerprint script exited with {res.returncode}")
                return cls._fallback_fingerprint(path, log_callback=log_callback)

            return cls._parse_fingerprint_output(res.stdout, raw_output=res.stdout)

        except Exception as e:
            if log_callback:
                log_callback(f"[ReverseEngineering] Fingerprint exception: {e}")
            return cls._fallback_fingerprint(path, log_callback=log_callback)

    @classmethod
    def _parse_fingerprint_output(cls, output: str, raw_output: str = "") -> Dict[str, Any]:
        """Parses output of fingerprint.sh into structured dictionary."""
        data = {
            "success": True,
            "framework": "Native Android",
            "framework_rationale": "",
            "obfuscation": "LOW",
            "http_stack": [],
            "di": [],
            "serialization": [],
            "third_party_sdks": [],
            "native_libs": [],
            "recommended_next_step": "",
            "raw_output": raw_output
        }

        for line in output.splitlines():
            line_str = line.strip()
            if line_str.startswith("Framework:"):
                data["framework"] = line_str.replace("Framework:", "").strip()
            elif line_str.startswith("Rationale:"):
                data["framework_rationale"] = line_str.replace("Rationale:", "").strip()
            elif line_str.startswith("Obfuscation:"):
                data["obfuscation"] = line_str.replace("Obfuscation:", "").strip()
            elif line_str.startswith("HTTP stack:"):
                items = line_str.replace("HTTP stack:", "").strip().split()
                data["http_stack"] = [i for i in items if i]
            elif line_str.startswith("DI:"):
                items = line_str.replace("DI:", "").strip().split()
                data["di"] = [i for i in items if i]
            elif line_str.startswith("Serialization:"):
                items = line_str.replace("Serialization:", "").strip().split()
                data["serialization"] = [i for i in items if i]
            elif line_str.startswith("Third-party SDKs:"):
                data["third_party_sdks"] = [s.strip() for s in line_str.replace("Third-party SDKs:", "").strip().split() if s.strip()]
            elif line_str.startswith("Recommended next step:"):
                data["recommended_next_step"] = line_str.replace("Recommended next step:", "").strip()

        return data

    @classmethod
    def _fallback_fingerprint(
        cls,
        apk_path: Path,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """Internal lightweight zip-inspection fallback if fingerprint.sh is unavailable."""
        import zipfile
        if log_callback:
            log_callback("Running internal zip-table architecture scan...")

        framework = "Native Android (Java/Kotlin)"
        rationale = "Standard classes.dex structure"
        http_stack = []
        sdks = []
        native_libs = []

        try:
            with zipfile.ZipFile(apk_path, "r") as z:
                names = set(z.namelist())

                # Check framework markers
                if any("libflutter.so" in n or "flutter_assets/" in n for n in names):
                    framework = "Flutter"
                    rationale = "libflutter.so / flutter_assets detected"
                elif any("libreactnativejni.so" in n or "index.android.bundle" in n for n in names):
                    framework = "React Native"
                    rationale = "libreactnativejni.so / bundle detected"
                elif any("libunity.so" in n for n in names):
                    framework = "Unity 3D"
                    rationale = "libunity.so detected"
                elif any("assets/www/" in n or "cordova" in n.lower() for n in names):
                    framework = "Cordova / Capacitor (Hybrid Web)"
                    rationale = "assets/www Web assets detected"

                # Detect native architectures
                for n in names:
                    if n.startswith("lib/"):
                        parts = n.split("/")
                        if len(parts) >= 2 and parts[1] not in native_libs:
                            native_libs.append(parts[1])

                # Check third-party markers
                if any("firebase" in n.lower() for n in names):
                    sdks.append("Firebase")
                if any("play-services" in n.lower() for n in names):
                    sdks.append("Google Play Services")

        except Exception as e:
            if log_callback:
                log_callback(f"Fallback scan error: {e}")

        return {
            "success": True,
            "framework": framework,
            "framework_rationale": rationale,
            "obfuscation": "UNKNOWN",
            "http_stack": http_stack,
            "di": [],
            "serialization": [],
            "third_party_sdks": sdks,
            "native_libs": native_libs,
            "recommended_next_step": "Standard APKTool rebuild",
            "raw_output": f"Fallback scan: {framework}"
        }

    @classmethod
    def decompile_with_jadx(
        cls,
        apk_path: Path | str,
        output_dir: Path | str,
        timeout: int = 180,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Decompiles APK to Java/Kotlin source code using jadx.
        """
        jadx_bin = cls.get_jadx_binary()
        if not jadx_bin:
            return {
                "success": False,
                "error": "jadx executable not found. Run install-dep.sh jadx or install jadx."
            }

        in_path = Path(apk_path).resolve()
        out_path = Path(output_dir).resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(jadx_bin),
            "-d", str(out_path),
            "--no-imports",
            "--show-bad-code",
            str(in_path)
        ]

        if log_callback:
            log_callback(f"Executing jadx decompilation: {' '.join(cmd)}")

        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
            return {
                "success": proc.returncode == 0,
                "output_dir": str(out_path),
                "returncode": proc.returncode,
                "log": proc.stdout
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"jadx decompilation timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}
