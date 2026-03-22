import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from core.input_normalization import InputNormalizer


class InputNormalizationTests(unittest.TestCase):
    def test_canonical_name_resolution_for_aliases(self):
        self.assertEqual(InputNormalizer.canonical_name_for("panel.pnl"), "panel_pnl.txt")
        self.assertEqual(InputNormalizer.canonical_name_for("layout.xml"), "layout_xml.txt")
        self.assertEqual(InputNormalizer.canonical_name_for("sample_REVIEWED.txt"), "sample.txt")
        self.assertEqual(InputNormalizer.reviewed_name_for("panel.pnl"), "panel_pnl_REVIEWED.txt")

    def test_candidate_names_include_aliases(self):
        candidates = InputNormalizer.candidate_names_for("panel.pnl")
        self.assertIn("panel.pnl", candidates)
        self.assertIn("panel_pnl.txt", candidates)
        self.assertIn("panel_pnl_REVIEWED.txt", candidates)

    def test_read_text_file_detects_utf8_sig_cp949_and_euc_kr(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            utf8_sig_path = os.path.join(tmp_dir, "utf8_sig.txt")
            cp949_path = os.path.join(tmp_dir, "cp949.txt")
            euc_kr_path = os.path.join(tmp_dir, "euc_kr.txt")
            with open(utf8_sig_path, "w", encoding="utf-8-sig") as handle:
                handle.write("hello")
            with open(cp949_path, "w", encoding="cp949") as handle:
                handle.write("한글")
            with open(euc_kr_path, "w", encoding="euc-kr") as handle:
                handle.write("경계")

            utf8_text, utf8_encoding = InputNormalizer.read_text_file(utf8_sig_path)
            cp949_text, cp949_encoding = InputNormalizer.read_text_file(cp949_path)
            euc_kr_text, euc_kr_encoding = InputNormalizer.read_text_file(euc_kr_path)

            self.assertEqual(utf8_text, "hello")
            self.assertEqual(utf8_encoding, "utf-8-sig")
            self.assertEqual(cp949_text, "한글")
            self.assertEqual(cp949_encoding, "cp949")
            self.assertEqual(euc_kr_text, "경계")
            self.assertEqual(euc_kr_encoding, "cp949")


if __name__ == "__main__":
    unittest.main()
