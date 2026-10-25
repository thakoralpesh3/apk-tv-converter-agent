"""
Android TV Desktop Mouse Cursor Builder & Injector.
Compiles native Java overlay classes into DEX bytecode and injects
multidex payload and ContentProvider declaration into target APKs.
"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from core.manifest_transformer import ManifestTransformer

BASE_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = Path(__file__).resolve().parent
CURSOR_SRC_DIR = CORE_DIR / "cursor_src"
PRECOMPILED_DEX = CORE_DIR / "tv_cursor.dex"

DEFAULT_TOOLS_DIR = Path(os.environ.get("APK_TOOLS_DIR", Path.home() / ".apk_tv_converter" / "tools"))
WEB2APK_TOOLS_DIR = Path(os.environ.get("WEB2APK_TOOLS_DIR", Path.home() / ".web2apk" / "tools"))
WEB2APK_JDK_DIR = Path(os.environ.get("JAVA_HOME", Path.home() / ".web2apk" / "jdk" / "jdk-17.0.10+7" / "bin"))

PROVIDER_CLASS = "com.tv.cursor.TvCursorInitProvider"

class TVCursorBuilder:
    @staticmethod
    def get_tool_paths() -> Dict[str, Path]:
        """Resolve paths to java, javac, r8, and android.jar."""
        java_bin = shutil.which("java")
        if not java_bin:
            cand = WEB2APK_JDK_DIR / "java"
            if cand.is_file():
                java_bin = cand
            else:
                java_bin = DEFAULT_TOOLS_DIR / "java"
        else:
            java_bin = Path(java_bin)

        javac_bin = shutil.which("javac")
        if not javac_bin:
            cand = WEB2APK_JDK_DIR / "javac"
            if cand.is_file():
                javac_bin = cand
            else:
                javac_bin = Path("/usr/bin/javac")
        else:
            javac_bin = Path(javac_bin)

        android_jar = DEFAULT_TOOLS_DIR / "android.jar"
        r8_jar = WEB2APK_TOOLS_DIR / "r8.jar"

        return {
            "java": java_bin,
            "javac": javac_bin,
            "android_jar": android_jar,
            "r8_jar": r8_jar
        }

    @classmethod
    def compile_dex(
        cls,
        output_dex_path: Optional[Path] = None,
        force: bool = False,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> Path:
        """
        Compiles Java cursor sources to DEX bytecode using javac and D8.
        """
        target_dex = output_dex_path or PRECOMPILED_DEX

        if not force and target_dex.is_file() and target_dex.stat().st_size > 0:
            if log_callback:
                log_callback(f"Using precompiled TV cursor DEX: {target_dex.name} ({target_dex.stat().st_size} bytes)")
            return target_dex

        tools = cls.get_tool_paths()
        if not tools["javac"].is_file() or not tools["android_jar"].is_file() or not tools["r8_jar"].is_file():
            if target_dex.is_file():
                if log_callback:
                    log_callback("Build tools not all present; falling back to precompiled TV cursor DEX.")
                return target_dex
            raise FileNotFoundError("Cannot compile TV cursor: javac, android.jar, or r8.jar missing.")

        java_sources = list(CURSOR_SRC_DIR.rglob("*.java"))
        if not java_sources:
            if target_dex.is_file():
                return target_dex
            raise FileNotFoundError(f"No Java sources found in {CURSOR_SRC_DIR}")

        with tempfile.TemporaryDirectory(prefix="tv_cursor_build_") as tmpdir:
            tmp_path = Path(tmpdir)
            classes_dir = tmp_path / "classes"
            dex_dir = tmp_path / "dex"
            classes_dir.mkdir(parents=True, exist_ok=True)
            dex_dir.mkdir(parents=True, exist_ok=True)

            if log_callback:
                log_callback("Compiling native Android TV cursor Java sources with javac...")

            # 1. Compile Java with javac
            javac_cmd = [
                str(tools["javac"]),
                "-cp", str(tools["android_jar"]),
                "-d", str(classes_dir)
            ] + [str(s) for s in java_sources]

            res = subprocess.run(javac_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"javac compilation failed:\n{res.stderr}")

            compiled_classes = list(classes_dir.rglob("*.class"))
            if not compiled_classes:
                raise RuntimeError("javac did not produce any .class files")

            # 2. Desugar and dex with D8
            if log_callback:
                log_callback("Translating bytecode to Dalvik DEX via D8...")

            d8_cmd = [
                str(tools["java"]),
                "-cp", str(tools["r8_jar"]),
                "com.android.tools.r8.D8",
                "--lib", str(tools["android_jar"]),
                "--release",
                "--min-api", "21",
                "--output", str(dex_dir)
            ] + [str(c) for c in compiled_classes]

            res_d8 = subprocess.run(d8_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res_d8.returncode != 0:
                raise RuntimeError(f"D8 dex compilation failed:\n{res_d8.stderr}")

            produced_dex = dex_dir / "classes.dex"
            if not produced_dex.is_file():
                raise FileNotFoundError("D8 did not produce classes.dex")

            target_dex.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(produced_dex, target_dex)
            if log_callback:
                log_callback(f"Successfully compiled native TV cursor DEX: {target_dex} ({target_dex.stat().st_size} bytes)")

        return target_dex

    @classmethod
    def inject(
        cls,
        decoded_dir: Path,
        transformer: ManifestTransformer,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Injects the native TV cursor into the decoded APK:
        1. Copies tv_cursor.dex as classesN.dex (multidex extension)
        2. Injects ContentProvider into AndroidManifest.xml
        """
        dex_path = cls.compile_dex(log_callback=log_callback)
        if not dex_path.is_file():
            raise FileNotFoundError(f"TV cursor DEX file not found: {dex_path}")

        # Determine next dex index in decoded_dir
        existing_dex = list(decoded_dir.glob("classes*.dex"))
        indices = []
        for f in existing_dex:
            m = re.match(r"^classes(\d*)\.dex$", f.name)
            if m:
                val = m.group(1)
                indices.append(1 if val == "" else int(val))

        next_index = (max(indices) + 1) if indices else 1
        target_dex_name = "classes.dex" if next_index == 1 else f"classes{next_index}.dex"
        target_dex_path = decoded_dir / target_dex_name

        shutil.copy2(dex_path, target_dex_path)
        if log_callback:
            log_callback(f"Injected native TV cursor multidex: {target_dex_name} ({dex_path.stat().st_size} bytes)")

        # Inject ContentProvider into manifest
        pkg_name = transformer.get_package_name()
        authority = f"{pkg_name}.tvcursorinitprovider"
        success = transformer.inject_provider(
            name=PROVIDER_CLASS,
            authorities=authority,
            exported=False,
            init_order=999999
        )

        if success and log_callback:
            log_callback(f"Injected ContentProvider '{PROVIDER_CLASS}' (authority: {authority})")

        return {
            "status": "ok",
            "injected_dex": target_dex_name,
            "provider": PROVIDER_CLASS,
            "authority": authority
        }
