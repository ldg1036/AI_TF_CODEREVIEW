import datetime
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from typing import Dict, List, Optional, Tuple


class CtrlppWrapper:
    """Wrapper for invoking Siemens CtrlppCheck in fail-soft mode."""
    _install_lock = threading.Lock()

    def __init__(self, tool_path: Optional[str] = None, config_path: Optional[str] = None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.project_root = os.path.abspath(os.path.join(base_dir, ".."))
        self.config_path = config_path or os.path.join(self.project_root, "Config", "config.json")
        self.config = self._load_ctrlpp_config(self.config_path)

        self.default_enabled = bool(self.config.get("enabled_default", False))
        self.timeout_sec = self._safe_int(self.config.get("timeout_sec", 30) or 30, 30)
        self.enable_levels = str(self.config.get("enable_levels", "style,information") or "style,information")
        self.winccoa_project_name = str(
            self.config.get("winccoa_project_name", os.environ.get("WINCCOA_PROJECT_NAME", "CodeReviewProject"))
            or "CodeReviewProject"
        ).strip()
        if not self.winccoa_project_name:
            self.winccoa_project_name = "CodeReviewProject"
        self.version = str(self.config.get("version", "v1.0.2") or "v1.0.2")
        self.auto_install_on_missing = bool(self.config.get("auto_install_on_missing", True))
        self.github_repo = str(self.config.get("github_repo", "siemens/CtrlppCheck") or "siemens/CtrlppCheck")
        self.asset_pattern = str(
            self.config.get("asset_pattern", "WinCCOA_QualityChecks_*.zip") or "WinCCOA_QualityChecks_*.zip"
        )
        self.install_dir = self._resolve_optional_path(self.config.get("install_dir", "tools/CtrlppCheck"))
        if not self.install_dir:
            self.install_dir = os.path.join(self.project_root, "tools", "CtrlppCheck")

        self.rule_file = self._resolve_optional_path(self.config.get("rule_file"))
        self.naming_rule_file = self._resolve_optional_path(self.config.get("naming_rule_file"))
        self.library = self._resolve_optional_path(self.config.get("library"))
        self.suppressions_list = self._resolve_optional_path(self.config.get("suppressions_list"))

        self.persist_install_metadata_to_config = bool(self.config.get("persist_install_metadata_to_config", False))
        configured_state_path = self._resolve_optional_path(self.config.get("install_state_path"))
        self.install_state_path = configured_state_path or os.path.join(self.install_dir, "install_state.json")
        self.install_state = self._load_install_state(self.install_state_path)
        self.state_binary_path = self._resolve_optional_path(self.install_state.get("binary_path"))

        self.config_binary_path = self._resolve_optional_path(self.config.get("binary_path"))
        self.tool_path = tool_path
        self._install_retry_block_until = 0.0
        self._install_retry_block_reason = ""

    @staticmethod
    def _safe_int(value, fallback):
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _perf_now() -> float:
        try:
            return datetime.datetime.now(datetime.timezone.utc).timestamp()
        except Exception:
            return 0.0

    def _load_ctrlpp_config(self, path: str) -> Dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            section = payload.get("ctrlppcheck", {})
            return section if isinstance(section, dict) else {}
        except Exception:
            return {}

    def _resolve_optional_path(self, path_value: Optional[str]) -> str:
        if not path_value:
            return ""
        candidate = str(path_value).strip()
        if not candidate:
            return ""
        if os.path.isabs(candidate):
            return candidate
        return os.path.normpath(os.path.join(self.project_root, candidate))

    @staticmethod
    def _is_within_path(path_value: str, root_value: str) -> bool:
        if not path_value or not root_value:
            return False
        try:
            path_norm = os.path.normcase(os.path.abspath(path_value))
            root_norm = os.path.normcase(os.path.abspath(root_value))
            return os.path.commonpath([path_norm, root_norm]) == root_norm
        except Exception:
            return False

    def _is_trusted_state_binary_path(self, path_value: str) -> bool:
        normalized = self._resolve_optional_path(path_value)
        if not normalized:
            return False
        if self._is_within_path(normalized, self.install_dir):
            return True
        # Allow project-local binaries, but ignore state pointing to unrelated repos/machines.
        if self._is_within_path(normalized, self.project_root):
            return True
        return False

    def _find_binary(self, binary_path: Optional[str] = None) -> str:
        candidates = []
        if binary_path:
            candidates.append(binary_path)
        if self.tool_path:
            candidates.append(self.tool_path)
        if self.state_binary_path and self._is_trusted_state_binary_path(self.state_binary_path):
            candidates.append(self.state_binary_path)
        if self.config_binary_path:
            candidates.append(self.config_binary_path)

        env_path = os.environ.get("CTRLPPCHECK_PATH", "").strip()
        if env_path:
            candidates.append(env_path)

        for item in candidates:
            normalized = self._resolve_optional_path(item)
            if normalized and os.path.exists(normalized):
                if os.path.basename(normalized).lower() == "ctrlppcheck":
                    exe_candidate = normalized + ".exe"
                    if os.path.exists(exe_candidate):
                        return exe_candidate
                return normalized

        for executable in ("ctrlppcheck", "ctrlppcheck.exe"):
            found = shutil.which(executable)
            if found:
                return found
        return ""

    @staticmethod
    def _safe_json_load(path: str) -> Dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _load_install_state(path: str) -> Dict:
        if not path or not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _github_headers() -> Dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "User-Agent": "wincc-oa-code-inspector",
        }

    def _fetch_release_payload(self) -> Dict:
        url = f"https://api.github.com/repos/{self.github_repo}/releases/tags/{self.version}"
        req = urllib.request.Request(url=url, headers=self._github_headers(), method="GET")
        timeout = max(self.timeout_sec, 30)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise RuntimeError("release payload is not a JSON object")
        return payload

    def _select_release_asset(self, release_payload: Dict) -> Dict:
        assets = release_payload.get("assets") or []
        if not isinstance(assets, list):
            raise RuntimeError("release assets format is invalid")
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name", ""))
            if fnmatch.fnmatch(name, self.asset_pattern):
                return asset
        raise RuntimeError(f"asset not found for pattern '{self.asset_pattern}'")

    def _download_asset(self, download_url: str, destination_path: str):
        if not download_url:
            raise RuntimeError("asset download URL is empty")
        req = urllib.request.Request(url=download_url, headers=self._github_headers(), method="GET")
        timeout = max(self.timeout_sec, 60)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            with open(destination_path, "wb") as out:
                shutil.copyfileobj(resp, out)

    @staticmethod
    def _compute_sha256(file_path: str) -> str:
        digest = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def _verify_asset_checksum(self, file_path: str, digest_field: str):
        if not digest_field:
            return
        digest_value = str(digest_field).strip()
        if not digest_value:
            return
        expected = digest_value.split(":", 1)[1] if digest_value.lower().startswith("sha256:") else digest_value
        expected = expected.lower()
        actual = self._compute_sha256(file_path).lower()
        if actual != expected:
            raise RuntimeError(f"CtrlppCheck checksum mismatch: expected {expected}, actual {actual}")

    @staticmethod
    def _extract_archive(zip_path: str, extract_dir: str):
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

    @staticmethod
    def _find_installed_binary(search_root: str) -> str:
        fallback = ""
        for root, _, files in os.walk(search_root):
            for name in files:
                lower = name.lower()
                if lower == "ctrlppcheck.exe":
                    return os.path.join(root, name)
                if lower == "ctrlppcheck" and not fallback:
                    fallback = os.path.join(root, name)
        return fallback

    def _atomic_write_json(self, path: str, payload: Dict):
        parent = os.path.dirname(path)
        os.makedirs(parent, exist_ok=True)
        tmp_path = ""
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=parent, suffix=".tmp") as tmp:
                json.dump(payload, tmp, ensure_ascii=False, indent=2)
                tmp_path = tmp.name
            os.replace(tmp_path, path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _persist_installed_binary_metadata(self, binary_path: str):
        normalized_binary = os.path.normpath(binary_path)
        now_utc = (
            datetime.datetime.now(datetime.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

        state_payload = {
            "binary_path": normalized_binary,
            "installed_version": self.version,
            "installed_at": now_utc,
        }
        self._atomic_write_json(self.install_state_path, state_payload)
        self.install_state = state_payload
        self.state_binary_path = normalized_binary

        if self.persist_install_metadata_to_config:
            config_payload = self._safe_json_load(self.config_path)
            section = config_payload.get("ctrlppcheck")
            if not isinstance(section, dict):
                section = {}
                config_payload["ctrlppcheck"] = section
            section["binary_path"] = normalized_binary
            section["installed_version"] = self.version
            section["installed_at"] = now_utc
            self._atomic_write_json(self.config_path, config_payload)
            self.config = section
            self.config_binary_path = normalized_binary

    # Backward-compatible wrapper name used by existing call sites/tests.
    def _write_binary_path_to_config(self, binary_path: str):
        self._persist_installed_binary_metadata(binary_path)

    def ensure_installed(self) -> Tuple[str, str]:
        with self._install_lock:
            existing = self._find_binary()
            if existing:
                return existing, ""

            cached_extract_dir = os.path.join(self.install_dir, self.version, "extract")
            if os.path.isdir(cached_extract_dir):
                cached_binary = self._find_installed_binary(cached_extract_dir)
                if cached_binary:
                    try:
                        self._write_binary_path_to_config(cached_binary)
                    except Exception:
                        pass
                    return cached_binary, ""

            try:
                release_payload = self._fetch_release_payload()
            except Exception as exc:
                return "", f"CtrlppCheck download failed: {exc}"

            try:
                asset = self._select_release_asset(release_payload)
            except Exception as exc:
                return "", f"CtrlppCheck install failed: {exc}"

            version_dir = os.path.join(self.install_dir, self.version)
            download_dir = os.path.join(version_dir, "download")
            extract_dir = os.path.join(version_dir, "extract")
            os.makedirs(download_dir, exist_ok=True)
            os.makedirs(extract_dir, exist_ok=True)

            zip_name = asset.get("name") or f"CtrlppCheck_{self.version}.zip"
            zip_path = os.path.join(download_dir, zip_name)

            try:
                self._download_asset(str(asset.get("browser_download_url", "")), zip_path)
            except Exception as exc:
                return "", f"CtrlppCheck download failed: {exc}"

            try:
                self._verify_asset_checksum(zip_path, str(asset.get("digest", "") or ""))
            except Exception as exc:
                message = str(exc)
                if not message.startswith("CtrlppCheck checksum mismatch:"):
                    message = f"CtrlppCheck checksum mismatch: {message}"
                return "", message

            try:
                if os.path.isdir(extract_dir):
                    shutil.rmtree(extract_dir, ignore_errors=True)
                os.makedirs(extract_dir, exist_ok=True)
                self._extract_archive(zip_path, extract_dir)
            except Exception as exc:
                return "", f"CtrlppCheck install failed: {exc}"

            binary = self._find_installed_binary(extract_dir)
            if not binary:
                return "", "CtrlppCheck install failed: ctrlppcheck executable not found in archive"

            try:
                self._write_binary_path_to_config(binary)
            except Exception as exc:
                return "", f"CtrlppCheck install failed: metadata update failed: {exc}"

            return binary, ""

    def _set_install_retry_block(self, reason: str, seconds: int = 30):
        now = self._perf_now()
        self._install_retry_block_until = now + max(1, int(seconds or 1))
        self._install_retry_block_reason = str(reason or "").strip()

    def _clear_install_retry_block(self):
        self._install_retry_block_until = 0.0
        self._install_retry_block_reason = ""

    def _is_install_retry_blocked(self) -> bool:
        return self._perf_now() < float(self._install_retry_block_until or 0.0)

    def prepare_for_analysis(self, enabled: bool, selected_files: List[str]) -> Dict[str, object]:
        """Best-effort preflight for CtrlppCheck before analysis begins."""
        result: Dict[str, object] = {
            "attempted": False,
            "ready": False,
            "binary_path": "",
            "message": "",
            "error_code": "",
        }
        if not bool(enabled):
            result["message"] = "CtrlppCheck preflight skipped: disabled"
            return result

        has_ctl_target = any(str(item or "").lower().endswith(".ctl") for item in (selected_files or []))
        if not has_ctl_target:
            result["message"] = "CtrlppCheck preflight skipped: no .ctl target"
            return result

        existing = self._find_binary()
        if existing:
            result["ready"] = True
            result["binary_path"] = existing
            result["message"] = "CtrlppCheck preflight ready: existing binary found"
            self._clear_install_retry_block()
            return result

        if not self.auto_install_on_missing:
            msg = "CtrlppCheck binary not found (auto_install_on_missing=false)"
            result["message"] = msg
            result["error_code"] = "CTRLPPCHECK_NOT_FOUND"
            self._set_install_retry_block(msg)
            return result

        result["attempted"] = True
        try:
            binary, install_error = self.ensure_installed()
        except Exception as exc:
            binary, install_error = "", f"CtrlppCheck install failed: {exc}"

        if binary:
            result["ready"] = True
            result["binary_path"] = binary
            result["message"] = "CtrlppCheck preflight ready: installed"
            self._clear_install_retry_block()
            return result

        lowered = str(install_error or "").lower()
        if "download failed" in lowered:
            result["error_code"] = "CTRLPPCHECK_INSTALL_FAILED"
        elif "install failed" in lowered:
            result["error_code"] = "CTRLPPCHECK_INSTALL_FAILED"
        else:
            result["error_code"] = "CTRLPPCHECK_NOT_FOUND"
        result["message"] = str(install_error or "CtrlppCheck binary not found")
        self._set_install_retry_block(result["message"])
        return result

    def _build_command(self, binary: str, file_path: str) -> List[str]:
        cmd = [
            binary,
            "--xml",
            f"--enable={self.enable_levels}",
            f"--winccoa-projectName={self.winccoa_project_name}",
            file_path,
        ]
        if self.rule_file and os.path.exists(self.rule_file):
            cmd.append(f"--rule-file={self.rule_file}")
        if self.naming_rule_file and os.path.exists(self.naming_rule_file):
            cmd.append(f"--naming-rule-file={self.naming_rule_file}")
        if self.library and os.path.exists(self.library):
            cmd.append(f"--library={self.library}")
        if self.suppressions_list and os.path.exists(self.suppressions_list):
            cmd.append(f"--suppressions-list={self.suppressions_list}")
        return cmd

    @staticmethod
    def _extract_xml_block(text: str) -> str:
        if not text:
            return ""
        start = text.find("<?xml")
        if start < 0:
            start = text.find("<results")
        if start < 0:
            return ""
        end_tag = "</results>"
        end = text.rfind(end_tag)
        if end < 0:
            return ""
        end += len(end_tag)
        return text[start:end]

    def _parse_xml_report(self, xml_text: str, default_file: str) -> List[Dict]:
        parsed: List[Dict] = []
        if not xml_text.strip():
            return parsed

        root = ET.fromstring(xml_text)
        errors = root.find("errors")
        if errors is None:
            return parsed

        for err in errors.findall("error"):
            err_id = err.attrib.get("id", "ctrlppcheck.unknown")
            severity = err.attrib.get("severity", "information")
            message = err.attrib.get("msg") or err.attrib.get("verbose") or "CtrlppCheck finding"
            verbose = err.attrib.get("verbose", "")
            locations = err.findall("location")

            if not locations:
                parsed.append(
                    {
                        "type": severity,
                        "severity": severity,
                        "rule_id": err_id,
                        "line": 0,
                        "message": message,
                        "verbose": verbose,
                        "file": default_file,
                        "source": "CtrlppCheck",
                        "priority_origin": "P2",
                    }
                )
                continue

            for loc in locations:
                line_value = self._safe_int(loc.attrib.get("line"), 0)
                parsed.append(
                    {
                        "type": severity,
                        "severity": severity,
                        "rule_id": err_id,
                        "line": line_value,
                        "message": message,
                        "verbose": verbose,
                        "file": loc.attrib.get("file", default_file),
                        "source": "CtrlppCheck",
                        "priority_origin": "P2",
                    }
                )
        return parsed

    @staticmethod
    def _build_info_violation(message: str, file_path: str = "", violation_type: str = "information") -> Dict:
        return {
            "type": violation_type,
            "severity": violation_type,
            "rule_id": "ctrlppcheck.info",
            "line": 0,
            "message": message,
            "verbose": "",
            "file": file_path,
            "source": "CtrlppCheck",
            "priority_origin": "P2",
        }

    def run_check(
        self,
        file_path: str,
        code_content: str = None,
        enabled: Optional[bool] = None,
        binary_path: Optional[str] = None,
    ) -> List[Dict]:
        use_ctrlpp = self.default_enabled if enabled is None else bool(enabled)
        if not use_ctrlpp:
            return []

        if not str(file_path).lower().endswith(".ctl"):
            return []

        explicit_binary_override = bool(str(binary_path or "").strip())
        if explicit_binary_override:
            binary = ""
            explicit_candidate = self._resolve_optional_path(binary_path)
            if explicit_candidate and os.path.exists(explicit_candidate):
                if os.path.basename(explicit_candidate).lower() == "ctrlppcheck":
                    exe_candidate = explicit_candidate + ".exe"
                    binary = exe_candidate if os.path.exists(exe_candidate) else explicit_candidate
                else:
                    binary = explicit_candidate
        else:
            binary = self._find_binary(binary_path=None)

        if not binary and self.auto_install_on_missing and not self._is_install_retry_blocked():
            try:
                if explicit_binary_override:
                    original_find_binary = self._find_binary
                    self._find_binary = lambda *args, **kwargs: ""
                    try:
                        binary, install_error = self.ensure_installed()
                    finally:
                        self._find_binary = original_find_binary
                else:
                    binary, install_error = self.ensure_installed()
            except Exception as exc:
                install_error = f"CtrlppCheck install failed: {exc}"
            if not binary and install_error:
                self._set_install_retry_block(install_error)
                return [
                    self._build_info_violation(
                        install_error,
                        file_path=file_path,
                        violation_type="warning",
                    )
                ]
        elif not binary and self.auto_install_on_missing and self._is_install_retry_blocked():
            reason = self._install_retry_block_reason or "CtrlppCheck install retry temporarily suppressed"
            return [
                self._build_info_violation(
                    reason,
                    file_path=file_path,
                    violation_type="warning",
                )
            ]
        if not binary:
            return [
                self._build_info_violation(
                    "CtrlppCheck binary not found. Set CTRLPPCHECK_PATH or config.ctrlppcheck.binary_path.",
                    file_path=file_path,
                )
            ]

        cmd = self._build_command(binary, file_path)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )
        except subprocess.TimeoutExpired:
            return [
                self._build_info_violation(
                    f"CtrlppCheck timed out after {self.timeout_sec}s.",
                    file_path=file_path,
                    violation_type="warning",
                )
            ]
        except Exception as exc:
            return [
                self._build_info_violation(
                    f"CtrlppCheck execution error: {exc}",
                    file_path=file_path,
                    violation_type="warning",
                )
            ]

        xml_text = self._extract_xml_block(result.stderr) or self._extract_xml_block(result.stdout)
        if not xml_text:
            tail = (result.stderr or result.stdout or "").strip()
            tail = re.sub(r"\s+", " ", tail)[:300]
            if result.returncode != 0:
                return [
                    self._build_info_violation(
                        f"CtrlppCheck failed (exit={result.returncode}). {tail}",
                        file_path=file_path,
                        violation_type="warning",
                    )
                ]
            message = "CtrlppCheck returned no XML output."
            if tail:
                message = f"{message} {tail}"
            return [
                self._build_info_violation(
                    message,
                    file_path=file_path,
                    violation_type="warning",
                )
            ]

        try:
            parsed = self._parse_xml_report(xml_text, default_file=file_path)
            return parsed
        except Exception as exc:
            return [
                self._build_info_violation(
                    f"CtrlppCheck XML parse error: {exc}",
                    file_path=file_path,
                    violation_type="warning",
                )
            ]
