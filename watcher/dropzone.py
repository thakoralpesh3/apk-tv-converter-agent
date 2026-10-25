"""
Dropzone Auto-Watcher for APK Cross-Conversion.
Automatically processes APK files dropped into ~/APK_TV_Converter_Dropzone.
"""

import time
import shutil
from pathlib import Path
from typing import Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from rich.console import Console

from core.converter import APKCrossConverter
from core.manifest_transformer import ManifestTransformer
from core.apk_engine import APKEngine

console = Console()

class APKDropHandler(FileSystemEventHandler):
    def __init__(self, dropzone_dir: Path, output_dir: Path):
        self.dropzone_dir = dropzone_dir
        self.output_dir = output_dir
        self.converter = APKCrossConverter(output_dir)
        self.processed_dir = dropzone_dir / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.processing = set()

    def on_created(self, event):
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        if file_path.suffix.lower() == ".apk" and "processed" not in file_path.parts:
            self._handle_apk(file_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        dest_path = Path(event.dest_path)
        if dest_path.suffix.lower() == ".apk" and "processed" not in dest_path.parts:
            self._handle_apk(dest_path)

    def _handle_apk(self, apk_path: Path):
        if apk_path in self.processing:
            return
        self.processing.add(apk_path)

        console.print(f"\n[bold yellow]⚡ Dropzone Detected New APK:[/bold yellow] {apk_path.name}")
        # Wait briefly for file write completion
        time.sleep(1.5)

        # Determine target mode based on folder structure or smart auto-detection
        rel_parts = apk_path.relative_to(self.dropzone_dir).parts
        if "to_tv" in rel_parts:
            mode = "tv"
        elif "to_mobile" in rel_parts:
            mode = "mobile"
        elif "universal" in rel_parts:
            mode = "universal"
        else:
            # Smart auto-detection: inspect APK
            mode = "tv"  # default
            try:
                # If name contains 'tv', convert to mobile
                if "tv" in apk_path.stem.lower() and "phone" not in apk_path.stem.lower():
                    mode = "mobile"
                else:
                    mode = "tv"
            except Exception:
                mode = "tv"

        console.print(f"[cyan]Target Mode:[/cyan] [bold]{mode.upper()}[/bold]")

        try:
            res = self.converter.convert(
                input_apk=apk_path,
                target_mode=mode,
                log_callback=lambda msg: console.print(f"  [dim]{msg[:80]}[/dim]")
            )
            console.print(f"[bold green]✓ Conversion Finished:[/bold green] {res['filename']}")
            # Move processed input APK to processed archive
            archive_path = self.processed_dir / f"{time.strftime('%Y%m%d_%H%M%S')}_{apk_path.name}"
            shutil.move(str(apk_path), str(archive_path))
        except Exception as e:
            console.print(f"[bold red]❌ Conversion Error:[/bold red] {e}")
        finally:
            self.processing.discard(apk_path)

def start_dropzone_watcher(dropzone_dir: Optional[Path | str] = None, output_dir: Optional[Path | str] = None):
    drop_path = Path(dropzone_dir) if dropzone_dir else Path(os.environ.get("APK_DROPZONE_DIR", Path.home() / "APK_TV_Converter_Dropzone"))
    drop_path.mkdir(parents=True, exist_ok=True)
    (drop_path / "to_tv").mkdir(exist_ok=True)
    (drop_path / "to_mobile").mkdir(exist_ok=True)
    (drop_path / "universal").mkdir(exist_ok=True)

    out_path = Path(output_dir) if output_dir else Path(os.environ.get("APK_OUTPUT_DIR", Path.home() / "APK_TV_Converter_Output"))
    out_path.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold green]👁️ Dropzone Watcher Started[/bold green]")
    console.print(f"Watching directory: [cyan]{drop_path}[/cyan]")
    console.print("  • Drop in [bold]to_tv/[/bold] for Smartphone ➔ Android TV")
    console.print("  • Drop in [bold]to_mobile/[/bold] for Android TV ➔ Smartphone")
    console.print("  • Drop in [bold]universal/[/bold] for Dual-Mode Hybrid")
    console.print("\nPress Ctrl+C to stop.\n")

    event_handler = APKDropHandler(drop_path, out_path)
    observer = Observer()
    observer.schedule(event_handler, str(drop_path), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
