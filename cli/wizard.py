"""
Interactive Rich Terminal Wizard for APK Cross-Conversion.
"""

import sys
import glob
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markup import escape

from core.converter import APKCrossConverter

console = Console()

def run_wizard():
    console.clear()
    banner = """[bold cyan]╔═╗╔═╗╦╔═  ╔╦╗╦  ╦  ╔═╗┌─┐┌┐┌┬  ┬┌─┐┬─┐┌┬┐┌─┐┬─┐[/bold cyan]
[bold cyan]╠═╣╠═╝╠╩╗   ║ ╚╗╔╝  ║  │ ││││└┐┌┘├┤ ├┬┘ │ ├┤ ├┬┘[/bold cyan]
[bold cyan]╩ ╩╩  ╩ ╩   ╩  ╚╝   ╚═╝└─┘┘└┘ └┘ └─┘┴└─ ┴ └─┘┴└─[/bold cyan]
[bold white]Autonomous Smartphone ⇋ Android TV APK Cross-Converter[/bold white]
[dim]Powered by Gemini 4 Argon AI Content Engine[/dim]"""
    console.print(Panel(banner, border_style="cyan", expand=False))

    console.print("\n[bold yellow]🎯 Step 1: Select Input APK[/bold yellow]")
    
    # Check common folders for APKs
    recent_apks = glob.glob("/home/alpesh/Web2APK_Output/*.apk") + \
                  glob.glob("/home/alpesh/APK_TV_Converter_Output/*.apk") + \
                  glob.glob("/home/alpesh/Downloads/*.apk") + \
                  glob.glob("/home/alpesh/Desktop/*.apk")
    
    recent_apks = list(dict.fromkeys(recent_apks))[:6]

    if recent_apks:
        console.print("[dim]Recently detected APKs:[/dim]")
        for idx, apk in enumerate(recent_apks, 1):
            console.print(f"  [cyan]{idx}.[/cyan] {Path(apk).name} [dim]({apk})[/dim]")
        console.print("  [cyan]0.[/cyan] Enter a custom path manually\n")
        
        choice = Prompt.ask("Choose an option", choices=[str(i) for i in range(len(recent_apks) + 1)], default="1")
        if choice != "0":
            input_apk = recent_apks[int(choice) - 1]
        else:
            input_apk = Prompt.ask("Enter full path to APK file")
    else:
        input_apk = Prompt.ask("Enter full path to APK file")

    apk_file = Path(input_apk).expanduser().resolve()
    if not apk_file.is_file():
        console.print(f"[bold red]❌ Error: File not found: {apk_file}[/bold red]")
        return

    console.print(f"\n[green]Selected:[/green] [bold]{apk_file.name}[/bold]")

    console.print("\n[bold yellow]🔄 Step 2: Select Conversion Mode[/bold yellow]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Key", style="bold cyan", width=6)
    table.add_column("Conversion Target", style="bold white")
    table.add_column("Description")
    table.add_row("1", "📺 Smartphone ➔ Android TV", "Injects Leanback launcher, 16:9 banner, TV Remote Marker & D-pad focus, landscape")
    table.add_row("2", "📱 Android TV ➔ Smartphone", "Adds standard launcher icon, mobile touch compatibility, auto-rotation")
    table.add_row("3", "🌐 Universal Hybrid Mode", "Dual-mode APK across phones, tablets, Android TV, Fire Sticks with active Remote Marker")

    console.print(table)
    mode_choice = Prompt.ask("Select mode", choices=["1", "2", "3"], default="1")
    mode_map = {"1": "tv", "2": "mobile", "3": "universal"}
    target_mode = mode_map[mode_choice]

    custom_banner = None
    if target_mode in ("tv", "universal"):
        if Confirm.ask("\nDo you want to provide a custom 16:9 banner image?", default=False):
            custom_banner = Prompt.ask("Enter image path (PNG/JPG)")

    console.print("\n[bold yellow]⚡ Step 3: Processing & Building APK...[/bold yellow]\n")

    converter = APKCrossConverter()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Initializing pipeline...", total=None)

        def log_update(msg: str):
            progress.update(task, description=f"[cyan]{escape(msg[:75])}[/cyan]")

        try:
            result = converter.convert(
                input_apk=apk_file,
                target_mode=target_mode,
                custom_banner_path=custom_banner,
                ai_content=True,
                log_callback=log_update
            )
        except Exception as e:
            console.print(f"\n[bold red]❌ Conversion Failed:[/bold red] {e}")
            return

    console.print("\n[bold green]🎉 Conversion Completed Successfully![/bold green]\n")
    
    out_table = Table(title="Generated APK Details", border_style="green")
    out_table.add_column("Property", style="bold white")
    out_table.add_column("Value", style="bold cyan")
    out_table.add_row("Output File", result["filename"])
    out_table.add_row("Full Path", result["output_apk"])
    out_table.add_row("File Size", f"{result['size_mb']} MB")
    out_table.add_row("Target Mode", result["target_mode"].upper())
    if target_mode in ("tv", "universal"):
        out_table.add_row("Remote Marker", "🎯 Active (Neon Cyan #00E5FF Outline Focus)")
    out_table.add_row("Package", result["package_name"])
    out_table.add_row("SHA256", result["sha256"][:24] + "...")

    console.print(out_table)

    if Confirm.ask("\nOpen output folder now?", default=True):
        import subprocess
        subprocess.run(["xdg-open", str(converter.output_dir)])
