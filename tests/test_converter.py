"""
Test suite for APK Cross-Converter AI Agent.
"""

import sys
import pytest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.apk_engine import APKEngine
from core.converter import APKCrossConverter

def test_toolchain_ready():
    engine = APKEngine()
    status = engine.check_tools()
    assert status["java"] is True, "Java OpenJDK 17 must be available"
    assert status["apktool"] is True, "Apktool 2.9.3 must be available"
    assert status["signer"] is True, "Uber-APK-Signer must be available"
    assert status["all_ready"] is True

def test_smartphone_to_tv_conversion(tmp_path):
    sample_apk = Path("/home/alpesh/Web2APK_Output/API_Target_App-v1.0.0-smartphone.apk")
    if not sample_apk.is_file():
        pytest.skip("Sample smartphone APK not found")

    converter = APKCrossConverter(output_dir=tmp_path)
    result = converter.convert(
        input_apk=sample_apk,
        target_mode="tv"
    )

    assert result["status"] == "success"
    assert result["target_mode"] == "tv"
    out_apk = Path(result["output_apk"])
    assert out_apk.is_file()
    assert out_apk.stat().st_size > 0

    # Verify manifest of generated APK
    engine = APKEngine()
    decoded = tmp_path / "decoded_check"
    engine.decode(out_apk, decoded)
    manifest_text = (decoded / "AndroidManifest.xml").read_text()
    assert "android.intent.category.LEANBACK_LAUNCHER" in manifest_text
    assert "android.software.leanback" in manifest_text
    assert "android.hardware.touchscreen" in manifest_text
    assert "tv_banner" in manifest_text
    assert "defaultFocusHighlightEnabled" in manifest_text

def test_tv_to_smartphone_conversion(tmp_path):
    sample_apk = Path("/home/alpesh/Web2APK_Output/Cyber_Arcade_Hardened-v1.0.0-android-tv.apk")
    if not sample_apk.is_file():
        pytest.skip("Sample TV APK not found")

    converter = APKCrossConverter(output_dir=tmp_path)
    result = converter.convert(
        input_apk=sample_apk,
        target_mode="mobile"
    )

    assert result["status"] == "success"
    assert result["target_mode"] == "mobile"
    out_apk = Path(result["output_apk"])
    assert out_apk.is_file()
    assert out_apk.stat().st_size > 0

    engine = APKEngine()
    decoded = tmp_path / "decoded_check_mobile"
    engine.decode(out_apk, decoded)
    manifest_text = (decoded / "AndroidManifest.xml").read_text()
    assert "android.intent.category.LAUNCHER" in manifest_text

def test_universal_conversion(tmp_path):
    sample_apk = Path("/home/alpesh/Web2APK_Output/API_Target_App-v1.0.0-smartphone.apk")
    if not sample_apk.is_file():
        pytest.skip("Sample APK not found")

    converter = APKCrossConverter(output_dir=tmp_path)
    result = converter.convert(
        input_apk=sample_apk,
        target_mode="universal"
    )

    assert result["status"] == "success"
    assert result["target_mode"] == "universal"
    out_apk = Path(result["output_apk"])
    assert out_apk.is_file()
    assert out_apk.stat().st_size > 0

    engine = APKEngine()
    decoded = tmp_path / "decoded_check_univ"
    engine.decode(out_apk, decoded)
    manifest_text = (decoded / "AndroidManifest.xml").read_text()
    assert "android.intent.category.LAUNCHER" in manifest_text
    assert "android.intent.category.LEANBACK_LAUNCHER" in manifest_text

def test_gemini_ai_content_engine():
    from core.ai_content_engine import GeminiAIContentEngine
    assert GeminiAIContentEngine.get_preferred_model() == "gemini-4-argon"
    
    # Test banner content synthesis
    banner = GeminiAIContentEngine.generate_tv_banner_content("Action Game", "com.game.action", "smartphone")
    assert "tagline" in banner
    assert "color_theme" in banner
    
    # Test TV compatibility audit
    audit = GeminiAIContentEngine.audit_apk_for_tv({"has_tv_launcher": False}, "com.game.action")
    assert "readiness_score" in audit
    assert "grade" in audit
    
    # Test store listing copywriter
    copy = GeminiAIContentEngine.generate_store_copy("Action Game", "com.game.action", "tv")
    assert "title" in copy
    assert "short_description" in copy

def test_multi_activity_orientation_and_hardware_relaxation(tmp_path):
    from core.manifest_transformer import ManifestTransformer, _a
    manifest_file = tmp_path / "AndroidManifest.xml"
    manifest_xml = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.multi.test">
    <uses-feature android:name="android.hardware.camera" android:required="true" />
    <uses-feature android:name="android.hardware.telephony" android:required="true" />
    <application android:label="MultiTest">
        <activity android:name=".SplashActivity">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        <activity android:name=".HomeActivity" android:screenOrientation="portrait" />
        <activity android:name=".DetailActivity" android:screenOrientation="sensorPortrait" />
        <activity android:name=".PlayerActivity" android:screenOrientation="landscape" />
    </application>
</manifest>"""
    manifest_file.write_text(manifest_xml)

    # Transform to TV
    transformer = ManifestTransformer(manifest_file)
    res = transformer.transform_to_tv()
    assert res["status"] == "ok"

    app = transformer.get_app_element()
    activities = app.findall("activity")
    assert len(activities) == 4

    # Verify ALL activities are landscape on TV (none portrait)
    for act in activities:
        ori = act.attrib.get(_a("screenOrientation"))
        assert "portrait" not in ori.lower(), f"Activity {act.attrib.get(_a('name'))} still has portrait orientation"
        assert "landscape" in ori.lower(), f"Activity {act.attrib.get(_a('name'))} is not landscape-compatible"
        configs = act.attrib.get(_a("configChanges"), "")
        assert "keyboard" in configs
        assert "navigation" in configs

    # Verify TV features are relaxed
    features = {f.attrib.get(_a("name")): f.attrib.get(_a("required")) for f in transformer.root.findall("uses-feature")}
    assert features.get("android.hardware.camera") == "false"
    assert features.get("android.hardware.telephony") == "false"
    assert features.get("android.hardware.touchscreen") == "false"
    assert features.get("android.software.leanback") == "false"

def test_remote_focus_marker_engine(tmp_path):
    from core.dpad_optimizer import optimize_for_tv_navigation, ANDROID_NS
    import xml.etree.ElementTree as ET

    # Setup mock decoded app
    manifest_file = tmp_path / "AndroidManifest.xml"
    manifest_file.write_text("""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.marker.test">
    <application android:label="MarkerTest">
        <activity android:name=".MainActivity" />
    </application>
</manifest>""", encoding="utf-8")

    res_dir = tmp_path / "res"
    val_dir = res_dir / "values"
    val_dir.mkdir(parents=True)
    (val_dir / "styles.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="AppTheme" parent="@android:style/Theme.NoTitleBar">
        <item name="android:windowBackground">@android:color/black</item>
    </style>
</resources>""", encoding="utf-8")

    layout_dir = res_dir / "layout"
    layout_dir.mkdir(parents=True)
    (layout_dir / "activity_main.xml").write_text("""<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" android:layout_width="match_parent" android:layout_height="match_parent">
    <Button android:id="@+id/btn_play" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="Play" />
    <ImageView android:id="@+id/banner_thumb" android:layout_width="wrap_content" android:layout_height="wrap_content" android:clickable="true" />
    <FrameLayout android:id="@+id/tvMouseContainer" android:visibility="gone" android:layout_width="48dp" android:layout_height="48dp" />
</LinearLayout>""", encoding="utf-8")

    res = optimize_for_tv_navigation(tmp_path)
    assert res["status"] == "ok"
    assert res["manifest_updated"] is True
    assert res["drawable_created"] is True
    assert res["styles_updated"] > 0
    assert res["views_enhanced"] >= 3

    # 1. Verify Manifest
    m_tree = ET.parse(manifest_file)
    m_root = m_tree.getroot()
    m_app = m_root.find("application")
    assert m_app.attrib.get(f"{{{ANDROID_NS}}}defaultFocusHighlightEnabled") == "true"
    m_act = m_app.find("activity")
    assert m_act.attrib.get(f"{{{ANDROID_NS}}}defaultFocusHighlightEnabled") == "true"

    # 2. Verify Styles
    s_tree = ET.parse(val_dir / "styles.xml")
    s_items = {i.attrib.get("name"): i.text for i in s_tree.getroot().find("style").findall("item")}
    assert s_items.get("android:defaultFocusHighlightEnabled") == "true"
    assert s_items.get("android:colorFocusedHighlight") == "#00E5FF"

    # 3. Verify Drawable
    marker_drawable = res_dir / "drawable" / "tv_remote_focus_marker.xml"
    assert marker_drawable.is_file()
    assert "#00E5FF" in marker_drawable.read_text()

    # 4. Verify Layout
    l_tree = ET.parse(layout_dir / "activity_main.xml")
    btn = l_tree.getroot().find("Button")
    assert btn.attrib.get(f"{{{ANDROID_NS}}}focusable") == "true"
    assert btn.attrib.get(f"{{{ANDROID_NS}}}focusableInTouchMode") == "true"
    assert btn.attrib.get(f"{{{ANDROID_NS}}}defaultFocusHighlightEnabled") == "true"

    img = l_tree.getroot().find("ImageView")
    assert img.attrib.get(f"{{{ANDROID_NS}}}focusable") == "true"

    mouse_container = l_tree.getroot().find("FrameLayout")
    assert mouse_container.attrib.get(f"{{{ANDROID_NS}}}visibility") == "visible"

    # 5. Verify Desktop Mouse Cursor Drawables
    cursor_drawable = res_dir / "drawable" / "ic_tv_mouse_cursor.xml"
    assert cursor_drawable.is_file()
    ring_drawable = res_dir / "drawable" / "tv_mouse_click_ring.xml"
    assert ring_drawable.is_file()

def test_desktop_cursor_and_smali_orientation_patching(tmp_path):
    from core.dpad_optimizer import _patch_smali_tv_cursor_and_orientation, _inject_web_desktop_cursor

    # 1. Test Smali patching
    smali_dir = tmp_path / "smali" / "com" / "example"
    smali_dir.mkdir(parents=True)
    test_smali = smali_dir / "MainActivity.smali"
    test_smali.write_text("""
.method private checkIsTvDevice()Z
    .locals 5
    const/4 v0, 0x0
    return v0
.end method

.method protected onCreate(Landroid/os/Bundle;)V
    .locals 2
    const/4 v0, 0x1
    invoke-virtual {p0, v0}, Landroid/app/Activity;->setRequestedOrientation(I)V
    return-void
.end method
""", encoding="utf-8")

    patched = _patch_smali_tv_cursor_and_orientation(tmp_path)
    assert patched >= 2

    patched_content = test_smali.read_text(encoding="utf-8")
    assert "const/4 v0, 0x1" in patched_content  # in checkIsTvDevice
    assert "const/4 v0, 0x0" in patched_content  # in setRequestedOrientation (0=landscape)

    # 2. Test Web Desktop Cursor injection
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    index_html = assets_dir / "index.html"
    index_html.write_text("<!DOCTYPE html><html><head><title>App</title></head><body><h1>TV</h1></body></html>", encoding="utf-8")

    web_injected = _inject_web_desktop_cursor(tmp_path)
    assert web_injected is True
    assert (assets_dir / "tv_desktop_cursor.js").is_file()
    assert "tv_desktop_cursor.js" in index_html.read_text(encoding="utf-8")


def test_preview_asset_extraction():
    from web.server import app, extract_preview_data, get_apk_path
    from fastapi.testclient import TestClient

    sample_apk = get_apk_path("Openworld4All-converted-tv.apk")
    if not sample_apk:
        sample_apk = Path("/home/alpesh/APK_TV_Converter_Output/Openworld4All-converted-tv.apk")
    if not sample_apk.is_file():
        pytest.skip("Converted TV APK for preview test not found")

    # 1. Direct function extraction test
    data = extract_preview_data(sample_apk)
    assert data["filename"] == sample_apk.name
    assert "Openworld4all" in data["app_label"] or "Openworld" in data["app_label"]
    assert data["target_mode"] == "tv"
    assert data["has_banner"] is True
    assert data["has_icon"] is True
    assert data["remote_marker_active"] is True
    assert data["desktop_cursor_active"] is True
    assert data["orientation"] == "landscape"
    assert data["banner_url"].startswith("/api/preview/banner/")

    # 2. TestClient HTTP Endpoints test
    client = TestClient(app)

    # Preview metadata API
    res_data = client.get(f"/api/preview/data/{sample_apk.name}")
    assert res_data.status_code == 200
    p_json = res_data.json()
    assert p_json["has_banner"] is True
    assert p_json["remote_marker_active"] is True
    assert p_json["desktop_cursor_active"] is True
    assert p_json["orientation"] == "landscape"

    # TV Banner streaming API
    res_banner = client.get(f"/api/preview/banner/{sample_apk.name}")
    assert res_banner.status_code == 200
    assert res_banner.headers["content-type"] == "image/png"
    assert len(res_banner.content) > 100

    # TV Icon streaming API
    res_icon = client.get(f"/api/preview/icon/{sample_apk.name}")
    assert res_icon.status_code == 200
    assert res_icon.headers["content-type"] == "image/png"
    assert len(res_icon.content) > 100

    # TV Preview HTML page preloaded
    res_html = client.get(f"/preview/{sample_apk.name}")
    assert res_html.status_code == 200
    assert sample_apk.name in res_html.text
    assert "tvPreviewModal" in res_html.text
    assert "active-focus-marker" in res_html.text

    # Re-analysis API test
    res_re = client.get(f"/api/preview/re-analysis/{sample_apk.name}")
    assert res_re.status_code == 200
    re_json = res_re.json()
    assert "framework" in re_json
    assert "obfuscation_level" in re_json


def test_reverse_engineering_analyzer(tmp_path):
    from core.re_analyzer import ReverseEngineeringAnalyzer
    analyzer = ReverseEngineeringAnalyzer()

    sample_apk = PROJECT_ROOT / "samples" / "sample-smartphone.apk"
    if not sample_apk.is_file():
        pytest.skip("sample-smartphone.apk not found")

    report = analyzer.analyze(sample_apk)
    assert "framework" in report
    assert "obfuscation_level" in report
    assert "conversion_strategy" in report
    assert report["conversion_strategy"]["enforce_landscape"] is True

    # Test saving report
    out_json = tmp_path / "test-re-report.json"
    analyzer.save_report(report, out_json)
    assert out_json.is_file()
    assert out_json.stat().st_size > 0


def test_widescreen_horizontal_manifest_tags(tmp_path):
    from core.manifest_transformer import ManifestTransformer, _a
    manifest_file = tmp_path / "AndroidManifest.xml"
    manifest_xml = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.widescreen.test">
    <application android:label="WideTest">
        <activity android:name=".MainActivity" />
    </application>
</manifest>"""
    manifest_file.write_text(manifest_xml)

    transformer = ManifestTransformer(manifest_file)
    res = transformer.transform_to_tv()
    assert res["status"] == "ok"

    # Verify <supports-screens> is present with 16:9 big-screen sizing
    supports = transformer.root.find("supports-screens")
    assert supports is not None
    assert supports.attrib.get(_a("largeScreens")) == "true"
    assert supports.attrib.get(_a("xlargeScreens")) == "true"
    assert supports.attrib.get(_a("resizeable")) == "true"

    # Verify resizeableActivity on application and activity
    app = transformer.get_app_element()
    assert app.attrib.get(_a("resizeableActivity")) == "true"
    act = app.find("activity")
    assert act.attrib.get(_a("resizeableActivity")) == "true"
    assert act.attrib.get(_a("screenOrientation")) == "landscape"


def test_layout_desktop_cursor_injection_on_bare_layout(tmp_path):
    from core.dpad_optimizer import _optimize_layouts_for_remote_focus, ANDROID_NS
    import xml.etree.ElementTree as ET

    layout_dir = tmp_path / "res" / "layout"
    layout_dir.mkdir(parents=True)
    bare_layout = layout_dir / "activity_home.xml"
    bare_layout.write_text("""<?xml version="1.0" encoding="utf-8"?>
<RelativeLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent">
    <TextView android:id="@+id/txt_title" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="Home" />
</RelativeLayout>""", encoding="utf-8")

    layouts_mod, views_enh = _optimize_layouts_for_remote_focus(tmp_path)
    assert layouts_mod >= 1

    # Verify tvMouseContainer was automatically injected
    tree = ET.parse(bare_layout)
    root = tree.getroot()
    has_mouse = False
    for el in root.iter():
        if "tvmousecontainer" in el.attrib.get(f"{{{ANDROID_NS}}}id", "").lower():
            has_mouse = True
            break
    assert has_mouse is True, "tvMouseContainer must be injected into activity_home.xml"



