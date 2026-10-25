"""
Low-Level APK Tooling Engine
Executes apktool decoding, resource building, zip-alignment, and APK signature verification.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Callable, Optional

DEFAULT_TOOLS_DIR = Path(os.environ.get("APK_TOOLS_DIR", Path.home() / ".apk_tv_converter" / "tools"))
LOCAL_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"

def _find_binary(preferred: Optional[Path], name: str, fallback_candidates: list[Path]) -> Path:
    if preferred and Path(preferred).is_file():
        return Path(preferred)
    for c in fallback_candidates:
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            return Path(c)
    which_path = shutil.which(name)
    if which_path:
        return Path(which_path)
    return fallback_candidates[0] if fallback_candidates else Path(name)

def _find_jar(preferred: Optional[Path], name: str, fallback_candidates: list[Path]) -> Path:
    if preferred and Path(preferred).is_file():
        return Path(preferred)
    env_key = name.upper().replace("-", "_").replace(".", "_")
    if os.environ.get(env_key) and Path(os.environ[env_key]).is_file():
        return Path(os.environ[env_key])
    for c in fallback_candidates:
        if c and Path(c).is_file():
            return Path(c)
    return fallback_candidates[0] if fallback_candidates else Path(name)

class APKEngine:
    def __init__(
        self,
        java_bin: Optional[Path] = None,
        apktool_jar: Optional[Path] = None,
        signer_jar: Optional[Path] = None,
        aapt2_bin: Optional[Path] = None,
        android_jar: Optional[Path] = None
    ):
        java_candidates = [
            DEFAULT_TOOLS_DIR / "java",
            LOCAL_TOOLS_DIR / "java",
            Path(os.environ.get("JAVA_HOME", "")) / "bin" / "java" if os.environ.get("JAVA_HOME") else None,
            Path("/usr/bin/java")
        ]
        self.java_bin = _find_binary(java_bin, "java", [c for c in java_candidates if c])

        apktool_candidates = [
            DEFAULT_TOOLS_DIR / "apktool.jar",
            LOCAL_TOOLS_DIR / "apktool.jar",
            Path("/usr/local/share/apktool/apktool.jar"),
            Path("/usr/share/apktool/apktool.jar")
        ]
        self.apktool_jar = _find_jar(apktool_jar, "apktool.jar", apktool_candidates)

        signer_candidates = [
            DEFAULT_TOOLS_DIR / "uber-apk-signer.jar",
            LOCAL_TOOLS_DIR / "uber-apk-signer.jar",
            Path("/usr/local/share/uber-apk-signer/uber-apk-signer.jar")
        ]
        self.signer_jar = _find_jar(signer_jar, "uber-apk-signer.jar", signer_candidates)

        aapt2_candidates = [
            DEFAULT_TOOLS_DIR / "aapt2",
            LOCAL_TOOLS_DIR / "aapt2"
        ]
        self.aapt2_bin = _find_binary(aapt2_bin, "aapt2", [c for c in aapt2_candidates if c])

        android_jar_candidates = [
            DEFAULT_TOOLS_DIR / "android.jar",
            LOCAL_TOOLS_DIR / "android.jar",
            Path(os.environ.get("ANDROID_HOME", "")) / "platforms/android-34/android.jar" if os.environ.get("ANDROID_HOME") else None
        ]
        self.android_jar = _find_jar(android_jar, "android.jar", [c for c in android_jar_candidates if c])

    def check_tools(self) -> Dict[str, Any]:
        """Verify presence and functionality of all required build tools."""
        results = {
            "java": False,
            "java_version": "",
            "apktool": False,
            "apktool_version": "",
            "signer": False,
            "all_ready": False
        }

        # Test Java
        if self.java_bin.is_file():
            try:
                res = subprocess.run([str(self.java_bin), "-version"], stderr=subprocess.PIPE, text=True, timeout=15)
                if res.returncode == 0:
                    results["java"] = True
                    results["java_version"] = res.stderr.split("\n")[0]
            except Exception:
                pass

        # Test Apktool
        if results["java"] and self.apktool_jar.is_file():
            try:
                res = subprocess.run(
                    [str(self.java_bin), "-jar", str(self.apktool_jar), "--version"],
                    stdout=subprocess.PIPE,
                    text=True,
                    timeout=15
                )
                if res.returncode == 0:
                    results["apktool"] = True
                    results["apktool_version"] = res.stdout.strip()
            except Exception:
                pass

        # Test Uber-APK-Signer
        if results["java"] and self.signer_jar.is_file():
            try:
                res = subprocess.run(
                    [str(self.java_bin), "-jar", str(self.signer_jar), "--help"],
                    stdout=subprocess.PIPE,
                    text=True,
                    timeout=15
                )
                if res.returncode == 0:
                    results["signer"] = True
            except Exception:
                pass

        # Test Native aapt2
        results["aapt2"] = False
        if self.aapt2_bin.is_file() and os.access(self.aapt2_bin, os.X_OK):
            try:
                res = subprocess.run([str(self.aapt2_bin), "version"], stdout=subprocess.PIPE, text=True, timeout=15)
                if res.returncode == 0:
                    results["aapt2"] = True
                    results["aapt2_version"] = res.stdout.strip()
            except Exception:
                pass

        # Test Android framework jar
        results["android_jar"] = self.android_jar.is_file()

        results["all_ready"] = results["java"] and results["apktool"] and results["signer"]
        return results

    def decode(
        self,
        apk_path: Path,
        destination_dir: Path,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> Path:
        """
        Fast-decode APK resources and manifest without dissassembling DEX bytecode.
        Uses apktool with '-s' (no-source).
        """
        if not apk_path.is_file():
            raise FileNotFoundError(f"Input APK not found: {apk_path}")

        destination_dir.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(self.java_bin),
            "-Xmx768m",
            "-jar",
            str(self.apktool_jar),
            "d",
            "-s",  # Skip smali decompile, keep raw classes.dex for speed and safety
            "-f",  # Force overwrite
            str(apk_path),
            "-o",
            str(destination_dir)
        ]

        if log_callback:
            log_callback(f"Executing: {' '.join(cmd)}")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        for line in proc.stdout:
            clean = line.strip()
            if clean and log_callback:
                log_callback(f"[Apktool Decode] {clean}")

        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"Apktool decode failed with code {proc.returncode}")

        return destination_dir

    def sanitize_resources(
        self,
        decoded_dir: Path,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        """
        Sanitizes extracted resource names that contain '$' or illegal characters.
        AGP/AAPT2 often inlines vector and anim drawables as '$name__0.xml'.
        AAPT2 resource compiler rejects '$' leading characters with 'invalid entry name'.
        This renames them to 'val_name__0.xml' and updates all XML references.
        """
        res_dir = decoded_dir / "res"
        if not res_dir.is_dir():
            return

        renamed_map = {}
        for f in list(res_dir.rglob("*$*")):
            if f.is_file():
                old_name = f.name
                new_name = old_name.replace("$", "val_")
                new_path = f.parent / new_name
                f.rename(new_path)
                renamed_map[old_name.split(".")[0]] = new_name.split(".")[0]

        if not renamed_map:
            return

        if log_callback:
            log_callback(f"Sanitized {len(renamed_map)} inlined vector/drawable resource names.")

        for xml_file in res_dir.rglob("*.xml"):
            try:
                content = xml_file.read_text(encoding="utf-8", errors="ignore")
                if "$" in content:
                    for old_stem, new_stem in renamed_map.items():
                        content = content.replace(f"@{old_stem}", f"@{new_stem}")
                        content = content.replace(f"@drawable/{old_stem}", f"@drawable/{new_stem}")
                        content = content.replace(f'name="{old_stem}"', f'name="{new_stem}"')
                        content = content.replace(f'"{old_stem}"', f'"{new_stem}"')
                    xml_file.write_text(content, encoding="utf-8")
            except Exception:
                pass

    def build(
        self,
        decoded_dir: Path,
        output_apk: Path,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> Path:
        """Rebuild APK from decoded directory using apktool with automatic AAPT1 fallback."""
        output_apk.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(self.java_bin),
            "-Xmx768m",
            "-jar",
            str(self.apktool_jar),
            "b",
        ]
        if self.aapt2_bin.is_file() and os.access(self.aapt2_bin, os.X_OK):
            cmd += ["-a", str(self.aapt2_bin)]
        cmd += [str(decoded_dir), "-o", str(output_apk)]

        if log_callback:
            log_callback(f"Executing: {' '.join(cmd)}")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        for line in proc.stdout:
            clean = line.strip()
            if clean and log_callback:
                log_callback(f"[Apktool Build] {clean}")

        proc.wait()
        if proc.returncode != 0:
            # Automatic fallback to --use-aapt1 for apps with complex/dollar-sign vector resources
            if log_callback:
                log_callback("[Apktool Build] AAPT2 build encountered resource conflicts; retrying with --use-aapt1 engine...")
            
            cmd_fallback = [
                str(self.java_bin),
                "-Xmx768m",
                "-jar",
                str(self.apktool_jar),
                "b",
                "--use-aapt1",
                str(decoded_dir),
                "-o",
                str(output_apk)
            ]
            
            proc_fb = subprocess.Popen(
                cmd_fallback,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            for line in proc_fb.stdout:
                clean = line.strip()
                if clean and log_callback:
                    log_callback(f"[Apktool Build/AAPT1] {clean}")
            
            proc_fb.wait()
            if proc_fb.returncode != 0:
                raise RuntimeError(f"Apktool build failed with code {proc_fb.returncode}")

        return output_apk

    def sign_and_align(
        self,
        unaligned_apk: Path,
        signed_dir: Path,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> Path:
        """
        Zipaligns and signs the APK using uber-apk-signer.
        Generates production-grade debug/release v1, v2, and v3 signatures.
        """
        signed_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(self.java_bin),
            "-jar",
            str(self.signer_jar),
            "-a",
            str(unaligned_apk),
            "--allowResign",
            
            "-o",
            str(signed_dir)
        ]

        if log_callback:
            log_callback(f"Executing: {' '.join(cmd)}")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        for line in proc.stdout:
            clean = line.strip()
            if clean and log_callback:
                log_callback(f"[Signer] {clean}")

        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"APK signing failed with code {proc.returncode}")

        # Look for the generated signed APK
        expected_candidates = list(signed_dir.glob("*-aligned-debugSigned.apk")) + \
                              list(signed_dir.glob("*.apk"))
        
        if not expected_candidates:
            raise FileNotFoundError("Could not find signed APK in output directory")

        return expected_candidates[0]
