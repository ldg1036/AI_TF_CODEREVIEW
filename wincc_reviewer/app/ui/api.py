"""
pywebview JavaScript-Python 브리지 API (TRD §5.9 & Phase 8 기준).

JS 프론트엔드에서 호출할 수 있는 백엔드 인터페이스:
- select_input_path: 파일/폴더 선택 시스템 다이얼로그
- run_review: 파이프라인 백그라운드 실행 및 리뷰 결과 반환
"""

from __future__ import annotations

import difflib
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.core.pipeline import Pipeline, PipelineConfig
from app.core.report.html_report_builder import HTMLReportBuilder
from app.core.report.report_builder import ReportBuilder
from app.utils.encoding import read_text_with_fallback

logger = logging.getLogger(__name__)


class JSApi:
    """JS-Python 바인딩 브리지 API."""

    def __init__(self) -> None:
        self._window = None
        self._custom_settings_path: Path | None = None
        self.output_dir: Path = Path("output")

    def set_window(self, window: Any) -> None:

        """webview 윈도우 인스턴스를 설정합니다."""
        self._window = window

    def select_input_path(self, dialog_type: str = "folder") -> dict[str, Any]:
        """
        시스템 파일/폴더 선택 다이얼로그를 호출합니다.

        Args:
            dialog_type: "folder" 또는 "file"

        Returns:
            {"selected_path": str | None}
        """
        try:
            if self._window is not None:

                import webview

                file_types = ("WinCC OA Files (*.ctl;*.pnl;*.xml)", "All Files (*.*)")
                dialog_kind = (
                    webview.FOLDER_DIALOG
                    if dialog_type == "folder"
                    else webview.OPEN_DIALOG
                )

                res = self._window.create_file_dialog(
                    dialog_kind,
                    file_types=(file_types if dialog_type != "folder" else ()),
                )
                if res and len(res) > 0:
                    return {"selected_path": res[0]}
                return {"selected_path": None}

            # Fallback to tkinter if window is not attached (e.g. testing)
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)

            if dialog_type == "folder":
                path = filedialog.askdirectory(title="검사 대상 디렉터리 선택")
            else:
                path = filedialog.askopenfilename(
                    title="검사 대상 파일 선택",
                    filetypes=[("WinCC OA Files", "*.ctl *.pnl *.xml"), ("All Files", "*.*")],
                )
            root.destroy()

            return {"selected_path": path if path else None}

        except Exception as e:
            logger.error("파일 선택 창 실패: %s", e)
            return {"selected_path": None, "error": str(e)}

    def run_review(self, input_path: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        파이프라인을 실행하고 리뷰 리포트 및 HTML 렌더링 결과를 반환합니다.

        Args:
            input_path: 검사 대상 파일 또는 디렉터리 경로
            options: 추가 실행 옵션 (no_ai, output_dir 등)

        Returns:
            {"success": True, "report": dict, "html_content": str}
        """
        if not input_path:
            return {"success": False, "error": "검사 대상 경로가 지정되지 않았습니다."}

        path = Path(input_path)
        if not path.exists():
            return {"success": False, "error": f"존재하지 않는 경로입니다: {input_path}"}

        opts = options or {}
        output_dir = Path(opts.get("output_dir", "./output"))
        no_ai = opts.get("no_ai", True)
        extract_scripts_only = opts.get("extract_scripts_only", True)

        try:
            # 1. 먼저 정적 분석만 수행하기 위해 강제로 no_ai=True로 설정
            config = PipelineConfig(
                input_path=path,
                output_dir=output_dir,
                no_ai=True,
                extract_scripts_only=extract_scripts_only,
            )

            pipeline = Pipeline(config)
            report = pipeline.run()

            report_dict = ReportBuilder.to_dict(report)
            html_content = HTMLReportBuilder.render_html(report)

            self._last_report = report

            # 2. 사용자가 AI 분석을 요청했다면 백그라운드 스레드에서 AI 처리 진행
            if not no_ai:
                import threading
                threading.Thread(target=self._run_ai_background, args=(path, output_dir, extract_scripts_only), daemon=True).start()

            return {
                "success": True,
                "report": report_dict,
                "html_content": html_content,
                "ai_pending": not no_ai,
            }

        except (FileNotFoundError, PermissionError, ValueError, RuntimeError) as e:
            logger.error("UI 파이프라인 실행 중 알려진 오류 발생 (%s): %s", type(e).__name__, e, exc_info=True)
            return {"success": False, "error": f"[{type(e).__name__}] {e}"}
        except Exception as e:
            logger.error("UI 파이프라인 실행 중 예상치 못한 오류 발생: %s", e, exc_info=True)
            return {"success": False, "error": f"시스템 오류가 발생했습니다: {e}"}

    def _run_ai_background(self, path: Path, output_dir: Path, extract_scripts_only: bool = True) -> None:
        """백그라운드 스레드에서 AI 분석을 실행하고 UI에 알립니다."""
        import json
        try:
            logger.info("백그라운드 AI 심층 리뷰를 시작합니다: %s", path)
            config = PipelineConfig(
                input_path=path,
                output_dir=output_dir,
                no_ai=False,
                extract_scripts_only=extract_scripts_only,
            )
            pipeline = Pipeline(config)
            # 캐시가 존재하므로 정적 파싱은 즉시 통과하고, AI 리뷰 블록이 실행됨
            report = pipeline.run()

            report_dict = ReportBuilder.to_dict(report)
            html_content = HTMLReportBuilder.render_html(report)

            self._last_report = report

            if self._window:
                res = {
                    "success": True,
                    "report": report_dict,
                    "html_content": html_content,
                }
                self._window.evaluate_js(f"if(window.onAiReviewComplete) {{ window.onAiReviewComplete({json.dumps(res)}); }}")
        except Exception as e:
            logger.error("백그라운드 AI 실행 중 오류 발생: %s", e, exc_info=True)
            if self._window:
                res = {"success": False, "error": str(e)}
                self._window.evaluate_js(f"if(window.onAiReviewComplete) {{ window.onAiReviewComplete({json.dumps(res)}); }}")

    def export_report(self, format_type: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        원하는 확장자 형식(json, html, csv)으로 선택 리포트를 파일 저장합니다.

        Args:
            format_type: "json", "html", 또는 "csv"
            options: 추가 저장 옵션

        Returns:
            {"success": True, "saved_path": str}
        """
        if not hasattr(self, "_last_report") or self._last_report is None:
            return {"success": False, "error": "내보낼 수 있는 리뷰 결과가 없습니다. 먼저 정적 리뷰를 실행하세요."}

        report = self._last_report
        fmt = format_type.lower()
        default_filename = f"{report.run_id}_review_report.{fmt}"

        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)

            file_types = [("Report File", f"*.{fmt}"), ("All Files", "*.*")]
            save_path = filedialog.asksaveasfilename(
                title=f"리포트 내보내기 ({fmt.upper()})",
                initialfile=default_filename,
                filetypes=file_types,
            )
            root.destroy()

            if not save_path:
                return {"success": False, "error": "저장이 취소되었습니다."}

            out_path = Path(save_path)

            if fmt == "json":
                ReportBuilder.export_json(report, out_path)
            elif fmt == "html":
                HTMLReportBuilder.export_html(report, out_path)
            elif fmt == "csv":
                from app.core.report.csv_report_builder import CSVReportBuilder
                CSVReportBuilder.export_csv(report, out_path)
            elif fmt in ("excel", "xlsx"):
                from app.core.report.excel_report_builder import ExcelReportBuilder
                ExcelReportBuilder.export_excel(report, out_path)
            elif fmt == "pdf":
                from app.core.report.pdf_report_builder import PDFReportBuilder
                PDFReportBuilder.export_pdf(report, out_path)
            else:
                return {"success": False, "error": f"지원하지 않는 포맷 형식입니다: {format_type}"}

            return {"success": True, "saved_path": str(out_path)}

        except (FileNotFoundError, PermissionError, ValueError, OSError) as e:
            logger.error("리포트 내보내기 중 I/O 또는 형식 오류 발생 (%s): %s", type(e).__name__, e, exc_info=True)
            return {"success": False, "error": f"내보내기 실패: {e}"}
        except Exception as e:
            logger.error("리포트 Export 중 예상치 못한 오류 발생: %s", e, exc_info=True)
            return {"success": False, "error": str(e)}

    def get_file_content(self, file_path: str, extract_scripts_only: bool = True) -> dict[str, Any]:
        """
        요청된 파일의 소스 코드 텍스트를 읽어서 반환합니다. (extract_scripts_only 적용 시 PNL/XML 정제 스크립트 반환)

        Args:
            file_path: 파일 경로
            extract_scripts_only: 스크립트만 정제하여 읽을지 여부

        Returns:
            {"success": True, "content": str, "file_path": str}
        """
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "error": f"파일을 찾을 수 없습니다: {file_path}"}

        try:
            if extract_scripts_only and path.suffix.lower() in (".pnl", ".xml"):
                from app.core.input_normalization.service import NormalizationService
                parsed = NormalizationService.normalize_and_parse(path, extract_scripts_only=True)
                if parsed and parsed.content:
                    return {"success": True, "content": parsed.content, "file_path": str(path)}

            # 원본 다국어 인코딩 읽기
            content = read_text_with_fallback(path)

            return {"success": True, "content": content, "file_path": str(path)}
        except (FileNotFoundError, UnicodeDecodeError, PermissionError, OSError) as e:
            logger.error("파일 내용 읽기 실패 (%s): %s", type(e).__name__, e)
            return {"success": False, "error": f"파일 읽기 오류 ({type(e).__name__}): {e}"}
        except Exception as e:
            logger.error("파일 내용 읽기 중 예상치 못한 오류 발생: %s", e, exc_info=True)
            return {"success": False, "error": str(e)}

    def _resolve_settings_path(self, custom_path: str | None = None) -> Path:
        """설정 파일 경로를 탐색하여 반환합니다."""
        if custom_path and str(custom_path).strip():
            target = Path(str(custom_path).strip())
            self._custom_settings_path = target
            return target
        if self._custom_settings_path is not None:
            return self._custom_settings_path
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        config_path = base_dir / "config" / "settings.yaml"
        if not config_path.exists():
            config_path = Path.cwd() / "config" / "settings.yaml"
        return config_path

    def get_settings(self, custom_path: str | None = None) -> dict[str, Any]:
        """
        config 디렉토리 내 settings yaml 설정 파일을 읽어 딕셔너리로 반환합니다.

        Args:
            custom_path: 선택적인 커스텀 설정 파일 경로

        Returns:
            {"success": True, "settings": dict, "config_path": str}
        """
        try:
            import yaml

            cfg_path = self._resolve_settings_path(custom_path)
            if not cfg_path.exists():
                return {"success": True, "settings": {}, "config_path": str(cfg_path)}

            with open(cfg_path, "r", encoding="utf_8_sig") as f:
                data = yaml.safe_load(f) or {}

            import os
            env_key = os.environ.get("WINCC_AI_API_KEY") or os.environ.get("LOCAL_AI_API_KEY")
            if env_key and "ai" in data and "local_server" in data["ai"]:
                data["ai"]["local_server"]["api_key"] = env_key

            return {"success": True, "settings": data, "config_path": str(cfg_path)}
        except Exception as e:
            logger.error("설정 파일 로딩 실패: %s", e)
            return {"success": False, "error": str(e)}

    def update_settings(self, new_settings: dict[str, Any], custom_path: str | None = None) -> dict[str, Any]:
        """
        UI에서 수신한 새 설정 데이터로 지정된 settings yaml 파일을 갱신합니다.

        Args:
            new_settings: 변경할 설정 딕셔너리
            custom_path: 선택적인 커스텀 저장 경로

        Returns:
            {"success": True, "settings": dict, "message": str}
        """
        try:
            import yaml

            if not isinstance(new_settings, dict) or not new_settings:
                return {"success": False, "error": "유효하지 않은 설정 데이터입니다."}

            cfg_path = self._resolve_settings_path(custom_path)
            if not cfg_path.parent.exists():
                cfg_path.parent.mkdir(parents=True, exist_ok=True)

            with open(cfg_path, "w", encoding="utf_8_sig") as f:
                yaml.dump(new_settings, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

            logger.info("UI를 통한 설정 갱신 완료: path=%s", cfg_path)
            return {
                "success": True,
                "settings": new_settings,
                "message": "설정이 성공적으로 변경 및 저장되었습니다.",
                "config_path": str(cfg_path),
            }
        except Exception as e:
            logger.error("설정 파일 저장 실패: %s", e)
            return {"success": False, "error": str(e)}

    def list_ai_models(self, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        선택된 AI 제공자 또는 로컬 AI 서버에 연결하여 사용 가능한 모델 리스트를 조회합니다.

        Args:
            options: {"provider": str, "host": str, "port": int, "api_key": str}

        Returns:
            {"success": bool, "models": list[str], "error": str | None}
        """
        opts = options or {}
        provider = str(opts.get("provider", "local")).lower()

        if provider == "mock":
            return {
                "success": True,
                "models": ["mock_gemini_3_6_pro", "mock_local_llm"],
            }

        if provider == "gemini":
            return {
                "success": True,
                "models": ["gemini_3_6_pro", "gemini_2_5_pro", "gemini_1_5_pro"],
            }

        host = str(opts.get("host", "127.0.0.1")).strip()
        port = int(opts.get("port", 8000))
        api_key = str(opts.get("api_key", "")).strip()

        url = f"http://{host}:{port}/v1/models"
        default_local_models = ["sane_local_llm", "llama3", "qwen2_5_coder", "mistral"]

        try:
            import json
            import urllib.request

            req = urllib.request.Request(url, method="GET")
            if api_key:
                req.add_header("Authorization", f"Bearer {api_key}")

            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf_8"))

            models = []
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                for item in data["data"]:
                    if isinstance(item, dict) and "id" in item:
                        models.append(str(item["id"]))
                    elif isinstance(item, str):
                        models.append(item)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "id" in item:
                        models.append(str(item["id"]))
                    elif isinstance(item, str):
                        models.append(item)

            if not models:
                models = default_local_models

            return {"success": True, "is_online": True, "models": models}
        except Exception as e:
            logger.info("로컬 AI 서버가 연결되지 않아 오프라인 기본 모델 목록을 사용합니다: %s", e)
            return {
                "success": False,
                "is_online": False,
                "error": f"로컬 AI 서버 미구동 (정적 룰 검사 모드 작동 중): {e}",
                "models": default_local_models,
            }
    def get_system_status(self) -> dict[str, Any]:
        """
        현업 데스크톱의 핵심 환경 상태를 자가 진단하여 반환합니다.

        진단 항목:
        1. python_runtime: 실행 중인 Python 버전 및 경로
        2. winmerge_available: WinMergeU.exe CLI 실행 가능 여부
        3. ruleset_validity: Client/Server Excel 룰 카탈로그 파일 존재 및 파싱 유효성
        4. ai_online: 설정 파일 기반 로컬 AI 서버 연결 응답 상태

        Returns:
            {
                "success": bool,
                "python_runtime": {"status": "ok"|"warn", "version": str, "path": str},
                "winmerge_available": {"status": "ok"|"warn", "message": str},
                "ruleset_validity": {"status": "ok"|"error", "client": bool, "server": bool, "message": str},
                "ai_online": {"status": "ok"|"warn"|"offline", "message": str},
            }
        """
        import sys
        import urllib.request

        result: dict[str, Any] = {"success": True}

        # 1. Python 런타임 상태
        py_version = sys.version.split(" ")[0]
        py_path = sys.executable
        major, minor = sys.version_info.major, sys.version_info.minor
        py_status = "ok" if (major == 3 and minor >= 12) else "warn"
        result["python_runtime"] = {
            "status": py_status,
            "version": py_version,
            "path": py_path,
            "message": f"Python {py_version}" if py_status == "ok" else f"Python {py_version} (3.12 이상 권장)",
        }

        # 2. WinMerge 가용성
        winmerge_path = shutil.which("WinMergeU") or shutil.which("WinMerge")
        if not winmerge_path:
            # 일반적인 설치 경로 탐색
            import os
            common_paths = [
                r"C:\Program Files\WinMerge\WinMergeU.exe",
                r"C:\Program Files (x86)\WinMerge\WinMergeU.exe",
            ]
            winmerge_path = next((p for p in common_paths if os.path.isfile(p)), None)

        if winmerge_path:
            result["winmerge_available"] = {
                "status": "ok",
                "message": f"WinMerge 감지됨: {winmerge_path}",
                "path": winmerge_path,
            }
        else:
            result["winmerge_available"] = {
                "status": "warn",
                "message": "WinMerge 미설치 — difflib 폴백 모드로 작동합니다.",
                "path": None,
            }

        # 3. Excel 룰셋 파일 유효성
        try:
            cfg_path = self._resolve_settings_path()
            base_dir = cfg_path.parent.parent if cfg_path.name == "settings.yaml" else cfg_path.parent
            client_excel = base_dir / "config" / "(코드리뷰결과서-Client) 코드 리뷰 결과서 양식_v2.0_20251201.xlsx"
            server_excel = base_dir / "config" / "(코드리뷰결과서-Server) 코드 리뷰 결과서 양식_v2.0_20251104.xlsx"

            client_ok = client_excel.exists()
            server_ok = server_excel.exists()
            both_ok = client_ok and server_ok

            result["ruleset_validity"] = {
                "status": "ok" if both_ok else "error",
                "client": client_ok,
                "server": server_ok,
                "message": (
                    "Client/Server 룰셋 파일 정상"
                    if both_ok
                    else f"룰셋 파일 누락 — Client: {'O' if client_ok else 'X'}, Server: {'O' if server_ok else 'X'}"
                ),
            }
        except Exception as e:
            result["ruleset_validity"] = {
                "status": "error",
                "client": False,
                "server": False,
                "message": f"룰셋 파일 경로 탐색 실패: {e}",
            }

        # 4. AI 서버 온라인 상태
        try:
            import yaml
            cfg_path = self._resolve_settings_path()
            settings: dict[str, Any] = {}
            if cfg_path.exists():
                with open(cfg_path, encoding="utf-8-sig") as f:
                    settings = yaml.safe_load(f) or {}

            ai_cfg = settings.get("ai", {})
            local_srv = ai_cfg.get("local_server", {})
            host = str(local_srv.get("host", "127.0.0.1")).strip()
            port = int(local_srv.get("port", 8000))
            api_key = str(local_srv.get("api_key", "")).strip()

            url = f"http://{host}:{port}/v1/models"
            req = urllib.request.Request(url, method="GET")
            if api_key:
                req.add_header("Authorization", f"Bearer {api_key}")

            with urllib.request.urlopen(req, timeout=2.0) as resp:
                resp.read()

            result["ai_online"] = {
                "status": "ok",
                "message": f"AI 서버 응답 정상 ({host}:{port})",
                "host": host,
                "port": port,
            }
        except Exception as e:
            result["ai_online"] = {
                "status": "offline",
                "message": f"AI 서버 미연결 — 정적 룰 검사 모드로 작동합니다. ({e})",
                "host": None,
                "port": None,
            }

        return result

    def filter_review_results(
        self,
        report_dict: dict[str, Any],
        severities: list[str] | None = None,
        rule_id: str | None = None,
        path_prefix: str | None = None,
    ) -> dict[str, Any]:
        """
        리포트 딕셔너리에서 특정 심각도, 룰 ID, 파일 경로 프리픽스에 맞는 위반 내역을 필터링합니다.

        Args:
            report_dict: 기존에 실행된 전체 리뷰 리포트 딕셔너리
            severities: 원하는 심각도 리스트 (예: ['CRITICAL', 'HIGH'])
            rule_id: 필터링할 특정 룰 ID (예: 'CTL_RES_001')
            path_prefix: 파일 경로 필터 (예: 'scripts/')

        Returns:
            필터링된 위반 목록과 업데이트된 위반 요약 통계를 포함한 딕셔너리
        """
        if not report_dict or "violations" not in report_dict:
            return {"violations": [], "summary": {}, "total_violations": 0}

        violations = report_dict.get("violations", [])
        filtered: list[dict[str, Any]] = []

        sev_set = {s.upper() for s in severities} if severities else None
        target_rule = rule_id.strip().upper() if rule_id else None
        target_prefix = path_prefix.replace("\\", "/").strip() if path_prefix else None

        for v in violations:
            v_sev = str(v.get("severity", "")).upper()
            v_rule = str(v.get("rule_id", "")).upper()
            v_file = str(v.get("file_id", "")).replace("\\", "/")

            if sev_set and v_sev not in sev_set:
                continue
            if target_rule and target_rule != v_rule:
                continue
            if target_prefix and not v_file.startswith(target_prefix):
                continue

            filtered.append(v)

        # 필터링된 위반을 바탕으로 파일별 위반 수 계산
        file_counts: dict[str, int] = {}
        sev_counts: dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}

        for v in filtered:
            f = str(v.get("file_id", "unknown"))
            s = str(v.get("severity", "INFO")).upper()
            file_counts[f] = file_counts.get(f, 0) + 1
            if s in sev_counts:
                sev_counts[s] += 1

        return {
            "success": True,
            "violations": filtered,
            "total_violations": len(filtered),
            "severity_counts": sev_counts,
            "file_counts": file_counts,
        }

    def get_file_tree_summary(self, report_dict: dict[str, Any]) -> dict[str, Any]:
        """
        리포트 딕셔너리의 파일 경로들을 바탕으로 계층적 트리 구조와 폴더/파일별 위반 통계를 생성합니다.

        Returns:
            {
                "success": bool,
                "tree": [ { "name": "scripts", "type": "dir", "violation_count": 5, "children": [...] }, ... ]
            }
        """
        if not report_dict or "violations" not in report_dict:
            return {"success": True, "tree": [], "total_files": 0}

        violations = report_dict.get("violations", [])

        # 파일별 위반 수 집계
        file_violation_counts: dict[str, int] = {}
        for v in violations:
            f = str(v.get("file_id", "unknown")).replace("\\", "/")
            file_violation_counts[f] = file_violation_counts.get(f, 0) + 1

        # 계층 트리 구축을 위한 내부 노드 구조: { "name": str, "type": "dir"|"file", "count": int, "children": dict }
        root_nodes: dict[str, Any] = {}

        def _insert_path(path_parts: list[str], current_dict: dict[str, Any], count: int, full_path: str):
            part = path_parts[0]
            is_file = len(path_parts) == 1

            if part not in current_dict:
                current_dict[part] = {
                    "name": part,
                    "type": "file" if is_file else "dir",
                    "violation_count": 0,
                    "full_path": full_path if is_file else "",
                    "children": {},
                }

            current_dict[part]["violation_count"] += count

            if not is_file:
                _insert_path(path_parts[1:], current_dict[part]["children"], count, full_path)

        for f_path, v_cnt in file_violation_counts.items():
            parts = [p for p in f_path.split("/") if p]
            if parts:
                _insert_path(parts, root_nodes, v_cnt, f_path)

        # 딕셔너리 트리를 리스트 구조로 변환
        def _to_list(node_dict: dict[str, Any]) -> list[dict[str, Any]]:
            items = []
            for name in sorted(node_dict.keys()):
                node = node_dict[name]
                item = {
                    "name": node["name"],
                    "type": node["type"],
                    "violation_count": node["violation_count"],
                }
                if node["type"] == "file":
                    item["full_path"] = node["full_path"]
                else:
                    item["children"] = _to_list(node["children"])
                items.append(item)
            return items

        tree_list = _to_list(root_nodes)
        return {
            "success": True,
            "tree": tree_list,
            "total_files": len(file_violation_counts),
            "total_violations": len(violations),
        }

    def get_review_trend(self, current_report_dict: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        직전 검사 리포트와 현재 리포트를 대조하여 위반 트렌드(신규/해결/유지)를 산출합니다.
        (TRD Phase 3: 점진적 검사 및 트렌드 분석)

        Args:
            current_report_dict: 현재 리포트 딕셔너리 (None일 경우 최신 저장된 JSON 리포트 자동 조회)

        Returns:
            dict[str, Any]: {
                "success": bool,
                "has_previous": bool,
                "new_count": int,
                "resolved_count": int,
                "unchanged_count": int,
                "new_violations": list[dict],
                "resolved_violations": list[dict],
            }
        """
        try:
            curr_report = current_report_dict
            curr_violations = curr_report.get("violations", []) if curr_report else []

            output_dir = self.output_dir
            if not output_dir.exists():
                return {
                    "success": True,
                    "has_previous": False,
                    "new_count": len(curr_violations),
                    "resolved_count": 0,
                    "unchanged_count": 0,
                    "new_violations": curr_violations,
                    "resolved_violations": [],
                }


            json_reports = sorted(
                output_dir.glob("*_review_report.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            prev_report = None
            if curr_report is None:
                if len(json_reports) == 0:
                    return {
                        "success": True,
                        "has_previous": False,
                        "new_count": 0,
                        "resolved_count": 0,
                        "unchanged_count": 0,
                        "new_violations": [],
                        "resolved_violations": [],
                    }
                try:
                    with open(json_reports[0], encoding="utf-8") as f:
                        curr_report = json.load(f)
                        curr_violations = curr_report.get("violations", [])
                except Exception as e:
                    logger.debug("최신 리포트 로드 실패: %s", e)
                    return {"success": False, "error": f"최신 리포트 로드 실패: {e}"}

                if len(json_reports) >= 2:
                    try:
                        with open(json_reports[1], encoding="utf-8") as f:
                            prev_report = json.load(f)
                    except Exception:
                        pass
            else:
                curr_run_id = curr_report.get("run_id", "")
                for rep_file in json_reports:
                    try:
                        with open(rep_file, encoding="utf-8") as f:
                            candidate = json.load(f)
                        if curr_run_id and candidate.get("run_id") == curr_run_id:
                            continue
                        prev_report = candidate
                        break
                    except Exception as e:
                        logger.debug("리포트 후보 로드 실패 (%s): %s", rep_file, e)
                        continue




            if prev_report is None:
                # 이전 리포트가 없는 최초 검사 상황
                return {
                    "success": True,
                    "has_previous": False,
                    "new_count": len(curr_violations),
                    "resolved_count": 0,
                    "unchanged_count": 0,
                    "new_violations": curr_violations,
                    "resolved_violations": [],
                }

            prev_violations = prev_report.get("violations", [])

            def _v_key(v: dict[str, Any]) -> tuple[str, str, str]:
                return (
                    str(v.get("rule_id", "")).upper(),
                    str(v.get("file_id", "")).replace("\\", "/"),
                    str(v.get("line_start", "")),
                )

            curr_map = {_v_key(v): v for v in curr_violations}
            prev_map = {_v_key(v): v for v in prev_violations}

            curr_keys = set(curr_map.keys())
            prev_keys = set(prev_map.keys())

            new_keys = curr_keys - prev_keys
            resolved_keys = prev_keys - curr_keys
            unchanged_keys = curr_keys & prev_keys

            new_violations = [curr_map[k] for k in sorted(new_keys)]
            resolved_violations = [prev_map[k] for k in sorted(resolved_keys)]

            return {
                "success": True,
                "has_previous": True,
                "new_count": len(new_violations),
                "resolved_count": len(resolved_violations),
                "unchanged_count": len(unchanged_keys),
                "new_violations": new_violations,
                "resolved_violations": resolved_violations,
            }
        except Exception as e:
            logger.error("위반 트렌드 산출 실패: %s", e)
            return {"success": False, "error": str(e)}

    def get_code_diff(self, original_text: str, modified_text: str) -> dict[str, Any]:
        """
        원본 코드 텍스트와 수정본 텍스트의 Unified Diff 및 변경 라인 정보를 반환합니다.
        """
        try:
            orig_lines = original_text.splitlines(keepends=True)
            mod_lines = modified_text.splitlines(keepends=True)
            diff_lines = list(
                difflib.unified_diff(
                    orig_lines,
                    mod_lines,
                    fromfile="Original",
                    tofile="Modified",
                    n=3,
                )
            )
            diff_text = "".join(diff_lines)
            return {
                "success": True,
                "diff_text": diff_text,
                "has_changes": bool(diff_lines),
            }
        except Exception as e:
            logger.error("Diff 산출 중 오류 발생: %s", e)
            return {"success": False, "error": str(e)}

    def open_in_winmerge(self, original_file_path: str, modified_text: str) -> dict[str, Any]:
        """
        WinMerge를 실행하여 원본 파일과 AI 수정본을 1-Click GUI Diff로 비교합니다.
        WinMerge가 설치되지 않은 경우 builtin Diff 결과를 반환합니다.
        """
        try:
            orig_path = Path(original_file_path)
            if not orig_path.exists():
                return {"success": False, "error": f"원본 파일을 찾을 수 없습니다: {original_file_path}"}

            from app.core.autofix.engine import AutofixEngine
            from app.core.diff.winmerge_runner import WinMergeRunner

            autofix_file = orig_path.with_suffix(orig_path.suffix + ".autofixed")
            real_modified_text = ""

            if autofix_file.exists():
                try:
                    real_modified_text = read_text_with_fallback(autofix_file)
                except (UnicodeDecodeError, FileNotFoundError):
                    pass
            elif hasattr(self, "_last_report") and self._last_report:
                file_violations = [v for v in self._last_report.violations if str(v.file_id) == str(orig_path) or Path(str(v.file_id)).name == orig_path.name]
                if file_violations:
                    engine = AutofixEngine(enabled=True)
                    generated_path, ok = engine.apply_autofix(orig_path, file_violations)
                    if ok and generated_path.exists():
                        try:
                            real_modified_text = read_text_with_fallback(generated_path)
                        except (UnicodeDecodeError, FileNotFoundError):
                            pass

            if real_modified_text:
                modified_text = real_modified_text

            runner = WinMergeRunner()
            temp_dir = Path(tempfile.gettempdir()) / "wincc_reviewer_diff"
            temp_dir.mkdir(parents=True, exist_ok=True)
            mod_path = temp_dir / f"{orig_path.stem}.modified{orig_path.suffix}"
            mod_path.write_text(modified_text, encoding="utf-8")

            if runner.executable_path and Path(runner.executable_path).exists():
                try:
                    subprocess.Popen([runner.executable_path, str(orig_path), str(mod_path)])
                    return {
                        "success": True,
                        "mode": "winmerge",
                        "message": "WinMerge 창이 열렸습니다. GUI에서 1-Click Diff 및 수정이 가능합니다.",
                        "modified_path": str(mod_path),
                    }
                except Exception as ex:
                    logger.warning("WinMerge 실행 실패 -> builtin Diff로 전환합니다: %s", ex)

            try:
                orig_text = read_text_with_fallback(orig_path)
            except (UnicodeDecodeError, FileNotFoundError):
                orig_text = ""

            diff_res = self.get_code_diff(orig_text, modified_text)
            return {
                "success": True,
                "mode": "builtin",
                "message": "WinMerge 미설치로 내장 Diff 뷰어를 제공합니다.",
                "diff_text": diff_res.get("diff_text", ""),
                "modified_path": str(mod_path),
            }
        except Exception as e:
            logger.error("WinMerge/Diff 1-Click 실행 실패: %s", e)
            return {"success": False, "error": str(e)}





