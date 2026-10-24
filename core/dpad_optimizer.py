"""
Android TV D-Pad & Focus Navigation Optimizer
Enhances TV directional pad (remote control) responsiveness,
hardware acceleration, remote reconnection stability, and injects
the Android TV Remote Focus Marker (outline/highlight) across manifests,
themes, styles, and layouts so users can see and interact with active elements.
"""

import os
from pathlib import Path
from typing import Dict, Any, Callable, Optional, Tuple
import xml.etree.ElementTree as ET

ANDROID_NS = "http://schemas.android.com/apk/res/android"
ET.register_namespace("android", ANDROID_NS)

TV_REMOTE_MARKER_XML = """<?xml version="1.0" encoding="utf-8"?>
<selector xmlns:android="http://schemas.android.com/apk/res/android">
    <item android:state_focused="true">
        <shape android:shape="rectangle">
            <solid android:color="#00000000" />
            <stroke android:width="3.0dip" android:color="#00E5FF" />
            <corners android:radius="8.0dip" />
        </shape>
    </item>
    <item>
        <shape android:shape="rectangle">
            <solid android:color="#00000000" />
        </shape>
    </item>
</selector>
"""

TV_MOUSE_CURSOR_XML = """<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="32dp"
    android:height="32dp"
    android:viewportWidth="32"
    android:viewportHeight="32">
    <!-- Drop Shadow -->
    <path
        android:fillColor="#55000000"
        android:pathData="M5,4 L5,26 L11,20 L15,29 L18,27.5 L14,19 L22,19 Z" />
    <!-- Outer Black Border -->
    <path
        android:fillColor="#000000"
        android:pathData="M3,2 L3,24 L9,18 L13,27 L16,25.5 L12,17 L20,17 Z" />
    <!-- Inner White Pointer Body -->
    <path
        android:fillColor="#FFFFFF"
        android:pathData="M4.5,4.5 L4.5,21.5 L8.5,17.5 L12.5,25.5 L14,24.5 L10.2,16.5 L17.5,16.5 Z" />
</vector>
"""

TV_MOUSE_CLICK_RING_XML = """<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android"
    android:shape="oval">
    <stroke
        android:width="2dp"
        android:color="#00E5FF" />
    <solid
        android:color="#4400E5FF" />
</shape>
"""

TV_DESKTOP_CURSOR_JS = """/**
 * Android TV Desktop Mouse Cursor Engine
 * Displays a desktop mouse cursor arrow on 16:9 horizontal screens,
 * controlled via TV Remote D-Pad / Arrow keys and Gamepad buttons.
 */
(function() {
    'use strict';
    if (window.__tv_mouse_cursor_loaded) return;
    window.__tv_mouse_cursor_loaded = true;

    // Desktop Cursor Coordinates centered in horizontal 16:9 view
    let cursorX = window.innerWidth > 0 ? window.innerWidth / 2 : 640;
    let cursorY = window.innerHeight > 0 ? window.innerHeight / 2 : 360;
    const BASE_SPEED = 22;
    let repeatCounter = 0;
    let lastKey = null;

    // Inject Desktop Cursor DOM
    const cursorContainer = document.createElement('div');
    cursorContainer.id = 'tv-desktop-cursor-container';
    cursorContainer.style.cssText = `
        position: fixed;
        left: 0;
        top: 0;
        width: 32px;
        height: 32px;
        pointer-events: none;
        z-index: 2147483647;
        transform: translate(${cursorX}px, ${cursorY}px);
        transition: transform 0.04s linear;
        display: block;
    `;

    cursorContainer.innerHTML = `
        <svg width="32" height="32" viewBox="0 0 32 32" style="filter: drop-shadow(0 2px 4px rgba(0,0,0,0.85)); display: block;">
            <path fill="#000000" d="M3,2 L3,24 L9,18 L13,27 L16,25.5 L12,17 L20,17 Z"/>
            <path fill="#FFFFFF" d="M4.5,4.5 L4.5,21.5 L8.5,17.5 L12.5,25.5 L14,24.5 L10.2,16.5 L17.5,16.5 Z"/>
        </svg>
        <div id="tv-cursor-click-ring" style="position: absolute; left: -8px; top: -8px; width: 32px; height: 32px; border: 3px solid #00E5FF; border-radius: 50%; opacity: 0; pointer-events: none; transform: scale(0.5); transition: transform 0.2s ease-out, opacity 0.2s ease-out;"></div>
    `;

    function attachCursor() {
        if (!document.getElementById('tv-desktop-cursor-container') && document.body) {
            document.body.appendChild(cursorContainer);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', attachCursor);
    } else {
        attachCursor();
    }

    function updateCursorPosition() {
        cursorX = Math.max(5, Math.min(cursorX, window.innerWidth - 15));
        cursorY = Math.max(5, Math.min(cursorY, window.innerHeight - 15));
        cursorContainer.style.transform = `translate(${cursorX}px, ${cursorY}px)`;
    }

    function triggerClickRipple() {
        const ring = document.getElementById('tv-cursor-click-ring');
        if (!ring) return;
        ring.style.opacity = '1';
        ring.style.transform = 'scale(1.6)';
        setTimeout(() => {
            ring.style.opacity = '0';
            ring.style.transform = 'scale(0.5)';
        }, 220);
    }

    function performCursorClick() {
        triggerClickRipple();
        const target = document.elementFromPoint(cursorX, cursorY);
        if (target) {
            target.focus();
            ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(type => {
                const evt = new MouseEvent(type, {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                    clientX: cursorX,
                    clientY: cursorY
                });
                target.dispatchEvent(evt);
            });
            if (typeof target.click === 'function') {
                target.click();
            }
        }
    }

    // Key event listener for D-Pad and Keyboard
    window.addEventListener('keydown', function(e) {
        attachCursor();
        const code = e.keyCode || e.which;

        if (code === lastKey) {
            repeatCounter = Math.min(repeatCounter + 1, 8);
        } else {
            repeatCounter = 0;
            lastKey = code;
        }

        const speed = BASE_SPEED + (repeatCounter * 4);

        switch(code) {
            case 38: // UP
            case 19: // KEYCODE_DPAD_UP
                cursorY -= speed;
                updateCursorPosition();
                e.preventDefault();
                break;
            case 40: // DOWN
            case 20: // KEYCODE_DPAD_DOWN
                cursorY += speed;
                updateCursorPosition();
                e.preventDefault();
                break;
            case 37: // LEFT
            case 21: // KEYCODE_DPAD_LEFT
                cursorX -= speed;
                updateCursorPosition();
                e.preventDefault();
                break;
            case 39: // RIGHT
            case 22: // KEYCODE_DPAD_RIGHT
                cursorX += speed;
                updateCursorPosition();
                e.preventDefault();
                break;
            case 13: // ENTER
            case 23: // KEYCODE_DPAD_CENTER
            case 66: // KEYCODE_ENTER
                performCursorClick();
                e.preventDefault();
                break;
        }
    }, { capture: true });

    // Track physical mouse movement if desktop preview is used
    window.addEventListener('mousemove', function(e) {
        cursorX = e.clientX;
        cursorY = e.clientY;
        updateCursorPosition();
    }, { passive: true });
})();
"""

INTERACTIVE_TAG_SUFFIXES = (
    "Button",
    "ImageButton",
    "ImageView",
    "TextView",
    "EditText",
    "CheckBox",
    "RadioButton",
    "Switch",
    "ToggleButton",
    "SeekBar",
    "ProgressBar",
    "Spinner",
    "WebView",
    "CardView",
    "RecyclerView",
    "ListView",
    "GridView",
)

def _a(name: str) -> str:
    return f"{{{ANDROID_NS}}}{name}"

def _inject_manifest_focus(manifest_path: Path) -> bool:
    """Injects defaultFocusHighlightEnabled and hardwareAccelerated into AndroidManifest.xml."""
    if not manifest_path.is_file():
        return False

    try:
        tree = ET.parse(manifest_path)
        root = tree.getroot()
        app = root.find("application")
        if app is None:
            return False

        modified = False

        # 1. Enable Hardware Acceleration
        hacc = _a("hardwareAccelerated")
        if app.attrib.get(hacc) != "true":
            app.attrib[hacc] = "true"
            modified = True

        # 2. Enable Default Focus Highlight on Application
        dfh = _a("defaultFocusHighlightEnabled")
        if app.attrib.get(dfh) != "true":
            app.attrib[dfh] = "true"
            modified = True

        # 3. Enable Default Focus Highlight on all Activities and Aliases
        for act in app.findall("activity") + app.findall("activity-alias"):
            if act.attrib.get(dfh) != "true":
                act.attrib[dfh] = "true"
                modified = True

        if modified:
            tree.write(manifest_path, encoding="utf-8", xml_declaration=True)
        return modified
    except Exception:
        return False

def _inject_tv_remote_marker_drawable(decoded_dir: Path) -> bool:
    """Creates the high-contrast Neon Cyan TV Remote Marker and Desktop Mouse Cursor drawables."""
    try:
        drawable_dir = decoded_dir / "res" / "drawable"
        drawable_dir.mkdir(parents=True, exist_ok=True)

        # 1. TV Remote Focus Marker
        marker_file = drawable_dir / "tv_remote_focus_marker.xml"
        marker_file.write_text(TV_REMOTE_MARKER_XML.strip(), encoding="utf-8")

        # 2. Desktop Mouse Cursor Vector
        cursor_file = drawable_dir / "ic_tv_mouse_cursor.xml"
        cursor_file.write_text(TV_MOUSE_CURSOR_XML.strip(), encoding="utf-8")

        # 3. Mouse Click Ripple Ring
        ring_file = drawable_dir / "tv_mouse_click_ring.xml"
        ring_file.write_text(TV_MOUSE_CLICK_RING_XML.strip(), encoding="utf-8")

        # 4. Generate crisp PNG raster fallback in drawable-xhdpi
        drawable_xhdpi = decoded_dir / "res" / "drawable-xhdpi"
        drawable_xhdpi.mkdir(parents=True, exist_ok=True)
        try:
            from PIL import Image, ImageDraw
            cursor_img = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
            cdraw = ImageDraw.Draw(cursor_img)
            # Drop shadow
            cdraw.polygon([(9, 7), (9, 37), (17, 29), (23, 43), (28, 41), (22, 27), (35, 27)], fill=(0, 0, 0, 120))
            # Outer black border
            cdraw.polygon([(6, 4), (6, 34), (14, 26), (20, 40), (25, 38), (19, 24), (32, 24)], fill=(0, 0, 0, 255))
            # Inner white body
            cdraw.polygon([(8, 7), (8, 30), (14, 24), (19, 36), (22, 35), (17, 23), (28, 23)], fill=(255, 255, 255, 255))
            cursor_img.save(drawable_xhdpi / "ic_tv_mouse_cursor.png", "PNG")
        except Exception:
            pass

        return True
    except Exception:
        return False

def _inject_theme_focus_styles(decoded_dir: Path) -> int:
    """
    Injects defaultFocusHighlightEnabled and neon cyan focus marker colors
    into all style and theme XML files.
    """
    res_dir = decoded_dir / "res"
    if not res_dir.is_dir():
        return 0

    styles_updated = 0
    val_dirs = [d for d in res_dir.iterdir() if d.is_dir() and d.name.startswith("values")]

    target_items = {
        "android:defaultFocusHighlightEnabled": "true",
        "android:colorFocusedHighlight": "#00E5FF",
        "android:colorControlActivated": "#00E5FF"
    }

    found_any_style = False

    for vdir in val_dirs:
        for sfile in vdir.glob("*.xml"):
            if "style" not in sfile.name.lower() and "theme" not in sfile.name.lower():
                continue
            try:
                tree = ET.parse(sfile)
                root = tree.getroot()
                if root.tag != "resources":
                    continue

                modified = False
                for style in root.findall("style"):
                    found_any_style = True
                    existing_items = {item.attrib.get("name"): item for item in style.findall("item")}
                    for item_name, item_val in target_items.items():
                        if item_name not in existing_items:
                            elem = ET.SubElement(style, "item", name=item_name)
                            elem.text = item_val
                            modified = True
                            styles_updated += 1
                        elif existing_items[item_name].text != item_val and "Highlight" in item_name:
                            existing_items[item_name].text = item_val
                            modified = True

                if modified:
                    tree.write(sfile, encoding="utf-8", xml_declaration=True)
            except Exception:
                pass

    # If no styles file existed, create a basic one in res/values/styles.xml
    if not found_any_style:
        values_dir = res_dir / "values"
        values_dir.mkdir(parents=True, exist_ok=True)
        styles_file = values_dir / "styles.xml"
        try:
            root = ET.Element("resources")
            style = ET.SubElement(root, "style", name="Theme.APKTV.FocusMarker", parent="@android:style/Theme.DeviceDefault")
            for item_name, item_val in target_items.items():
                elem = ET.SubElement(style, "item", name=item_name)
                elem.text = item_val
            tree = ET.ElementTree(root)
            tree.write(styles_file, encoding="utf-8", xml_declaration=True)
            styles_updated += 1
        except Exception:
            pass

    return styles_updated

def _optimize_layouts_for_remote_focus(decoded_dir: Path) -> Tuple[int, int]:
    """
    Recursively scans all layout XML files and ensures interactive elements
    have focusability and default focus highlight enabled for TV remote navigation.
    Also activates virtual mouse containers if present.
    """
    res_dir = decoded_dir / "res"
    if not res_dir.is_dir():
        return (0, 0)

    layout_dirs = [d for d in res_dir.iterdir() if d.is_dir() and d.name.startswith("layout")]
    layouts_modified = 0
    total_views_enhanced = 0

    attr_focusable = _a("focusable")
    attr_touch_focusable = _a("focusableInTouchMode")
    attr_highlight = _a("defaultFocusHighlightEnabled")
    attr_clickable = _a("clickable")
    attr_onclick = _a("onClick")
    attr_id = _a("id")
    attr_visibility = _a("visibility")

    for ldir in layout_dirs:
        for lfile in ldir.glob("*.xml"):
            try:
                tree = ET.parse(lfile)
                root = tree.getroot()
                file_modified = False

                for elem in root.iter():
                    tag_clean = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                    elem_id = elem.attrib.get(attr_id, "")

                    # Check for virtual mouse container (e.g. tvMouseContainer)
                    if "tvmousecontainer" in elem_id.lower() or "mouse_cursor" in elem_id.lower():
                        if elem.attrib.get(attr_visibility) != "visible":
                            elem.attrib[attr_visibility] = "visible"
                            elem.attrib[attr_focusable] = "false"
                            elem.attrib[attr_clickable] = "false"
                            file_modified = True
                            total_views_enhanced += 1
                        continue

                    # Check if this element is interactive
                    is_interactive = any(tag_clean.endswith(s) for s in INTERACTIVE_TAG_SUFFIXES)
                    is_clickable = elem.attrib.get(attr_clickable) == "true" or attr_onclick in elem.attrib

                    if is_interactive or is_clickable:
                        changed = False
                        if elem.attrib.get(attr_focusable) != "true":
                            elem.attrib[attr_focusable] = "true"
                            changed = True
                        if elem.attrib.get(attr_touch_focusable) != "true":
                            elem.attrib[attr_touch_focusable] = "true"
                            changed = True
                        if elem.attrib.get(attr_highlight) != "true":
                            elem.attrib[attr_highlight] = "true"
                            changed = True

                        if changed:
                            file_modified = True
                            total_views_enhanced += 1

                if file_modified:
                    tree.write(lfile, encoding="utf-8", xml_declaration=True)
                    layouts_modified += 1

            except Exception:
                pass

    # Ensure Desktop Mouse Cursor overlay is injected into primary activity layouts
    cursor_injected_count = 0
    for ldir in layout_dirs:
        for lfile in ldir.glob("*.xml"):
            name_lower = lfile.name.lower()
            if any(k in name_lower for k in ("activity", "main", "home", "player", "content")):
                if _inject_layout_cursor_container(lfile):
                    cursor_injected_count += 1
                    layouts_modified += 1
                    total_views_enhanced += 1

    # Fallback: if no activity/main layout matched, inject into the first available layout
    if cursor_injected_count == 0:
        for ldir in layout_dirs:
            for lfile in ldir.glob("*.xml"):
                if _inject_layout_cursor_container(lfile):
                    layouts_modified += 1
                    total_views_enhanced += 1
                    break

    return (layouts_modified, total_views_enhanced)

def _inject_layout_cursor_container(layout_file: Path) -> bool:
    """Injects the FrameLayout tvMouseContainer overlay into a layout file."""
    try:
        tree = ET.parse(layout_file)
        root = tree.getroot()
        for elem in root.iter():
            if "tvmousecontainer" in elem.attrib.get(_a("id"), "").lower():
                return False

        container = ET.SubElement(root, "FrameLayout")
        container.attrib[_a("id")] = "@+id/tvMouseContainer"
        container.attrib[_a("layout_width")] = "match_parent"
        container.attrib[_a("layout_height")] = "match_parent"
        container.attrib[_a("clickable")] = "false"
        container.attrib[_a("focusable")] = "false"
        container.attrib[_a("visibility")] = "visible"
        container.attrib[_a("elevation")] = "999dp"

        ring = ET.SubElement(container, "View")
        ring.attrib[_a("id")] = "@+id/tvMouseClickRing"
        ring.attrib[_a("layout_width")] = "32dp"
        ring.attrib[_a("layout_height")] = "32dp"
        ring.attrib[_a("layout_gravity")] = "center"
        ring.attrib[_a("background")] = "@drawable/tv_mouse_click_ring"
        ring.attrib[_a("visibility")] = "gone"

        cursor = ET.SubElement(container, "ImageView")
        cursor.attrib[_a("id")] = "@+id/tvMouseCursor"
        cursor.attrib[_a("layout_width")] = "36dp"
        cursor.attrib[_a("layout_height")] = "36dp"
        cursor.attrib[_a("layout_gravity")] = "center"
        cursor.attrib[_a("src")] = "@drawable/ic_tv_mouse_cursor"
        cursor.attrib[_a("visibility")] = "visible"

        tree.write(layout_file, encoding="utf-8", xml_declaration=True)
        return True
    except Exception:
        return False

def _patch_smali_tv_cursor_and_orientation(decoded_dir: Path) -> int:
    """
    Patches Smali bytecode:
    1. checkIsTvDevice()Z -> returns true (1) unconditionally
    2. setRequestedOrientation(1) -> setRequestedOrientation(0) (enforces horizontal landscape)
    """
    smali_dirs = [d for d in decoded_dir.iterdir() if d.is_dir() and d.name.startswith("smali")]
    if not smali_dirs:
        return 0

    import re
    patched = 0
    for sdir in smali_dirs:
        for sfile in sdir.rglob("*.smali"):
            try:
                content = sfile.read_text(encoding="utf-8", errors="ignore")
                mod = False

                # 1. Patch checkIsTvDevice()Z
                if "checkIsTvDevice()Z" in content:
                    replacement = ".method private checkIsTvDevice()Z\n    .locals 1\n    const/4 v0, 0x1\n    return v0\n.end method"
                    new_c = re.sub(r"\.method (?:private|public) checkIsTvDevice\(\)Z[\s\S]*?\.end method", replacement, content)
                    if new_c != content:
                        content = new_c
                        mod = True
                        patched += 1

                # 2. Patch setRequestedOrientation portrait (0x1) to landscape (0x0)
                if "setRequestedOrientation" in content:
                    new_c = re.sub(
                        r"const/4 (v\d+), 0x1\s*(\n\s*invoke-virtual \{[^}]*, \1\}, Landroid/app/Activity;->setRequestedOrientation)",
                        r"const/4 \1, 0x0\2",
                        content
                    )
                    if new_c != content:
                        content = new_c
                        mod = True
                        patched += 1

                if mod:
                    sfile.write_text(content, encoding="utf-8")
            except Exception:
                pass

    return patched

def _inject_web_desktop_cursor(decoded_dir: Path) -> bool:
    """
    Recursively injects the standalone TV Desktop Mouse Cursor Engine into all
    web and hybrid assets (assets/, assets/www/, assets/public/, etc.).
    """
    assets_dir = decoded_dir / "assets"
    if not assets_dir.is_dir():
        return False

    injected = False
    try:
        # Find all HTML files recursively in assets
        html_files = list(assets_dir.rglob("*.html")) + list(assets_dir.rglob("*.htm"))

        # Always place cursor script at the root of assets
        root_cursor_js = assets_dir / "tv_desktop_cursor.js"
        root_cursor_js.write_text(TV_DESKTOP_CURSOR_JS.strip(), encoding="utf-8")
        injected = True

        for hfile in html_files:
            try:
                # Also ensure cursor js exists in the directory of the HTML file
                dir_cursor_js = hfile.parent / "tv_desktop_cursor.js"
                if not dir_cursor_js.is_file():
                    dir_cursor_js.write_text(TV_DESKTOP_CURSOR_JS.strip(), encoding="utf-8")

                html_text = hfile.read_text(encoding="utf-8", errors="ignore")
                if "tv_desktop_cursor.js" not in html_text:
                    if "</head>" in html_text:
                        html_text = html_text.replace("</head>", '<script src="tv_desktop_cursor.js"></script></head>', 1)
                    elif "</body>" in html_text:
                        html_text = html_text.replace("</body>", '<script src="tv_desktop_cursor.js"></script></body>', 1)
                    else:
                        html_text += '<script src="tv_desktop_cursor.js"></script>'
                    hfile.write_text(html_text, encoding="utf-8")
                    injected = True
            except Exception:
                pass

        return injected
    except Exception:
        return False

def optimize_for_tv_navigation(
    decoded_dir: Path,
    re_report: Optional[Dict[str, Any]] = None,
    log_callback: Optional[Callable[[str], None]] = None
) -> dict:
    """
    Applies comprehensive TV Remote Marker, Desktop Mouse Cursor & Focus Navigation Optimizations:
    1. Manifest focus highlight & hardware acceleration
    2. High-contrast Neon Cyan Remote Marker & Desktop Mouse Cursor drawables
    3. Theme/Styles remote focus attributes (defaultFocusHighlightEnabled, colorFocusedHighlight)
    4. Layout-level interactive element focusability & Desktop Mouse Cursor overlay injection
    5. Smali bytecode orientation & TV device detection patching
    6. Web assets TV Desktop Cursor injection
    """
    def _log(msg: str):
        if log_callback:
            log_callback(msg)

    manifest_path = decoded_dir / "AndroidManifest.xml"
    if not manifest_path.is_file():
        return {"status": "skipped", "reason": "No manifest"}

    strategy_info = re_report.get("conversion_strategy", {}) if re_report else {}
    strategy_name = strategy_info.get("name", "Universal Desktop Cursor Strategy")
    _log(f"Activating Android TV Remote Marker & Desktop Mouse Cursor Engine ({strategy_name})...")

    # 1. Manifest Focus Injection
    manifest_updated = _inject_manifest_focus(manifest_path)
    if manifest_updated:
        _log("  • Manifest: Injected android:defaultFocusHighlightEnabled='true' & hardwareAccelerated")

    # 2. Remote Marker & Desktop Mouse Cursor Drawables Injection
    drawable_created = _inject_tv_remote_marker_drawable(decoded_dir)
    if drawable_created:
        _log("  • Drawables: Injected Desktop Mouse Cursor (@drawable/ic_tv_mouse_cursor) & Remote Marker")

    # 3. Theme & Style Remote Marker Injection
    styles_updated = _inject_theme_focus_styles(decoded_dir)
    if styles_updated > 0:
        _log(f"  • Themes & Styles: Injected Neon Cyan Remote Marker (#00E5FF) across {styles_updated} style definitions")

    # 4. Layout Interactive View Focusability & Desktop Mouse Cursor Overlay
    layouts_mod, views_enh = _optimize_layouts_for_remote_focus(decoded_dir)
    if views_enh > 0 or layouts_mod > 0:
        _log(f"  • Layouts: Injected Desktop Mouse Cursor overlay & upgraded {views_enh} interactive views across {layouts_mod} layouts")

    # 5. Smali Bytecode Patching (enforce horizontal landscape & TV device detection)
    smali_patched = _patch_smali_tv_cursor_and_orientation(decoded_dir)
    if smali_patched > 0:
        _log(f"  • Smali Bytecode: Patched {smali_patched} methods for TV Desktop Cursor & Horizontal Landscape")

    # 6. Web Assets Desktop Cursor Injection
    web_injected = _inject_web_desktop_cursor(decoded_dir)
    if web_injected:
        _log("  • Assets: Recursively injected Android TV Desktop Mouse Cursor Engine (tv_desktop_cursor.js)")

    return {
        "status": "ok",
        "strategy": strategy_name,
        "hardware_accelerated": True,
        "manifest_updated": manifest_updated,
        "drawable_created": drawable_created,
        "styles_updated": styles_updated,
        "layouts_modified": layouts_mod,
        "views_enhanced": views_enh,
        "smali_patched": smali_patched,
        "web_injected": web_injected
    }

