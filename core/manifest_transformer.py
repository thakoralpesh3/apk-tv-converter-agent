"""
AndroidManifest.xml Transformer for Cross-Conversion
Handles intelligent modification of features, intent-filters, banners,
orientations, and hardware compatibility between Smartphone, Android TV, and Universal APKs.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional

ANDROID_NS = "http://schemas.android.com/apk/res/android"
ET.register_namespace("android", ANDROID_NS)

def _a(attr_name: str) -> str:
    """Format attribute with android namespace."""
    return f"{{{ANDROID_NS}}}{attr_name}"

class ManifestTransformer:
    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self.tree = ET.parse(manifest_path)
        self.root = self.tree.getroot()

    def get_package_name(self) -> str:
        return self.root.attrib.get("package", "com.unknown.app")

    def get_app_element(self) -> Optional[ET.Element]:
        return self.root.find("application")

    def get_main_activities(self) -> List[ET.Element]:
        """Find activities that handle android.intent.action.MAIN."""
        app = self.get_app_element()
        if app is None:
            return []
        
        main_activities = []
        for activity in app.findall("activity") + app.findall("activity-alias"):
            for ifilter in activity.findall("intent-filter"):
                for action in ifilter.findall("action"):
                    if action.attrib.get(_a("name")) == "android.intent.action.MAIN":
                        if activity not in main_activities:
                            main_activities.append(activity)
        return main_activities

    def inspect_current_mode(self) -> Dict[str, Any]:
        """Inspect whether the APK is currently TV, Smartphone, or Universal."""
        has_leanback_feature = False
        leanback_required = False
        touchscreen_optional = False

        for feat in self.root.findall("uses-feature"):
            name = feat.attrib.get(_a("name"))
            req = feat.attrib.get(_a("required"), "true").lower() == "true"
            if name == "android.software.leanback":
                has_leanback_feature = True
                leanback_required = req
            elif name == "android.hardware.touchscreen" and not req:
                touchscreen_optional = True

        has_tv_launcher = False
        has_mobile_launcher = False

        for act in self.get_main_activities():
            for ifilter in act.findall("intent-filter"):
                for cat in ifilter.findall("category"):
                    cname = cat.attrib.get(_a("name"))
                    if cname == "android.intent.category.LEANBACK_LAUNCHER":
                        has_tv_launcher = True
                    elif cname == "android.intent.category.LAUNCHER":
                        has_mobile_launcher = True

        app = self.get_app_element()
        has_banner = app is not None and _a("banner") in app.attrib

        if has_tv_launcher and has_mobile_launcher:
            detected = "universal"
        elif has_tv_launcher:
            detected = "android_tv"
        else:
            detected = "smartphone"

        return {
            "detected_mode": detected,
            "has_tv_launcher": has_tv_launcher,
            "has_mobile_launcher": has_mobile_launcher,
            "has_leanback_feature": has_leanback_feature,
            "leanback_required": leanback_required,
            "touchscreen_optional": touchscreen_optional,
            "has_banner": has_banner,
            "package": self.get_package_name()
        }

    def _ensure_uses_feature(self, name: str, required: bool):
        """Set or update a uses-feature declaration."""
        for feat in self.root.findall("uses-feature"):
            if feat.attrib.get(_a("name")) == name:
                feat.attrib[_a("required")] = "true" if required else "false"
                return
        
        # Add new feature right before <application>
        feat = ET.Element("uses-feature")
        feat.attrib[_a("name")] = name
        feat.attrib[_a("required")] = "true" if required else "false"
        app = self.get_app_element()
        if app is not None:
            idx = list(self.root).index(app)
            self.root.insert(idx, feat)
        else:
            self.root.append(feat)

    def _relax_mobile_hardware_features(self):
        """Relax hardware features that are not guaranteed on TV devices."""
        features_to_relax = [
            "android.hardware.touchscreen",
            "android.hardware.touchscreen.multitouch",
            "android.hardware.touchscreen.multitouch.distinct",
            "android.hardware.touchscreen.multitouch.jazzhand",
            "android.hardware.faketouch",
            "android.hardware.telephony",
            "android.hardware.camera",
            "android.hardware.camera.autofocus",
            "android.hardware.camera.front",
            "android.hardware.camera.any",
            "android.hardware.camera.flash",
            "android.hardware.camera.external",
            "android.hardware.microphone",
            "android.hardware.bluetooth",
            "android.hardware.wifi",
            "android.hardware.location",
            "android.hardware.location.gps",
            "android.hardware.location.network",
            "android.hardware.sensor.accelerometer",
            "android.hardware.sensor.compass",
            "android.hardware.sensor.gyroscope",
            "android.hardware.sensor.barometer",
            "android.hardware.sensor.light",
            "android.hardware.sensor.proximity",
            "android.hardware.sensor.stepcounter",
            "android.hardware.sensor.stepdetector",
            "android.hardware.fingerprint",
            "android.hardware.biometrics",
            "android.hardware.nfc"
        ]

        # 1. Update any existing uses-feature tags
        for feat in self.root.findall("uses-feature"):
            name = feat.attrib.get(_a("name"))
            if name:
                if name in features_to_relax or any(name.startswith(p) for p in ("android.hardware.camera", "android.hardware.sensor", "android.hardware.touchscreen")):
                    feat.attrib[_a("required")] = "false"

        # 2. Essential TV optional features MUST be explicitly declared optional
        # so TV package managers and Google Play do not filter out or reject installation.
        mandatory_tv_optional = [
            "android.hardware.touchscreen",
            "android.hardware.faketouch",
            "android.hardware.telephony",
            "android.hardware.camera",
            "android.hardware.camera.autofocus",
            "android.hardware.microphone",
            "android.hardware.location.gps",
            "android.hardware.wifi",
            "android.hardware.bluetooth",
            "android.hardware.screen.portrait",
            "android.hardware.screen.landscape"
        ]
        for name in mandatory_tv_optional:
            self._ensure_uses_feature(name, required=False)

    def transform_to_tv(
        self,
        banner_res: str = "@drawable/tv_banner",
        orientation: str = "landscape",
        pure_tv: bool = False
    ) -> Dict[str, Any]:
        """Transform APK manifest into an Android TV compatible manifest."""
        changes = []

        # 0. Supports Screens: enforce 16:9 wide screen scaling without pillarboxing/letterboxing
        supports_screens = self.root.find("supports-screens")
        if supports_screens is None:
            supports_screens = ET.Element("supports-screens")
            self.root.insert(0, supports_screens)
        supports_screens.attrib[_a("smallScreens")] = "true"
        supports_screens.attrib[_a("normalScreens")] = "true"
        supports_screens.attrib[_a("largeScreens")] = "true"
        supports_screens.attrib[_a("xlargeScreens")] = "true"
        supports_screens.attrib[_a("anyDensity")] = "true"
        supports_screens.attrib[_a("resizeable")] = "true"
        changes.append("Configured <supports-screens> for 16:9 widescreen big-screen display")

        # 1. Leanback feature declaration
        # For pure TV it's required=true, for broad compatibility required=false
        leanback_req = True if pure_tv else False
        self._ensure_uses_feature("android.software.leanback", required=leanback_req)
        changes.append(f"Set android.software.leanback required={leanback_req}")

        # 2. Relax touchscreen and other mobile hardware requirements
        self._relax_mobile_hardware_features()
        changes.append("Declared hardware features optional for Android TV")

        # 3. Leanback Banner, Resizeable Activity & Remote Focus Highlight on Application
        app = self.get_app_element()
        if app is not None:
            app.attrib[_a("banner")] = banner_res
            app.attrib[_a("defaultFocusHighlightEnabled")] = "true"
            app.attrib[_a("resizeableActivity")] = "true"
            app.attrib[_a("hardwareAccelerated")] = "true"
            changes.append(f"Configured application banner={banner_res}")
            changes.append("Enabled TV default focus highlight marker & resizeableActivity=true")

        # 4. Activities & Activity Aliases: transform orientation, configChanges, and remote focus across ALL activities
        all_activities = (app.findall("activity") + app.findall("activity-alias")) if app is not None else []
        main_activities = self.get_main_activities()
        if not main_activities and all_activities:
            main_activities = [all_activities[0]]

        # Ensure all activities adapt to landscape, remote focus marker, and handle TV configurations
        for act in all_activities:
            act_name = act.attrib.get(_a("name"), "activity")
            # Unconditionally enforce horizontal landscape orientation across EVERY activity for Android TV
            act.attrib[_a("screenOrientation")] = orientation
            act.attrib[_a("resizeableActivity")] = "true"
            changes.append(f"Enforced horizontal landscape orientation on activity '{act_name}' ({orientation})")

            act.attrib[_a("defaultFocusHighlightEnabled")] = "true"

            # Append configChanges for remote / keyboard / orientation handling
            configs = act.attrib.get(_a("configChanges"), "")
            needed = ["keyboard", "keyboardHidden", "navigation", "orientation", "screenSize", "screenLayout", "smallestScreenSize", "uiMode"]
            curr_tokens = [c.strip() for c in configs.split("|") if c.strip()]
            for item in needed:
                if item not in curr_tokens:
                    curr_tokens.append(item)
            act.attrib[_a("configChanges")] = "|".join(curr_tokens)

        # 5. Leanback Banner & Category on Main Activities
        for act in main_activities:
            act.attrib[_a("banner")] = banner_res

            main_filters = []
            for ifilter in act.findall("intent-filter"):
                for action in ifilter.findall("action"):
                    if action.attrib.get(_a("name")) == "android.intent.action.MAIN":
                        main_filters.append(ifilter)

            if not main_filters:
                new_filter = ET.SubElement(act, "intent-filter")
                ET.SubElement(new_filter, "action", {_a("name"): "android.intent.action.MAIN"})
                main_filters = [new_filter]

            for ifilter in main_filters:
                categories = {cat.attrib.get(_a("name")): cat for cat in ifilter.findall("category")}
                
                # Add LEANBACK_LAUNCHER if not present
                if "android.intent.category.LEANBACK_LAUNCHER" not in categories:
                    ET.SubElement(ifilter, "category", {_a("name"): "android.intent.category.LEANBACK_LAUNCHER"})
                    changes.append("Injected category LEANBACK_LAUNCHER")

                # If pure TV mode, remove phone LAUNCHER category
                if pure_tv and "android.intent.category.LAUNCHER" in categories:
                    ifilter.remove(categories["android.intent.category.LAUNCHER"])
                    changes.append("Removed phone LAUNCHER category (pure TV mode)")

        self.save()
        return {"status": "ok", "changes": changes}

    def transform_to_mobile(
        self,
        icon_res: str = "@mipmap/ic_launcher",
        orientation: str = "unspecified"
    ) -> Dict[str, Any]:
        """Transform Android TV APK manifest into a Smartphone / Tablet manifest."""
        changes = []

        # 1. Leanback must NOT be required
        for feat in self.root.findall("uses-feature"):
            if feat.attrib.get(_a("name")) == "android.software.leanback":
                feat.attrib[_a("required")] = "false"
                changes.append("Set android.software.leanback required=false")

        # 2. Touchscreen can be present or optional
        for feat in self.root.findall("uses-feature"):
            if feat.attrib.get(_a("name")) == "android.hardware.touchscreen":
                feat.attrib[_a("required")] = "false"

        # 3. Application icon
        app = self.get_app_element()
        if app is not None:
            if _a("icon") not in app.attrib:
                app.attrib[_a("icon")] = icon_res
                changes.append(f"Configured mobile icon={icon_res}")

        # 4. Activities: Unlock landscape orientation across the ENTIRE application
        all_activities = (app.findall("activity") + app.findall("activity-alias")) if app is not None else []
        main_activities = self.get_main_activities()
        if not main_activities and all_activities:
            main_activities = [all_activities[0]]

        for act in all_activities:
            act_name = act.attrib.get(_a("name"), "activity")
            current_ori = act.attrib.get(_a("screenOrientation"), "")
            if "landscape" in current_ori.lower():
                act.attrib[_a("screenOrientation")] = orientation
                changes.append(f"Unlocked activity '{act_name}' orientation to {orientation}")

        for act in main_activities:
            main_filters = []
            for ifilter in act.findall("intent-filter"):
                for action in ifilter.findall("action"):
                    if action.attrib.get(_a("name")) == "android.intent.action.MAIN":
                        main_filters.append(ifilter)

            if not main_filters:
                new_filter = ET.SubElement(act, "intent-filter")
                ET.SubElement(new_filter, "action", {_a("name"): "android.intent.action.MAIN"})
                main_filters = [new_filter]

            for ifilter in main_filters:
                categories = {cat.attrib.get(_a("name")): cat for cat in ifilter.findall("category")}
                
                # Add LAUNCHER if not present
                if "android.intent.category.LAUNCHER" not in categories:
                    ET.SubElement(ifilter, "category", {_a("name"): "android.intent.category.LAUNCHER"})
                    changes.append("Injected category LAUNCHER")

        self.save()
        return {"status": "ok", "changes": changes}

    def transform_to_universal(
        self,
        banner_res: str = "@drawable/tv_banner",
        icon_res: str = "@mipmap/ic_launcher"
    ) -> Dict[str, Any]:
        """Configure APK manifest for Universal compatibility across Mobile, Tablets, and Android TV."""
        changes = []

        # 1. Leanback optional
        self._ensure_uses_feature("android.software.leanback", required=False)
        changes.append("Set android.software.leanback required=false")

        # 2. Touchscreen optional
        self._relax_mobile_hardware_features()
        changes.append("Declared hardware features optional")

        # 3. Application banner, icon, and remote focus highlight
        app = self.get_app_element()
        if app is not None:
            app.attrib[_a("banner")] = banner_res
            app.attrib[_a("defaultFocusHighlightEnabled")] = "true"
            if _a("icon") not in app.attrib:
                app.attrib[_a("icon")] = icon_res
            changes.append(f"Set banner={banner_res} and icon")
            changes.append("Enabled TV default focus highlight marker (android:defaultFocusHighlightEnabled=true)")

        # 4. Activities: adapt orientation, remote focus, and configChanges across ALL activities
        all_activities = (app.findall("activity") + app.findall("activity-alias")) if app is not None else []
        main_activities = self.get_main_activities()
        if not main_activities and all_activities:
            main_activities = [all_activities[0]]

        for act in all_activities:
            act.attrib[_a("screenOrientation")] = "unspecified"
            act.attrib[_a("defaultFocusHighlightEnabled")] = "true"
            configs = act.attrib.get(_a("configChanges"), "")
            needed = ["keyboard", "keyboardHidden", "navigation", "orientation", "screenSize", "screenLayout", "smallestScreenSize"]
            curr_tokens = [c.strip() for c in configs.split("|") if c.strip()]
            for item in needed:
                if item not in curr_tokens:
                    curr_tokens.append(item)
            act.attrib[_a("configChanges")] = "|".join(curr_tokens)

        for act in main_activities:
            act.attrib[_a("banner")] = banner_res

            main_filters = []
            for ifilter in act.findall("intent-filter"):
                for action in ifilter.findall("action"):
                    if action.attrib.get(_a("name")) == "android.intent.action.MAIN":
                        main_filters.append(ifilter)

            if not main_filters:
                new_filter = ET.SubElement(act, "intent-filter")
                ET.SubElement(new_filter, "action", {_a("name"): "android.intent.action.MAIN"})
                main_filters = [new_filter]

            for ifilter in main_filters:
                cats = {cat.attrib.get(_a("name")): cat for cat in ifilter.findall("category")}
                if "android.intent.category.LAUNCHER" not in cats:
                    ET.SubElement(ifilter, "category", {_a("name"): "android.intent.category.LAUNCHER"})
                    changes.append("Injected category LAUNCHER")
                if "android.intent.category.LEANBACK_LAUNCHER" not in cats:
                    ET.SubElement(ifilter, "category", {_a("name"): "android.intent.category.LEANBACK_LAUNCHER"})
                    changes.append("Injected category LEANBACK_LAUNCHER")

        self.save()
        return {"status": "ok", "changes": changes}

    def inject_provider(
        self,
        name: str,
        authorities: str,
        exported: bool = False,
        init_order: int = 999999
    ) -> bool:
        """Inject or update a ContentProvider in <application>."""
        app = self.get_app_element()
        if app is None:
            return False

        for prov in app.findall("provider"):
            if prov.attrib.get(_a("name")) == name:
                return True

        provider_elem = ET.SubElement(app, "provider")
        provider_elem.attrib[_a("name")] = name
        provider_elem.attrib[_a("authorities")] = authorities
        provider_elem.attrib[_a("exported")] = "true" if exported else "false"
        provider_elem.attrib[_a("initOrder")] = str(init_order)
        self.save()
        return True

    def save(self):
        """Write modified XML back to AndroidManifest.xml."""
        self.tree.write(self.manifest_path, encoding="utf-8", xml_declaration=True)

