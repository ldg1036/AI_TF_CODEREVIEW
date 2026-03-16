"""Shared imports and base fixtures for system verification tests."""

import glob
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

try:
    from .core.ctrl_wrapper import CtrlppWrapper
    from .core.heuristic_checker import HeuristicChecker
    from .core.llm_reviewer import LLMReviewer
    from .core.mcp_context import MCPContextClient
    from .core.pnl_parser import PnlParser
    from .core.reporter import Reporter
    from .core.xml_parser import XmlParser
    from .main import CodeInspectorApp, DEFAULT_MODE
except ImportError:
    from core.ctrl_wrapper import CtrlppWrapper
    from core.heuristic_checker import HeuristicChecker
    from core.llm_reviewer import LLMReviewer
    from core.mcp_context import MCPContextClient
    from core.pnl_parser import PnlParser
    from core.reporter import Reporter
    from core.xml_parser import XmlParser
    from main import CodeInspectorApp, DEFAULT_MODE


class SystemVerificationBase(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.base_dir)
        self.config_dir = os.path.join(self.project_root, "Config")
        self.data_dir = os.path.join(self.project_root, "CodeReview_Data")

    @staticmethod
    def _normalize_text(text):
        return text.replace("\r\n", "\n").replace("\r", "\n").strip()

    def _copy_sources_to_temp(self, extensions):
        temp_dir = tempfile.TemporaryDirectory()
        copied = []
        for name in sorted(os.listdir(self.data_dir)):
            lower = name.lower()
            if any(lower.endswith(ext) for ext in extensions):
                src = os.path.join(self.data_dir, name)
                dst = os.path.join(temp_dir.name, name)
                shutil.copy2(src, dst)
                copied.append(name)
        return temp_dir, copied

    @staticmethod
    def _extract_xml_script_texts(content):
        root = ET.fromstring(content)
        scripts = []
        for script in root.iter("script"):
            if script.text and script.text.strip():
                scripts.append(html.unescape(script.text).strip())
        return scripts


__all__ = [
    "CodeInspectorApp",
    "CtrlppWrapper",
    "DEFAULT_MODE",
    "ET",
    "HeuristicChecker",
    "LLMReviewer",
    "MCPContextClient",
    "PnlParser",
    "Reporter",
    "SystemVerificationBase",
    "XmlParser",
    "glob",
    "html",
    "json",
    "os",
    "shutil",
    "subprocess",
    "tempfile",
    "zipfile",
]
