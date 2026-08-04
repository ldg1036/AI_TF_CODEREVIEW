"""
pywebview GUI 애플리케이션 진입점 (TRD §5.9 & Phase 8 기준).

WinCC OA 코드 리뷰 자동화 도구 데스크톱 윈도우 생성 및 런처.
"""

from __future__ import annotations

import logging
from pathlib import Path

import webview

from app.ui.api import JSApi

logger = logging.getLogger(__name__)


def launch_ui() -> None:
    """pywebview 윈도우를 생성하고 GUI 애플리케이션을 실행합니다."""
    api = JSApi()
    html_file = Path(__file__).parent / "index.html"

    if not html_file.exists():
        raise FileNotFoundError(f"UI HTML 파일을 찾을 수 없습니다: {html_file}")

    window = webview.create_window(
        title="WinCC OA Code Reviewer",
        url=str(html_file.resolve()),
        js_api=api,
        width=1280,
        height=840,
        min_size=(900, 600),
    )

    api.set_window(window)
    webview.start(debug=False)


if __name__ == "__main__":
    launch_ui()
