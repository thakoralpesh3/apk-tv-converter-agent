import unittest
from pathlib import Path

from core.cursor_builder import TVCursorBuilder, CURSOR_SRC_DIR, PRECOMPILED_DEX


class TestOttTvOsd(unittest.TestCase):

    def test_ott_tv_osd_source_and_dex(self):
        overlay_src_file = CURSOR_SRC_DIR / "com/tv/cursor/TvDesktopCursorOverlay.java"
        self.assertTrue(overlay_src_file.is_file(), "TvDesktopCursorOverlay.java must exist")

        src_text = overlay_src_file.read_text(encoding="utf-8")
        self.assertIn("class OttTvPlayerOsdView", src_text)
        self.assertIn("sOttTvOsdView", src_text)
        self.assertIn("togglePlayPause", src_text)
        self.assertIn("triggerSeek", src_text)
        self.assertIn("sLastFocusedViewRef", src_text)

        # Verify compiled DEX exists and is > 30KB
        self.assertTrue(PRECOMPILED_DEX.is_file(), "tv_cursor.dex must exist")
        self.assertGreater(PRECOMPILED_DEX.stat().st_size, 30000)

    def test_cursor_builder_recompile(self):
        dex_path = TVCursorBuilder.compile_dex(force=False)
        self.assertTrue(dex_path.is_file())
        self.assertGreater(dex_path.stat().st_size, 30000)
