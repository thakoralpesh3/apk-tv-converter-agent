#!/usr/bin/env python3
"""
APK TV & Smartphone Cross-Converter AI Agent
Autonomous Agent for bi-directional conversion between Smartphone APKs and Android TV APKs.
Powered by Gemini 4 Argon AI Content Engine.
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rich.markup import escape

# Add agent root to sys.path
AGENT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENT_ROOT))

from core.converter import APKCrossConverter, DEFAULT_OUTPUT_DIR
from core.apk_engine import APKEngine
from core.ai_content_engine import GeminiAIContentEngine
from core.re_analyzer import ReverseEngineeringAnalyzer
from cli.wizard import run_wizard
from watcher.dropzone import start_dropzone_watcher
from web.server import start_server

console = Console()

def print_banner():
    ai_status = "[bold magenta]● Online (Gemini 4 Argon)[/bold magenta]" if GeminiAIContentEngine.is_available() else "[yellow]📴 Local Zero-Network Fallback Engine[/yellow]"
    banner = f"""[bold cyan]╔═╗╔═╗╦╔═  ╔╦╗╦  ╦  ╔═╗┌─┐┌┐┌┬  ┬┌─┐┬─┐┌┬┐┌─┐┬─┐[/bold cyan]
[bold cyan]╠═╣╠═╝╠╩╗   ║ ╚╗╔╝  ║  │ ││││└┐┌┘├┤ ├┬┘ │ ├┤ ├┬┘[/bold cyan]
[bold cyan]╩ ╩╩  ╩ ╩   ╩  ╚╝   ╚═╝└─┘┘└┘ └┘ └─┘┴└─ ┴ └─┘┴└─[/bold cyan]
[bold white]Autonomous Smartphone ⇋ Android TV Cross-Conversion Studio[/bold white]
[dim]Leanback Injector • Adaptive Banner Synthesis • Touchscreen & D-Pad Engine[/dim]
Status: {ai_status}"""
    console.print(Panel(banner, border_style="cyan", expand=False))

def check_environment():
    print_banner()
    console.print("\n[bold magenta]🛠️ Environment & Tooling Diagnostics[/bold magenta]\n")
    engine = APKEngine()
    status = engine.check_tools()

    table = Table(title="Agent Toolchain & Dependencies", border_style="cyan")
    table.add_column("Component", style="bold white")
    table.add_column("Location / Detail", style="dim")
    table.add_column("Status", style="bold")

    # AI Content Engine
    ai_model = GeminiAIContentEngine.get_preferred_model()
    ai_st = f"[green]✓ Online ({ai_model})[/green]" if GeminiAIContentEngine.is_available() else "[yellow]Local Heuristic Fallback[/yellow]"
    table.add_row("Gemini AI Content Engine", f"Tier-1 Model: {ai_model}", ai_st)

    # Java
    j_status = "[green]✓ Ready[/green]" if status["java"] else "[red]✗ Missing[/red]"
    table.add_row("Java OpenJDK 17", status.get("java_version", str(engine.java_bin)), j_status)

    # Apktool
    a_status = f"[green]✓ Ready (v{status.get('apktool_version')})[/green]" if status["apktool"] else "[red]✗ Missing[/red]"
    table.add_row("Apktool Decompiler & Rebuilder", str(engine.apktool_jar), a_status)

    # Signer
    s_status = "[green]✓ Ready (v1+v2+v3)[/green]" if status["signer"] else "[red]✗ Missing[/red]"
    table.add_row("Uber-APK-Signer & Zipalign", str(engine.signer_jar), s_status)

    # Native AAPT2
    a2_status = "[green]✓ Ready[/green]" if status.get("aapt2") else "[yellow]Optional[/yellow]"
    table.add_row("Android Asset Packaging (aapt2)", str(engine.aapt2_bin), a2_status)

    # Android Platform SDK
    jar_status = "[green]✓ Ready (API 34/33)[/green]" if status.get("android_jar") else "[yellow]Optional[/yellow]"
    table.add_row("Android SDK Platform Jar", str(engine.android_jar), jar_status)

    # Output Dir
    out_dir = DEFAULT_OUTPUT_DIR
    out_status = "[green]✓ Accessible[/green]" if out_dir.exists() else "[yellow]Created on demand[/yellow]"
    table.add_row("Output Directory", str(out_dir), out_status)

    # Dropzone Dir
    drop_dir = Path("/home/alpesh/APK_TV_Converter_Dropzone")
    drop_status = "[green]✓ Ready[/green]" if drop_dir.exists() else "[yellow]Created on demand[/yellow]"
    table.add_row("Dropzone Directory", str(drop_dir), drop_status)

    # Reverse Engineering Engine
    re_analyzer = ReverseEngineeringAnalyzer()
    re_status = re_analyzer.check_tools()
    fp_st = "[green]✓ Ready (fingerprint.sh)[/green]" if re_status["fingerprint_ready"] else "[yellow]Internal Fallback[/yellow]"
    table.add_row("Architecture Fingerprinting", re_status.get("fingerprint_path") or "Built-in Triage", fp_st)

    jadx_st = f"[green]✓ Ready (v{re_status.get('jadx_version')})[/green]" if re_status["jadx_ready"] else "[yellow]Optional (Phase 2 Source Decompiler)[/yellow]"
    table.add_row("JADX Decompiler Engine", re_status.get("jadx_path") or "Not configured", jadx_st)

    console.print(table)

    if status["all_ready"]:
        console.print("\n[bold green]✓ All core systems operational! Ready to convert APKs.[/bold green]\n")
    else:
        console.print("\n[bold red]⚠️ Some dependencies need attention.[/bold red]\n")

def main():
    parser = argparse.ArgumentParser(
        description="APK Cross-Converter AI Agent: Convert Smartphone APKs to Android TV & vice versa with Gemini 4 Argon"
    )
    parser.add_argument("--gui", "--web", action="store_true", help="Launch Web Studio Dashboard")
    parser.add_argument("--wizard", action="store_true", help="Launch Interactive Terminal Wizard")
    parser.add_argument("--convert", type=str, metavar="APK_PATH", help="Convert an APK via CLI")
    parser.add_argument("--fingerprint", type=str, metavar="APK_PATH", help="Run Phase 0 reverse-engineering architecture fingerprinting on an APK")
    parser.add_argument("--decompile", type=str, metavar="APK_PATH", help="Decompile APK to Java/Kotlin source code using JADX")
    parser.add_argument("--mode", type=str, choices=["tv", "mobile", "universal"], default="tv", help="Conversion target mode")
    parser.add_argument("--banner", type=str, metavar="IMAGE_PATH", help="Custom 16:9 banner image for TV")
    parser.add_argument("--orientation", type=str, help="Override screen orientation")
    parser.add_argument("--pure-tv", action="store_true", help="Pure TV mode (removes phone LAUNCHER category)")
    parser.add_argument("--no-ai", action="store_true", help="Disable Gemini AI content generation")
    parser.add_argument("--ai-audit", type=str, metavar="APK_PATH", help="Run Gemini 4 Argon big-screen compatibility audit")
    parser.add_argument("--ai-copy", type=str, metavar="APK_PATH", help="Generate Gemini 4 Argon Play Store listing copy")
    parser.add_argument("--set-model", type=str, help="Set preferred Gemini AI model (e.g. 'gemini-4-argon')")
    parser.add_argument("--watch", action="store_true", help="Start Dropzone Auto-Watcher")
    parser.add_argument("--preview", type=str, metavar="APK_PATH_OR_NAME", help="Launch Android TV Live Preview Studio for an APK")
    parser.add_argument("--check-env", action="store_true", help="Run toolchain diagnostics")
    parser.add_argument("--open-output", action="store_true", help="Open output folder in file manager")
    parser.add_argument("--sync-github", nargs="?", const="", metavar="COMMIT_MSG", help="Commit and push all changes to GitHub origin main")
    parser.add_argument("--watch-sync", action="store_true", help="Start background automatic GitHub sync daemon")
    parser.add_argument("--port", type=int, default=8877, help="Port for web dashboard")

    args = parser.parse_args()

    if args.sync_github is not None:
        print_banner()
        console.print("\n[bold cyan]🚀 Syncing Agent to GitHub...[/bold cyan]")
        sync_script = AGENT_ROOT / "sync_to_github.sh"
        msg = args.sync_github.strip()
        cmd = [str(sync_script)] + ([msg] if msg else [])
        subprocess.run(cmd)
        return

    if args.watch_sync:
        print_banner()
        console.print("\n[bold cyan]🔍 Starting Antigravity Auto-Sync Watcher Daemon...[/bold cyan]")
        watcher_script = AGENT_ROOT / "scripts" / "auto_git_sync.py"
        subprocess.run([sys.executable, str(watcher_script)])
        return

    if args.set_model:
        GeminiAIContentEngine.set_preferred_model(args.set_model)
        console.print(f"[bold green]✓ Preferred model set to:[/bold green] {args.set_model}")
        return

    if args.check_env:
        check_environment()
        return

    if args.fingerprint:
        print_banner()
        apk_target = Path(args.fingerprint).resolve()
        if not apk_target.is_file():
            console.print(f"[bold red]✗ Error:[/bold red] File not found: {apk_target}")
            return
        console.print(f"\n[bold magenta]🔬 Running Reverse-Engineering Architectural Triage on:[/bold magenta] {apk_target.name}\n")
        analyzer = ReverseEngineeringAnalyzer()
        report = analyzer.analyze(apk_target)

        table = Table(title=f"Reverse Engineering Blueprint: {apk_target.name}", border_style="magenta")
        table.add_column("Property", style="bold white")
        table.add_column("Analysis / Result", style="bold cyan")

        table.add_row("Framework", f"{report.get('framework')} ([dim]{report.get('framework_rationale')}[/dim])")
        table.add_row("Obfuscation Level", report.get("obfuscation_level", "LOW"))
        table.add_row("HTTP Network Stack", ", ".join(report.get("http_stack", [])) or "Standard Android HttpURLConnection")
        table.add_row("Dependency Injection", ", ".join(report.get("dependency_injection", [])) or "None")
        table.add_row("Serialization", ", ".join(report.get("serialization", [])) or "Standard")
        table.add_row("Third-Party SDKs", ", ".join(report.get("third_party_sdks", [])) or "None")
        table.add_row("Native CPU Architectures", ", ".join(report.get("native_libraries", [])) or "Pure Java/Kotlin Bytecode")
        strat = report.get("conversion_strategy", {})
        table.add_row("Recommended TV Strategy", f"[bold green]{strat.get('name')}[/bold green]\n[dim]{strat.get('notes')}[/dim]")
        console.print(table)
        return

    if args.decompile:
        print_banner()
        apk_target = Path(args.decompile).resolve()
        if not apk_target.is_file():
            console.print(f"[bold red]✗ Error:[/bold red] File not found: {apk_target}")
            return
        out_dir = DEFAULT_OUTPUT_DIR / f"{apk_target.stem}_decompiled_source"
        console.print(f"\n[bold cyan]🛠️ Decompiling APK to Java/Kotlin source:[/bold cyan] {apk_target.name} -> {out_dir}")
        analyzer = ReverseEngineeringAnalyzer()
        res = analyzer.decompile(apk_target, out_dir, log_callback=lambda msg: console.print(f"  [dim]{escape(msg)}[/dim]"))
        if res.get("success"):
            console.print(f"\n[bold green]✓ Decompilation Successful![/bold green] Output in: {out_dir}")
        else:
            console.print(f"\n[bold red]✗ Decompilation Failed:[/bold red] {res.get('error')}")
        return

    if args.open_output:
        subprocess.run(["xdg-open", str(DEFAULT_OUTPUT_DIR)])
        return

    if args.ai_audit:
        print_banner()
        console.print(f"\n[bold yellow]🔍 Running Big-Screen Compatibility Audit:[/bold yellow] {args.ai_audit}")
        audit = GeminiAIContentEngine.audit_apk_for_tv({}, Path(args.ai_audit).stem)
        console.print(f"\n[bold green]Score: {audit.get('readiness_score')}/100 ({audit.get('grade')})[/bold green]")
        console.print(f"[cyan]Summary:[/cyan] {audit.get('summary')}")
        console.print("\n[bold]Recommendations:[/bold]")
        for r in audit.get("dpad_recommendations", []):
            console.print(f"  • {r}")
        console.print(f"\n[dim]Engine: {audit.get('model')}[/dim]\n")
        return

    if args.ai_copy:
        print_banner()
        console.print(f"\n[bold yellow]📝 Generating Play Store Listing Copy:[/bold yellow] {args.ai_copy}")
        copy = GeminiAIContentEngine.generate_store_copy(Path(args.ai_copy).stem, "com.app", args.mode)
        console.print(f"\n[bold cyan]{copy.get('title')}[/bold cyan]")
        console.print(f"[italic]{copy.get('short_description')}[/italic]\n")
        console.print(copy.get("full_description", ""))
        console.print(f"\n[dim]Engine: {copy.get('model')}[/dim]\n")
        return

    if args.preview:
        print_banner()
        apk_target = args.preview
        target_path = Path(apk_target)
        filename = None
        if target_path.is_file():
            filename = target_path.name
        else:
            from web.server import get_apk_path
            found = get_apk_path(apk_target)
            if found:
                filename = found.name
            else:
                console.print(f"[bold red]✗ Error:[/bold red] Could not locate APK '{apk_target}' in outputs or search directories.")
                return

        import socket
        import webbrowser
        import time

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_running = (s.connect_ex(('127.0.0.1', args.port)) == 0)
        s.close()

        preview_url = f"http://localhost:{args.port}/preview/{filename}"
        console.print(f"\n[bold cyan]📺 Android TV Live Preview Studio[/bold cyan]")
        console.print(f"[bold white]Target APK:[/bold white] {filename}")
        console.print(f"[bold green]Studio URL:[/bold green] {preview_url}\n")

        if not server_running:
            console.print("[dim]Starting Web Studio server in background...[/dim]")
            subprocess.Popen(
                [sys.executable, str(AGENT_ROOT / "agent.py"), "--gui", "--port", str(args.port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # Wait up to 3 seconds for server to bind
            for _ in range(15):
                time.sleep(0.2)
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if s.connect_ex(('127.0.0.1', args.port)) == 0:
                    s.close()
                    break
                s.close()

        try:
            webbrowser.open(preview_url)
        except Exception:
            pass

        console.print(f"[bold green]✓ Live Preview Studio active at {preview_url}[/bold green]")
        console.print("[cyan]Controls:[/cyan] Use Virtual D-Pad / [bold white]Arrow Keys[/bold white] & [bold white]Enter[/bold white] for Remote Marker, or press [bold white]M[/bold white] for Mouse Mode.\n")
        return

    if args.watch:
        print_banner()
        start_dropzone_watcher()
        return

    if args.convert:
        print_banner()
        converter = APKCrossConverter()
        console.print(f"\n[bold yellow]Converting:[/bold yellow] {args.convert}")
        console.print(f"[bold cyan]Target Mode:[/bold cyan] {args.mode.upper()}\n")

        res = converter.convert(
            input_apk=args.convert,
            target_mode=args.mode,
            custom_banner_path=args.banner,
            orientation=args.orientation,
            pure_tv=args.pure_tv,
            ai_content=not args.no_ai,
            log_callback=lambda msg: console.print(f"  [dim]{escape(msg)}[/dim]")
        )

        console.print(f"\n[bold green]✓ Conversion Successful![/bold green]")
        console.print(f"Output File: [bold cyan]{res['output_apk']}[/bold cyan] ({res['size_mb']} MB)")
        if res.get("ai_content", {}).get("copy_path"):
            console.print(f"AI Store Copy: [bold purple]{res['ai_content']['copy_path']}[/bold purple]")
        return

    if args.gui:
        print_banner()
        start_server(port=args.port)
        return

    # Default to wizard
    run_wizard()

if __name__ == "__main__":
    main()
