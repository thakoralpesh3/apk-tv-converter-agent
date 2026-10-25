"""
Web Dashboard Server for APK TV & Smartphone Cross-Converter AI Agent.
Powered by FastAPI, WebSockets, HTML5 & Gemini 4 Argon AI Content Engine.
"""

import os
import shutil
import socket
import io
import base64
import json
import zipfile
import mimetypes
import subprocess
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi.staticfiles import StaticFiles
from fastapi.requests import Request
import qrcode
import uvicorn

from core.converter import APKCrossConverter, DEFAULT_OUTPUT_DIR
from core.apk_engine import APKEngine
from core.ai_content_engine import GeminiAIContentEngine
from core.manifest_transformer import ManifestTransformer

TEMPLATES_DIR = BASE_DIR / "web" / "templates"
STATIC_DIR = BASE_DIR / "web" / "static"

app = FastAPI(title="APK Cross-Converter AI Studio")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

converter = APKCrossConverter()
engine = APKEngine()

def get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def generate_qr_base64(url: str) -> str:
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def get_apk_path(filename: str) -> Optional[Path]:
    p = converter.output_dir / filename
    if p.is_file():
        return p
    search_dirs = [
        BASE_DIR / "samples",
        Path.home() / "Downloads",
        Path(os.environ.get("APK_DROPZONE_DIR", Path.home() / "APK_TV_Converter_Dropzone")),
        Path.home() / "Web2APK_Output"
    ]
    for d in search_dirs:
        alt = d / filename
        if alt.is_file():
            return alt
    return None

def extract_preview_data(apk_path: Path) -> dict:
    stem = apk_path.stem
    base_stem = stem.replace("-converted-tv", "").replace("-converted-mobile", "").replace("-converted-universal", "").replace("-smartphone", "").replace("-android-tv", "")
    
    with zipfile.ZipFile(apk_path, "r") as z:
        namelist = z.namelist()
        has_banner = any("tv_banner.png" in n.lower() or ("banner" in n.lower() and n.endswith(".png")) for n in namelist)
        has_icon = any("ic_launcher" in n.lower() and n.endswith(".png") for n in namelist)
        has_index_html = any(n == "assets/index.html" or (n.startswith("assets/") and n.endswith("index.html")) for n in namelist)

    audit_file = converter.output_dir / f"{base_stem}-AI-TV-Audit.json"
    audit_data = {}
    if audit_file.is_file():
        try:
            with open(audit_file, "r") as f:
                audit_data = json.load(f)
        except Exception:
            pass

    # Reverse engineering report
    re_file = converter.output_dir / f"{base_stem}-reverse-engineering-report.json"
    re_data = {}
    if re_file.is_file():
        try:
            with open(re_file, "r") as f:
                re_data = json.load(f)
        except Exception:
            pass
    if not re_data:
        try:
            re_data = converter.re_analyzer.analyze(apk_path)
        except Exception:
            re_data = {"framework": "Native Android", "obfuscation_level": "LOW"}

    target_mode = "tv" if "tv" in apk_path.name.lower() else ("mobile" if "mobile" in apk_path.name.lower() else "universal")
    tagline = audit_data.get("summary", "Certified Android TV Edition with Active Remote Marker")
    score = audit_data.get("readiness_score", 95)
    grade = audit_data.get("grade", "A+")

    return {
        "filename": apk_path.name,
        "app_label": base_stem.replace("_", " ").title(),
        "stem": stem,
        "target_mode": target_mode,
        "size_mb": round(apk_path.stat().st_size / (1024 * 1024), 2),
        "has_banner": has_banner,
        "has_icon": has_icon,
        "has_index_html": has_index_html,
        "banner_url": f"/api/preview/banner/{apk_path.name}",
        "icon_url": f"/api/preview/icon/{apk_path.name}",
        "webview_url": f"/api/preview/asset/{apk_path.name}/assets/index.html" if has_index_html else None,
        "tagline": tagline,
        "score": score,
        "grade": grade,
        "remote_marker_active": True,
        "desktop_cursor_active": True,
        "orientation": "landscape",
        "framework": re_data.get("framework", "Native Android"),
        "obfuscation": re_data.get("obfuscation_level", "LOW"),
        "strategy": re_data.get("conversion_strategy", {}).get("name", "Desktop Cursor Navigation"),
        "re_report": re_data
    }

def list_converted_apks() -> List[dict]:
    out_dir = converter.output_dir
    lan_ip = get_lan_ip()
    port = 8877
    items = []
    for p in sorted(out_dir.glob("*.apk"), key=lambda f: f.stat().st_mtime, reverse=True):
        dl_url = f"http://{lan_ip}:{port}/download/{p.name}"
        stem = p.stem
        base_stem = stem.replace("-converted-tv", "").replace("-converted-mobile", "").replace("-converted-universal", "").replace("-smartphone", "").replace("-android-tv", "")
        listing_file = out_dir / f"{base_stem}-AI-Store-Listing.md"
        audit_file = out_dir / f"{base_stem}-AI-TV-Audit.json"
        re_file = out_dir / f"{base_stem}-reverse-engineering-report.json"
        is_tv_mode = "tv" in p.name.lower() or "universal" in p.name.lower()

        framework = "Native Android"
        obf = "LOW"
        if re_file.is_file():
            try:
                with open(re_file, "r") as f:
                    r = json.load(f)
                    framework = r.get("framework", framework)
                    obf = r.get("obfuscation_level", obf)
            except Exception:
                pass

        items.append({
            "filename": p.name,
            "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
            "mtime": p.stat().st_mtime,
            "download_url": dl_url,
            "qr_code": generate_qr_base64(dl_url),
            "has_ai_listing": listing_file.is_file(),
            "has_ai_audit": audit_file.is_file(),
            "has_re_report": re_file.is_file(),
            "framework": framework,
            "obfuscation": obf,
            "is_tv_compatible": is_tv_mode,
            "preview_url": f"/preview/{p.name}"
        })
    return items

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    tools = engine.check_tools()
    apks = list_converted_apks()
    lan_ip = get_lan_ip()
    ai_available = GeminiAIContentEngine.is_available()
    ai_model = GeminiAIContentEngine.get_preferred_model()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "tools": tools,
            "apks": apks,
            "lan_ip": lan_ip,
            "port": 8877,
            "ai_available": ai_available,
            "ai_model": ai_model
        }
    )

@app.get("/api/status")
async def get_status():
    return {
        "tools": engine.check_tools(),
        "lan_ip": get_lan_ip(),
        "output_count": len(list(converter.output_dir.glob("*.apk"))),
        "output_dir": str(converter.output_dir),
        "dropzone_dir": str(Path(os.environ.get("APK_DROPZONE_DIR", Path.home() / "APK_TV_Converter_Dropzone"))),
        "ai_model": GeminiAIContentEngine.get_preferred_model(),
        "ai_online": GeminiAIContentEngine.is_available()
    }

@app.get("/download/{filename}")
async def download_apk(filename: str):
    apk_file = converter.output_dir / filename
    if not apk_file.is_file():
        return JSONResponse(status_code=404, content={"error": "File not found"})
    return FileResponse(
        str(apk_file),
        media_type="application/vnd.android.package-archive",
        filename=filename
    )

@app.get("/download-doc/{filename}")
async def download_doc(filename: str):
    doc_file = converter.output_dir / filename
    if not doc_file.is_file():
        return JSONResponse(status_code=404, content={"error": "Document not found"})
    return FileResponse(str(doc_file), filename=filename)

@app.get("/api/preview/data/{filename}")
async def api_preview_data(filename: str):
    p = get_apk_path(filename)
    if not p:
        return JSONResponse(status_code=404, content={"error": f"APK not found: {filename}"})
    try:
        return extract_preview_data(p)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/preview/re-analysis/{filename}")
async def api_preview_re_analysis(filename: str):
    p = get_apk_path(filename)
    if not p:
        return JSONResponse(status_code=404, content={"error": f"APK not found: {filename}"})
    base_stem = p.stem.replace("-converted-tv", "").replace("-converted-mobile", "").replace("-converted-universal", "").replace("-smartphone", "").replace("-android-tv", "")
    re_file = converter.output_dir / f"{base_stem}-reverse-engineering-report.json"
    if re_file.is_file():
        try:
            with open(re_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    try:
        report = converter.re_analyzer.analyze(p)
        return report
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/fingerprint/{filename}")
@app.get("/api/fingerprint")
async def api_fingerprint(filename: Optional[str] = None):
    if not filename:
        return JSONResponse(status_code=400, content={"error": "filename parameter is required"})
    p = get_apk_path(filename)
    if not p:
        return JSONResponse(status_code=404, content={"error": f"APK not found: {filename}"})
    try:
        return converter.re_analyzer.analyze(p)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/github/status")
async def api_github_status():
    try:
        def _git(args):
            r = subprocess.run(["git"] + args, cwd=str(BASE_DIR), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return r.returncode, r.stdout.strip()

        rc, branch = _git(["branch", "--show-current"])
        rc, commit = _git(["log", "-1", "--format=%h|%s|%an|%cr"])
        rc, dirty = _git(["status", "--porcelain"])
        rc, remote = _git(["remote", "get-url", "origin"])

        parts = commit.split("|") if commit else ["", "", "", ""]
        return {
            "branch": branch or "main",
            "commit_hash": parts[0] if len(parts) > 0 else "",
            "commit_msg": parts[1] if len(parts) > 1 else "",
            "commit_author": parts[2] if len(parts) > 2 else "",
            "commit_time": parts[3] if len(parts) > 3 else "",
            "is_dirty": bool(dirty),
            "uncommitted_files": len(dirty.splitlines()) if dirty else 0,
            "remote_url": remote or "https://github.com/thakoralpesh3/apk-tv-converter-agent"
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/github/sync")
async def api_github_sync(request: Request):
    try:
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        custom_msg = body.get("message") if isinstance(body, dict) else None
        sync_script = BASE_DIR / "sync_to_github.sh"
        cmd = [str(sync_script)] + ([custom_msg] if custom_msg else [])
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
        return {
            "success": res.returncode == 0,
            "output": res.stdout
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/preview/banner/{filename}")
async def api_preview_banner(filename: str):
    p = get_apk_path(filename)
    if not p:
        return FileResponse(str(BASE_DIR / "assets" / "default_banner.png"), media_type="image/png")
    try:
        with zipfile.ZipFile(p, "r") as z:
            candidates = [n for n in z.namelist() if "tv_banner.png" in n.lower()]
            if not candidates:
                candidates = [n for n in z.namelist() if "banner" in n.lower() and n.endswith(".png")]
            if candidates:
                best = sorted(candidates, key=lambda c: 0 if "drawable/tv_banner" in c else 1)[0]
                data = z.read(best)
                return Response(content=data, media_type="image/png")
    except Exception:
        pass
    return FileResponse(str(BASE_DIR / "assets" / "default_banner.png"), media_type="image/png")

@app.get("/api/preview/icon/{filename}")
async def api_preview_icon(filename: str):
    p = get_apk_path(filename)
    if not p:
        return FileResponse(str(BASE_DIR / "assets" / "app-icon.png"), media_type="image/png")
    try:
        with zipfile.ZipFile(p, "r") as z:
            candidates = [n for n in z.namelist() if "ic_launcher" in n.lower() and n.endswith(".png")]
            if candidates:
                best = sorted(candidates, key=lambda c: 0 if "xxhdpi" in c else 1)[0]
                data = z.read(best)
                return Response(content=data, media_type="image/png")
    except Exception:
        pass
    return FileResponse(str(BASE_DIR / "assets" / "app-icon.png"), media_type="image/png")

@app.get("/api/preview/asset/{filename}/{asset_path:path}")
async def api_preview_asset(filename: str, asset_path: str):
    p = get_apk_path(filename)
    if not p:
        return JSONResponse(status_code=404, content={"error": "APK not found"})
    try:
        with zipfile.ZipFile(p, "r") as z:
            path_candidates = [asset_path, f"assets/{asset_path}", asset_path.lstrip("/")]
            for cand in path_candidates:
                if cand in z.namelist():
                    data = z.read(cand)
                    mime, _ = mimetypes.guess_type(cand)
                    mime = mime or "application/octet-stream"
                    return Response(content=data, media_type=mime)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    return JSONResponse(status_code=404, content={"error": f"Asset not found: {asset_path}"})

@app.get("/preview/{filename}", response_class=HTMLResponse)
async def get_preview_page(request: Request, filename: str):
    tools = engine.check_tools()
    apks = list_converted_apks()
    lan_ip = get_lan_ip()
    ai_available = GeminiAIContentEngine.is_available()
    ai_model = GeminiAIContentEngine.get_preferred_model()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "tools": tools,
            "apks": apks,
            "lan_ip": lan_ip,
            "port": 8877,
            "ai_available": ai_available,
            "ai_model": ai_model,
            "auto_preview_apk": filename
        }
    )

@app.post("/api/convert")
async def convert_api(
    apk_file: UploadFile = File(...),
    target_mode: str = Form("tv"),
    custom_banner: Optional[UploadFile] = File(None),
    orientation: Optional[str] = Form(None),
    enable_ai: bool = Form(True)
):
    upload_temp_dir = Path("/tmp/apk_converter_uploads")
    upload_temp_dir.mkdir(parents=True, exist_ok=True)
    temp_apk = upload_temp_dir / apk_file.filename

    with open(temp_apk, "wb") as f:
        shutil.copyfileobj(apk_file.file, f)

    banner_path = None
    if custom_banner and custom_banner.filename:
        banner_path = upload_temp_dir / custom_banner.filename
        with open(banner_path, "wb") as f:
            shutil.copyfileobj(custom_banner.file, f)

    try:
        result = converter.convert(
            input_apk=temp_apk,
            target_mode=target_mode,
            custom_banner_path=banner_path,
            orientation=orientation,
            ai_content=enable_ai
        )
        lan_ip = get_lan_ip()
        dl_url = f"http://{lan_ip}:8877/download/{result['filename']}"
        result["download_url"] = dl_url
        result["qr_code"] = generate_qr_base64(dl_url)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if temp_apk.exists():
            temp_apk.unlink(missing_ok=True)
        if banner_path and banner_path.exists():
            banner_path.unlink(missing_ok=True)

@app.post("/api/ai/audit")
async def ai_audit(app_name: str = Form(...), package_name: str = Form("com.app")):
    info = {"has_tv_launcher": False, "touchscreen_optional": False, "has_banner": False}
    result = GeminiAIContentEngine.audit_apk_for_tv(info, package_name)
    return result

@app.post("/api/ai/copy")
async def ai_store_copy(app_name: str = Form(...), package_name: str = Form("com.app"), target_mode: str = Form("tv")):
    result = GeminiAIContentEngine.generate_store_copy(app_name, package_name, target_mode)
    return result

@app.post("/api/ai/set-model")
async def set_model(model_name: str = Form(...)):
    success = GeminiAIContentEngine.set_preferred_model(model_name)
    return {"status": "ok" if success else "error", "model": GeminiAIContentEngine.get_preferred_model()}

@app.websocket("/ws/convert")
async def websocket_convert(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        input_path = data.get("input_path")
        target_mode = data.get("target_mode", "tv")
        orientation = data.get("orientation")
        enable_ai = data.get("enable_ai", True)

        async def send_log(msg: str):
            await websocket.send_json({"type": "log", "message": msg})

        import asyncio
        loop = asyncio.get_event_loop()

        def sync_log(msg: str):
            asyncio.run_coroutine_threadsafe(send_log(msg), loop)

        res = await loop.run_in_executor(
            None,
            lambda: converter.convert(
                input_apk=input_path,
                target_mode=target_mode,
                orientation=orientation,
                ai_content=enable_ai,
                log_callback=sync_log
            )
        )
        lan_ip = get_lan_ip()
        dl_url = f"http://{lan_ip}:8877/download/{res['filename']}"
        res["download_url"] = dl_url
        res["qr_code"] = generate_qr_base64(dl_url)

        await websocket.send_json({"type": "complete", "result": res})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})

@app.post("/api/open-folder")
async def open_output_folder():
    import subprocess
    subprocess.Popen(["xdg-open", str(converter.output_dir)])
    return {"status": "ok"}

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False

def open_browser_when_ready(url: str, check_port: int):
    import time
    import webbrowser
    for _ in range(50):
        time.sleep(0.2)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                if s.connect_ex(("127.0.0.1", check_port)) == 0:
                    time.sleep(0.3)
                    webbrowser.open(url)
                    break
        except Exception:
            pass

def start_server(host: str = "0.0.0.0", port: int = 8877):
    # If server is already running, open in browser and exit cleanly
    if is_port_in_use(port):
        import webbrowser
        print(f"\n⚡ APK Cross-Converter Studio is already running on http://localhost:{port}!")
        print("🌐 Opening Studio dashboard in your browser...\n")
        webbrowser.open(f"http://localhost:{port}")
        return

    import threading
    t = threading.Thread(target=open_browser_when_ready, args=(f"http://localhost:{port}", port), daemon=True)
    t.start()

    print(f"\n🚀 Launching APK Cross-Converter Web Studio on http://{host}:{port}")
    lan_ip = get_lan_ip()
    model = GeminiAIContentEngine.get_preferred_model()
    print(f"✨ Gemini AI Engine: {model.upper()} (Active)")
    print(f"📡 Local LAN Network URL: http://{lan_ip}:{port}")
    print(f"🌐 Opening dashboard in browser: http://localhost:{port}\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")

if __name__ == "__main__":
    start_server()
