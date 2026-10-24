"""
High-Level APK Cross-Converter Orchestrator
Coordinates bi-directional conversion between Smartphone, Android TV, and Universal APKs.
Integrated with Gemini 4 Argon AI Content Engine for Big-Screen Audits and Store Listings.
"""

import os
import json
import shutil
import tempfile
import hashlib
from pathlib import Path
from typing import Dict, Any, Callable, Optional

from core.apk_engine import APKEngine
from core.manifest_transformer import ManifestTransformer
from core.banner_generator import generate_tv_banner
from core.icon_generator import ensure_smartphone_icons
from core.dpad_optimizer import optimize_for_tv_navigation
from core.ai_content_engine import GeminiAIContentEngine
from core.re_analyzer import ReverseEngineeringAnalyzer
from core.cursor_builder import TVCursorBuilder

DEFAULT_OUTPUT_DIR = Path("/home/alpesh/APK_TV_Converter_Output")

def calculate_sha256(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()

class APKCrossConverter:
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.engine = APKEngine()
        self.re_analyzer = ReverseEngineeringAnalyzer()

    def convert(
        self,
        input_apk: Path | str,
        target_mode: str = "tv",  # "tv", "mobile", or "universal"
        custom_banner_path: Optional[Path | str] = None,
        orientation: Optional[str] = None,
        pure_tv: Optional[bool] = None,
        ai_content: bool = True,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Execute full cross-conversion pipeline with Gemini 4 Argon content creation.
        """
        input_path = Path(input_apk).resolve()
        if not input_path.is_file():
            raise FileNotFoundError(f"Input APK not found: {input_path}")

        target_mode = target_mode.lower().strip()
        if target_mode not in ("tv", "mobile", "universal"):
            raise ValueError(f"Invalid target mode: {target_mode}. Must be 'tv', 'mobile', or 'universal'.")

        if pure_tv is None:
            pure_tv = (target_mode == "tv")

        def _log(msg: str):
            if log_callback:
                log_callback(msg)
            else:
                print(f"[Cross-Converter] {msg}")

        _log(f"Starting conversion for: {input_path.name}")
        _log(f"Target Mode: {target_mode.upper()}")

        # Verify build tools first
        tools_status = self.engine.check_tools()
        if not tools_status["all_ready"]:
            raise RuntimeError(f"Build tools not ready: {tools_status}")

        work_dir = Path(tempfile.mkdtemp(prefix="apk_convert_"))
        decoded_dir = work_dir / "decoded"
        unaligned_apk = work_dir / "rebuilt_unaligned.apk"
        signed_dir = work_dir / "signed"

        try:
            # Step 1: Deep Reverse Engineering & Architectural Fingerprinting
            _log("Phase 1/5: Reverse-engineering APK architecture & framework fingerprinting...")
            re_report = self.re_analyzer.analyze(input_path, log_callback=_log)
            _log(f"  • Framework: {re_report['framework']} | Obfuscation: {re_report['obfuscation_level']}")
            if re_report.get("http_stack"):
                _log(f"  • HTTP Stack: {', '.join(re_report['http_stack'])}")
            if re_report.get("third_party_sdks"):
                _log(f"  • Notable SDKs: {', '.join(re_report['third_party_sdks'])}")

            # Step 2: Decode APK
            _log("Decoding APK resources and manifest...")
            self.engine.decode(input_path, decoded_dir, log_callback=_log)
            self.engine.sanitize_resources(decoded_dir, log_callback=_log)

            # Step 3: Parse and Inspect Manifest
            manifest_path = decoded_dir / "AndroidManifest.xml"
            if not manifest_path.is_file():
                raise FileNotFoundError("Decoded APK is missing AndroidManifest.xml")

            transformer = ManifestTransformer(manifest_path)
            orig_info = transformer.inspect_current_mode()
            pkg_name = orig_info["package"]
            _log(f"Detected Original App: {pkg_name} ({orig_info['detected_mode'].upper()})")

            # Step 4: AI-Assisted Metadata Synthesis
            ai_banner_meta = {}
            if ai_content and target_mode in ("tv", "universal") and not custom_banner_path:
                _log("✨ Invoking Gemini 4 Argon to generate TV banner aesthetic & tagline...")
                try:
                    ai_banner_meta = GeminiAIContentEngine.generate_tv_banner_content(
                        app_name=input_path.stem,
                        package_name=pkg_name,
                        detected_mode=orig_info["detected_mode"]
                    )
                    _log(f"  • AI Tagline: \"{ai_banner_meta.get('tagline')}\" [Theme: {ai_banner_meta.get('color_theme')}] ({ai_banner_meta.get('model')})")
                except Exception as e:
                    _log(f"  [AI Advisor] Fallback to default styling: {e}")

            # Step 5: Apply transformations
            _log(f"Phase 2/5: Applying {target_mode.upper()} transformations & desktop cursor overlay...")
            manifest_changes = []

            if target_mode == "tv":
                _log("Synthesizing / Injecting 16:9 Android TV Leanback Banner...")
                banner_res = generate_tv_banner(
                    decoded_dir,
                    app_label=input_path.stem,
                    custom_banner_path=custom_banner_path,
                    tagline=ai_banner_meta.get("tagline"),
                    color_theme=ai_banner_meta.get("color_theme", "cyan_indigo"),
                    badge_text=ai_banner_meta.get("badge_text", "ANDROID TV EDITION")
                )
                tv_orientation = orientation or "landscape"
                res = transformer.transform_to_tv(
                    banner_res=banner_res,
                    orientation=tv_orientation,
                    pure_tv=pure_tv
                )
                manifest_changes = res["changes"]

                _log("Activating Android TV Remote Marker & Desktop Mouse Cursor Navigation...")
                optimize_for_tv_navigation(decoded_dir, re_report=re_report, log_callback=_log)
                _log("Injecting Native Android TV Desktop Mouse Cursor Engine (classesN.dex & ContentProvider)...")
                cursor_info = TVCursorBuilder.inject(decoded_dir, transformer, log_callback=_log)
                manifest_changes.append(f"Injected native TV cursor engine ({cursor_info['injected_dex']} / {cursor_info['provider']})")

            elif target_mode == "mobile":
                _log("Ensuring smartphone launcher icons across mipmaps...")
                icon_res = ensure_smartphone_icons(decoded_dir, app_label=input_path.stem)
                mobile_orientation = orientation or "unspecified"
                res = transformer.transform_to_mobile(
                    icon_res=icon_res,
                    orientation=mobile_orientation
                )
                manifest_changes = res["changes"]

            elif target_mode == "universal":
                _log("Synthesizing Leanback TV Banner and normalising icons...")
                banner_res = generate_tv_banner(
                    decoded_dir,
                    app_label=input_path.stem,
                    custom_banner_path=custom_banner_path,
                    tagline=ai_banner_meta.get("tagline"),
                    color_theme=ai_banner_meta.get("color_theme", "cyan_indigo"),
                    badge_text=ai_banner_meta.get("badge_text", "UNIVERSAL EDITION")
                )
                icon_res = ensure_smartphone_icons(decoded_dir, app_label=input_path.stem)
                res = transformer.transform_to_universal(
                    banner_res=banner_res,
                    icon_res=icon_res
                )
                manifest_changes = res["changes"]
                _log("Activating Android TV Remote Marker & Desktop Mouse Cursor Navigation...")
                optimize_for_tv_navigation(decoded_dir, re_report=re_report, log_callback=_log)
                _log("Injecting Native Android TV Desktop Mouse Cursor Engine (classesN.dex & ContentProvider)...")
                cursor_info = TVCursorBuilder.inject(decoded_dir, transformer, log_callback=_log)
                manifest_changes.append(f"Injected native TV cursor engine ({cursor_info['injected_dex']} / {cursor_info['provider']})")

            for change in manifest_changes:
                _log(f"  • {change}")

            # Step 5: Rebuild APK
            _log("Phase 3/5: Compiling resources and assembling APK...")
            self.engine.build(decoded_dir, unaligned_apk, log_callback=_log)

            # Step 6: Sign & Align
            _log("Phase 4/5: Aligning and signing APK (v1/v2/v3 signatures)...")
            final_signed_temp = self.engine.sign_and_align(unaligned_apk, signed_dir, log_callback=_log)

            # Step 7: Move to Output directory
            _log("Phase 5/5: Exporting final APK to Output directory...")
            base_stem = input_path.stem.replace("-smartphone", "").replace("-android-tv", "").replace("-universal", "")
            final_filename = f"{base_stem}-converted-{target_mode}.apk"
            destination_apk = self.output_dir / final_filename

            shutil.copy2(final_signed_temp, destination_apk)

            apk_size_mb = destination_apk.stat().st_size / (1024 * 1024)
            sha256_hash = calculate_sha256(destination_apk)

            # Step 8: Generate AI Store Copy & TV Audit Reports
            ai_reports = {}
            if ai_content:
                _log("✨ Generating Gemini 4 Argon Store Listing & Compatibility Audit...")
                try:
                    audit_res = GeminiAIContentEngine.audit_apk_for_tv(orig_info, pkg_name)
                    copy_res = GeminiAIContentEngine.generate_store_copy(input_path.stem, pkg_name, target_mode)
                    
                    # Save audit json
                    audit_file = self.output_dir / f"{base_stem}-AI-TV-Audit.json"
                    with open(audit_file, "w", encoding="utf-8") as f:
                        json.dump(audit_res, f, indent=2)

                    # Save store copy markdown
                    copy_file = self.output_dir / f"{base_stem}-AI-Store-Listing.md"
                    md_content = f"""# {copy_res.get('title', input_path.stem)}

**Package**: `{pkg_name}`
**Target**: `{target_mode.upper()}`
**Model**: `{copy_res.get('model', 'Gemini 4 Argon')}`

---

## Short Tagline
> {copy_res.get('short_description', '')}

## Key Highlights
"""
                    for h in copy_res.get("highlights", []):
                        md_content += f"- {h}\n"

                    md_content += f"\n## Description\n{copy_res.get('full_description', '')}\n"
                    md_content += f"\n## Remote Control Navigation Guide\n{copy_res.get('remote_guide', '')}\n"

                    with open(copy_file, "w", encoding="utf-8") as f:
                        f.write(md_content)

                    ai_reports = {
                        "audit": audit_res,
                        "store_copy": copy_res,
                        "audit_path": str(audit_file),
                        "copy_path": str(copy_file)
                    }
                    _log(f"  ✓ Saved AI Store Listing: {copy_file.name}")
                    _log(f"  ✓ Saved TV Audit (Score: {audit_res.get('readiness_score')}/100): {audit_file.name}")
                except Exception as e:
                    _log(f"  [AI Reports] Skipped saving extra documents: {e}")

            # Save Reverse Engineering Analysis Report
            re_file = self.output_dir / f"{base_stem}-reverse-engineering-report.json"
            try:
                self.re_analyzer.save_report(re_report, re_file)
                _log(f"  ✓ Saved Reverse-Engineering Report: {re_file.name}")
            except Exception as e:
                _log(f"  [Reverse Engineering] Skipped report file: {e}")

            _log(f"✓ Success! Output generated: {destination_apk.name} ({apk_size_mb:.2f} MB)")

            return {
                "status": "success",
                "output_apk": str(destination_apk),
                "filename": destination_apk.name,
                "size_mb": round(apk_size_mb, 2),
                "sha256": sha256_hash,
                "package_name": pkg_name,
                "original_mode": orig_info["detected_mode"],
                "target_mode": target_mode,
                "manifest_changes": manifest_changes,
                "ai_content": ai_reports,
                "re_report": re_report,
                "re_report_path": str(re_file)
            }

        finally:
            if work_dir.exists():
                shutil.rmtree(work_dir, ignore_errors=True)
