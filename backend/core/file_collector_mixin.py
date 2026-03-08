"""FileCollectorMixin – file listing, conversion, and collection logic extracted from main.py."""

import glob
import os
import tempfile
import threading
import uuid
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FileCollectorMixin:
    """Mixin providing file discovery, .pnl/.xml conversion, and target collection.

    Host class must supply (via __init__):
        data_dir              : str
        pnl_parser            : PnlParser
        xml_parser            : XmlParser
        _conversion_cache     : dict
        _conversion_cache_lock: threading.Lock
        _get_conversion_lock  : Callable
    And static/class helpers:
        _perf_now, _elapsed_ms, _safe_int, _source_signature,
        _metrics_add_timing, _metrics_inc, _metrics_inc_nested,
        _normalize_local_path (delegated here)
    """

    # ------------------------------------------------------------------
    # File listing
    # ------------------------------------------------------------------

    def list_available_files(self, allow_raw_txt=False):
        files = []

        for ext in ("*.ctl", "*.pnl", "*.xml"):
            for path in glob.glob(os.path.join(self.data_dir, ext)):
                files.append(
                    {
                        "name": os.path.basename(path),
                        "type": os.path.splitext(path)[1].lstrip("."),
                        "selectable": True,
                    }
                )

        for path in glob.glob(os.path.join(self.data_dir, "*.txt")):
            name = os.path.basename(path)
            if self._is_reviewed_txt(name):
                continue
            if self._is_raw_txt(name) and not allow_raw_txt:
                continue
            files.append(
                {
                    "name": name,
                    "type": "txt",
                    "selectable": True,
                }
            )

        return sorted(files, key=lambda item: item["name"].lower())

    def stage_input_files(self, uploaded_files: List[Dict[str, Any]], mode: str = "files") -> Dict[str, Any]:
        stage_root = tempfile.mkdtemp(prefix="winccoa_inputs_")
        staged_paths: List[str] = []
        for item in uploaded_files or []:
            if not isinstance(item, dict):
                continue
            rel_name = str(item.get("name", "") or "").replace("\\", "/").strip("/")
            content = item.get("content", b"")
            if not rel_name:
                continue
            safe_parts = [part for part in rel_name.split("/") if part not in ("", ".", "..")]
            if not safe_parts:
                continue
            target_path = os.path.join(stage_root, *safe_parts)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "wb") as handle:
                handle.write(content if isinstance(content, (bytes, bytearray)) else bytes(content))
            staged_paths.append(os.path.normpath(target_path))

        if not staged_paths:
            raise ValueError("No uploaded files to stage")

        root_label = os.path.basename(stage_root)
        if str(mode or "").lower() == "folder":
            relative_roots = {
                str(path).replace("\\", "/").split("/")[-2]
                for path in staged_paths
                if len(str(path).replace("\\", "/").split("/")) >= 2
            }
            if len(relative_roots) == 1:
                root_label = next(iter(relative_roots))
            return {
                "ok": True,
                "input_sources": [{"type": "folder_path", "value": stage_root, "label": root_label}],
                "staged_count": len(staged_paths),
            }

        return {
            "ok": True,
            "input_sources": [
                {"type": "file_path", "value": path, "label": os.path.basename(path)}
                for path in staged_paths
            ],
            "staged_count": len(staged_paths),
        }

    # ------------------------------------------------------------------
    # Filename helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_local_path(path_value: str) -> str:
        return os.path.normpath(os.path.abspath(str(path_value or "").strip()))

    @staticmethod
    def _is_normalized_txt(name):
        return name.endswith("_pnl.txt") or name.endswith("_xml.txt")

    @staticmethod
    def _is_reviewed_txt(name):
        return name.endswith("_REVIEWED.txt")

    @classmethod
    def _is_raw_txt(cls, name):
        return name.endswith(".txt") and not cls._is_normalized_txt(name) and not cls._is_reviewed_txt(name)

    @classmethod
    def _normalized_name_for_source(cls, name: str) -> str:
        if not isinstance(name, str):
            return ""
        lower = name.lower()
        if lower.endswith(".pnl"):
            return name[:-4] + "_pnl.txt"
        if lower.endswith(".xml"):
            return name[:-4] + "_xml.txt"
        return name

    @classmethod
    def _reviewed_name_for_source(cls, name: str) -> str:
        normalized = cls._normalized_name_for_source(name)
        if normalized.lower().endswith(".txt"):
            return normalized[:-4] + "_REVIEWED.txt"
        if normalized.lower().endswith(".ctl"):
            return normalized[:-4] + "_REVIEWED.txt"
        return ""

    @classmethod
    def _candidate_cached_filenames(cls, name: str):
        base = os.path.basename(str(name or ""))
        if not base:
            return []
        candidates = [base]
        normalized = cls._normalized_name_for_source(base)
        if normalized and normalized not in candidates:
            candidates.append(normalized)
        return candidates

    # ------------------------------------------------------------------
    # Folder scanning
    # ------------------------------------------------------------------

    def _scan_folder_targets(self, folder_path: str, allow_raw_txt: bool) -> List[str]:
        targets: List[str] = []
        root = self._normalize_local_path(folder_path)
        for current_root, _dirs, files in os.walk(root):
            for name in files:
                full_path = os.path.normpath(os.path.join(current_root, name))
                lower = name.lower()
                if lower.endswith(".ctl") or lower.endswith(".pnl") or lower.endswith(".xml"):
                    targets.append(full_path)
                    continue
                if lower.endswith(".txt"):
                    if self._is_reviewed_txt(name):
                        continue
                    if self._is_raw_txt(name) and not allow_raw_txt:
                        continue
                    targets.append(full_path)
        return sorted(set(targets))

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _convert_external_targets(self, selected_paths: List[str], metrics: Optional[Dict] = None) -> List[str]:
        generated_txt_files: List[str] = []
        for source in selected_paths:
            source_norm = os.path.normpath(str(source or ""))
            lower = source_norm.lower()
            if lower.endswith(".pnl"):
                target_path = self._convert_single_source(
                    source_norm,
                    converter_fn=self.pnl_parser.convert_to_text,
                    suffix="_pnl.txt",
                    metrics=metrics,
                )
                if target_path:
                    generated_txt_files.append(target_path)
            elif lower.endswith(".xml"):
                target_path = self._convert_single_source(
                    source_norm,
                    converter_fn=self.xml_parser.parse,
                    suffix="_xml.txt",
                    metrics=metrics,
                )
                if target_path:
                    generated_txt_files.append(target_path)
        return generated_txt_files

    def _convert_single_source(self, source: str, converter_fn, suffix: str, metrics: Optional[Dict] = None) -> str:
        source_name = os.path.basename(source)
        target_path = os.path.splitext(source)[0] + suffix
        lock = self._get_conversion_lock(source)
        started = self._perf_now()
        with lock:
            try:
                signature = self._source_signature(source)
                cache_key = os.path.normpath(source)
                with self._conversion_cache_lock:
                    cache_entry = self._conversion_cache.get(cache_key)
                    if (
                        isinstance(cache_entry, dict)
                        and tuple(cache_entry.get("sig", ())) == signature
                        and os.path.isfile(target_path)
                    ):
                        self._metrics_inc_nested(metrics, "convert_cache", "hits", 1)
                        return target_path

                with open(source, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                self._metrics_inc(metrics, "bytes_read", len(content.encode("utf-8", errors="ignore")))
                txt_content = converter_fn(content)
                temp_path = f"{target_path}.tmp.{threading.get_ident()}.{uuid.uuid4().hex[:8]}"
                try:
                    with open(temp_path, "w", encoding="utf-8") as f:
                        f.write(txt_content)
                    os.replace(temp_path, target_path)
                finally:
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except OSError:
                            pass
                with self._conversion_cache_lock:
                    self._conversion_cache[cache_key] = {"sig": signature, "target_path": target_path}
                self._metrics_inc_nested(metrics, "convert_cache", "misses", 1)
                self._metrics_inc(metrics, "bytes_written", len(txt_content.encode("utf-8", errors="ignore")))
                logger.info("Converted: %s -> %s", source_name, os.path.basename(target_path))
                return target_path
            except Exception as e:
                logger.warning("Error converting %s: %s", source, e)
                return ""
            finally:
                self._metrics_add_timing(metrics, "convert", self._elapsed_ms(started))

    def convert_sources(self, selected_files=None, metrics: Optional[Dict] = None, include_all_builtin: bool = True):
        selected = set(selected_files or [])
        generated_txt_files = []

        pnl_files = glob.glob(os.path.join(self.data_dir, "*.pnl"))
        xml_files = glob.glob(os.path.join(self.data_dir, "*.xml"))

        for source in pnl_files:
            source_name = os.path.basename(source)
            if not include_all_builtin and source_name not in selected:
                continue
            target_path = self._convert_single_source(
                source,
                converter_fn=self.pnl_parser.convert_to_text,
                suffix="_pnl.txt",
                metrics=metrics,
            )
            if target_path:
                generated_txt_files.append(target_path)

        for source in xml_files:
            source_name = os.path.basename(source)
            if not include_all_builtin and source_name not in selected:
                continue
            target_path = self._convert_single_source(
                source,
                converter_fn=self.xml_parser.parse,
                suffix="_xml.txt",
                metrics=metrics,
            )
            if target_path:
                generated_txt_files.append(target_path)

        return generated_txt_files

    # ------------------------------------------------------------------
    # Viewer content
    # ------------------------------------------------------------------

    def get_viewer_content(self, name: str, prefer_source: bool = False, output_dir: Optional[str] = None) -> dict:
        """Return reviewed/normalized/source text for the code viewer."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name is required")
        requested = str(name or "").strip()
        basename = os.path.basename(requested)

        def _read_text(path: str, resolved_name: str, source_kind: str, display_name: str, resolved_path: str = ""):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return {
                    "file": display_name,
                    "resolved_name": resolved_name,
                    "resolved_path": resolved_path or path,
                    "source": source_kind,
                    "content": f.read(),
                }

        target_output_dir = os.path.normpath(str(output_dir or self._last_output_dir or ""))
        if target_output_dir:
            session = self._get_review_session(target_output_dir)
            if session:
                try:
                    _session_output_dir, _session, resolved_cache_key, cached = self._resolve_review_session_and_file(requested, output_dir=target_output_dir)
                    display_name = str(cached.get("display_name", "") or cached.get("file", "") or basename or requested)
                    source_path = str(cached.get("source_path", "") or "")
                    resolved_viewer_path = source_path
                    if not resolved_viewer_path:
                        candidate_cache_key = str(resolved_cache_key or "")
                        if candidate_cache_key and os.path.isabs(candidate_cache_key):
                            resolved_viewer_path = candidate_cache_key
                    reviewed_name = str(cached.get("reviewed_name", "") or self._reviewed_name_for_source(display_name))
                    if reviewed_name and os.path.isdir(target_output_dir):
                        reviewed_path = os.path.join(target_output_dir, reviewed_name)
                        if os.path.isfile(reviewed_path) and not prefer_source:
                            return _read_text(reviewed_path, reviewed_name, "reviewed", display_name, resolved_viewer_path or reviewed_path)
                    if prefer_source and source_path and os.path.isfile(source_path):
                        return _read_text(source_path, display_name, "source", display_name, resolved_viewer_path or source_path)
                    if source_path and os.path.isfile(source_path):
                        return _read_text(source_path, display_name, "source", display_name, resolved_viewer_path or source_path)
                except FileNotFoundError:
                    pass

        normalized_requested = self._normalize_local_path(requested) if os.path.isabs(requested) else ""
        if normalized_requested and os.path.isfile(normalized_requested):
            display_name = os.path.basename(normalized_requested)
            return _read_text(normalized_requested, display_name, "source", display_name, normalized_requested)

        reviewed_name = self._reviewed_name_for_source(basename)
        normalized_name = self._normalized_name_for_source(basename)
        source_path = os.path.join(self.data_dir, basename)
        normalized_path = os.path.join(self.data_dir, normalized_name)

        if prefer_source and os.path.isfile(source_path):
            return _read_text(source_path, basename, "source", basename, source_path)

        if reviewed_name and target_output_dir and os.path.isdir(target_output_dir):
            reviewed_path = os.path.join(target_output_dir, reviewed_name)
            if os.path.isfile(reviewed_path):
                return _read_text(reviewed_path, reviewed_name, "reviewed", basename, source_path)

        if normalized_name != basename and os.path.isfile(normalized_path):
            return _read_text(normalized_path, normalized_name, "normalized", basename, normalized_path)

        if os.path.isfile(source_path):
            return _read_text(source_path, basename, "source", basename, source_path)

        raise FileNotFoundError(f"File not found: {requested}")

    # ------------------------------------------------------------------
    # Target collection (main entry point)
    # ------------------------------------------------------------------

    @staticmethod
    def infer_file_type(filename):
        # Rule split policy: .ctl => Server, .txt (converted/raw) => Client.
        return "Server" if filename.lower().endswith(".ctl") else "Client"

    def collect_targets(self, selected_files=None, allow_raw_txt=False, metrics: Optional[Dict] = None, input_sources: Optional[List[Dict[str, Any]]] = None):
        selected = set(selected_files or [])
        include_all_builtin = not selected and not list(input_sources or [])
        generated_txt_files = self.convert_sources(
            selected_files=selected_files,
            metrics=metrics,
            include_all_builtin=include_all_builtin,
        )
        targets = []

        for ctl in glob.glob(os.path.join(self.data_dir, "*.ctl")):
            name = os.path.basename(ctl)
            if not include_all_builtin and name not in selected:
                continue
            targets.append(ctl)

        for generated in generated_txt_files:
            generated_name = os.path.basename(generated)
            source_name = generated_name.replace("_pnl.txt", ".pnl").replace("_xml.txt", ".xml")
            if not include_all_builtin and generated_name not in selected and source_name not in selected:
                continue
            targets.append(generated)

        # Explicit normalized txt selection is always allowed for compatibility.
        for item in selected:
            if not self._is_normalized_txt(item):
                continue
            candidate = os.path.join(self.data_dir, item)
            if os.path.exists(candidate) and candidate not in targets:
                targets.append(candidate)

        if allow_raw_txt:
            raw_txt_paths = glob.glob(os.path.join(self.data_dir, "*.txt"))
            for path in raw_txt_paths:
                name = os.path.basename(path)
                if not self._is_raw_txt(name):
                    continue
                if not include_all_builtin and name not in selected:
                    continue
                if path not in targets:
                    targets.append(path)

        external_direct_targets: List[str] = []
        for item in input_sources or []:
            if not isinstance(item, dict):
                continue
            source_type = str(item.get("type", "") or "").strip().lower()
            source_value = str(item.get("value", "") or "").strip()
            if not source_value:
                continue
            if source_type == "builtin_file":
                continue
            normalized = self._normalize_local_path(source_value)
            if source_type == "file_path":
                if os.path.isfile(normalized):
                    external_direct_targets.append(normalized)
            elif source_type == "folder_path":
                if os.path.isdir(normalized):
                    external_direct_targets.extend(self._scan_folder_targets(normalized, allow_raw_txt=allow_raw_txt))

        external_generated_txt = self._convert_external_targets(external_direct_targets, metrics=metrics)
        for path in external_direct_targets:
            lower = path.lower()
            if lower.endswith(".ctl"):
                targets.append(path)
            elif lower.endswith(".txt"):
                name = os.path.basename(path)
                if self._is_reviewed_txt(name):
                    continue
                if self._is_raw_txt(name) and not allow_raw_txt:
                    continue
                targets.append(path)
        targets.extend(external_generated_txt)

        return sorted(set(targets))
