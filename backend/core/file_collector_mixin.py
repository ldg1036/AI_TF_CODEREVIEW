"""FileCollectorMixin – file listing, conversion, and collection logic extracted from main.py."""

import glob
import os
import tempfile
import threading
import uuid
import logging
from typing import Any, Dict, List, Optional

from core.input_normalization import InputNormalizer

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
                name = os.path.basename(path)
                descriptor = self._build_file_descriptor(name, resolved_name=name)
                files.append(
                    {
                        "name": name,
                        "type": os.path.splitext(path)[1].lstrip("."),
                        "selectable": True,
                        "canonical_file_id": descriptor.get("canonical_file_id", ""),
                        "file_descriptor": descriptor,
                    }
                )

        for path in glob.glob(os.path.join(self.data_dir, "*.txt")):
            name = os.path.basename(path)
            if self._is_reviewed_txt(name):
                continue
            if self._is_raw_txt(name) and not allow_raw_txt:
                continue
            descriptor = self._build_file_descriptor(name, resolved_name=name)
            files.append(
                {
                    "name": name,
                    "type": "txt",
                    "selectable": True,
                    "canonical_file_id": descriptor.get("canonical_file_id", ""),
                    "file_descriptor": descriptor,
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

    @property
    def _normalizer(self):
        return getattr(self, "input_normalizer", None) or InputNormalizer

    @staticmethod
    def _normalize_local_path(path_value: str) -> str:
        return os.path.normpath(os.path.abspath(str(path_value or "").strip()))

    def _build_file_descriptor(
        self,
        requested_name: str,
        *,
        resolved_name: str = "",
        detected_encoding: str = "",
        viewer_source: str = "",
        display_name: str = "",
    ) -> Dict[str, Any]:
        return self._normalizer.build_descriptor(
            requested_name,
            resolved_name=resolved_name,
            detected_encoding=detected_encoding,
            viewer_source=viewer_source,
            display_name=display_name,
        )

    def _read_text_file(self, path: str):
        return self._normalizer.read_text_file(path)

    @classmethod
    def _is_normalized_txt(cls, name):
        return InputNormalizer.is_normalized_txt(name)

    @classmethod
    def _is_reviewed_txt(cls, name):
        return InputNormalizer.is_reviewed_txt(name)

    @classmethod
    def _is_raw_txt(cls, name):
        return InputNormalizer.is_raw_txt(name)

    @classmethod
    def _normalized_name_for_source(cls, name: str) -> str:
        return InputNormalizer.canonical_name_for(name)

    @classmethod
    def _reviewed_name_for_source(cls, name: str) -> str:
        return InputNormalizer.reviewed_name_for(name)

    @classmethod
    def _candidate_cached_filenames(cls, name: str):
        return InputNormalizer.candidate_names_for(name)

    def _viewer_payload(
        self,
        *,
        path: str,
        requested_name: str,
        resolved_name: str,
        viewer_source: str,
        display_name: str,
        resolved_path: str = "",
    ) -> Dict[str, Any]:
        content, detected_encoding = self._read_text_file(path)
        descriptor = self._build_file_descriptor(
            requested_name,
            resolved_name=resolved_name,
            detected_encoding=detected_encoding,
            viewer_source=viewer_source,
            display_name=display_name,
        )
        return {
            "file": display_name,
            "resolved_name": resolved_name,
            "resolved_path": resolved_path or path,
            "source": viewer_source,
            "viewer_source": viewer_source,
            "content": content,
            "detected_encoding": detected_encoding,
            "canonical_file_id": descriptor.get("canonical_file_id", ""),
            "file_descriptor": descriptor,
        }

    def _default_viewer_source(self, resolved_name: str) -> str:
        descriptor = self._build_file_descriptor(resolved_name, resolved_name=resolved_name)
        source_kind = str(descriptor.get("source_kind", "") or "")
        if source_kind in ("converted_pnl", "converted_xml"):
            return "normalized"
        return "source"

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

                content, _detected_encoding = self._read_text_file(source)
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

        target_output_dir = os.path.normpath(str(output_dir or self._last_output_dir or ""))
        if target_output_dir:
            session = self._get_review_session(target_output_dir)
            if session:
                try:
                    _session_output_dir, _session, resolved_cache_key, cached = self._resolve_review_session_and_file(requested, output_dir=target_output_dir)
                    cached_descriptor = cached.get("file_descriptor", {}) if isinstance(cached.get("file_descriptor", {}), dict) else {}
                    display_name = str(
                        cached_descriptor.get("display_name", "")
                        or cached.get("display_name", "")
                        or cached.get("file", "")
                        or basename
                        or requested
                    )
                    source_path = str(cached.get("source_path", "") or "")
                    canonical_path = str(cached.get("canonical_path", "") or source_path or "")
                    viewer_source_path = str(cached.get("viewer_source_path", "") or canonical_path or source_path)
                    resolved_display_name = str(cached_descriptor.get("canonical_name", "") or display_name or basename or requested)
                    reviewed_name = str(
                        cached.get("reviewed_name", "")
                        or cached_descriptor.get("reviewed_name", "")
                        or self._reviewed_name_for_source(resolved_display_name)
                    )
                    if reviewed_name and os.path.isdir(target_output_dir):
                        reviewed_path = os.path.join(target_output_dir, reviewed_name)
                        if os.path.isfile(reviewed_path) and not prefer_source:
                            return self._viewer_payload(
                                path=reviewed_path,
                                requested_name=requested,
                                resolved_name=reviewed_name,
                                viewer_source="reviewed",
                                display_name=display_name,
                                resolved_path=viewer_source_path or reviewed_path,
                            )
                    if viewer_source_path and os.path.isfile(viewer_source_path):
                        resolved_name = os.path.basename(viewer_source_path)
                        return self._viewer_payload(
                            path=viewer_source_path,
                            requested_name=requested,
                            resolved_name=resolved_name,
                            viewer_source=self._default_viewer_source(resolved_name),
                            display_name=display_name,
                            resolved_path=viewer_source_path,
                        )
                    if source_path and os.path.isfile(source_path):
                        resolved_name = os.path.basename(source_path)
                        return self._viewer_payload(
                            path=source_path,
                            requested_name=requested,
                            resolved_name=resolved_name,
                            viewer_source="source",
                            display_name=display_name,
                            resolved_path=source_path,
                        )
                except FileNotFoundError:
                    pass

        normalized_requested = self._normalize_local_path(requested) if os.path.isabs(requested) else ""
        if normalized_requested and os.path.isfile(normalized_requested):
            display_name = self._normalized_name_for_source(os.path.basename(normalized_requested))
            resolved_name = os.path.basename(normalized_requested)
            viewer_path = normalized_requested
            viewer_source = self._default_viewer_source(resolved_name)
            if not prefer_source:
                normalized_name = self._normalized_name_for_source(resolved_name)
                candidate_path = os.path.join(os.path.dirname(normalized_requested), normalized_name)
                if normalized_name != resolved_name and os.path.isfile(candidate_path):
                    viewer_path = candidate_path
                    resolved_name = os.path.basename(candidate_path)
                    viewer_source = "normalized"
            return self._viewer_payload(
                path=viewer_path,
                requested_name=requested,
                resolved_name=resolved_name,
                viewer_source=viewer_source,
                display_name=display_name,
                resolved_path=viewer_path,
            )

        reviewed_name = self._reviewed_name_for_source(basename)
        normalized_name = self._normalized_name_for_source(basename)
        source_path = os.path.join(self.data_dir, basename)
        normalized_path = os.path.join(self.data_dir, normalized_name)
        display_name = normalized_name or basename

        if prefer_source and normalized_name == basename and os.path.isfile(source_path):
            return self._viewer_payload(
                path=source_path,
                requested_name=requested,
                resolved_name=basename,
                viewer_source="source",
                display_name=display_name,
                resolved_path=source_path,
            )

        if reviewed_name and target_output_dir and os.path.isdir(target_output_dir):
            reviewed_path = os.path.join(target_output_dir, reviewed_name)
            if os.path.isfile(reviewed_path) and not prefer_source:
                return self._viewer_payload(
                    path=reviewed_path,
                    requested_name=requested,
                    resolved_name=reviewed_name,
                    viewer_source="reviewed",
                    display_name=display_name,
                    resolved_path=normalized_path if os.path.isfile(normalized_path) else source_path,
                )

        if normalized_name != basename and os.path.isfile(normalized_path):
            return self._viewer_payload(
                path=normalized_path,
                requested_name=requested,
                resolved_name=normalized_name,
                viewer_source="normalized",
                display_name=display_name,
                resolved_path=normalized_path,
            )

        if os.path.isfile(source_path):
            return self._viewer_payload(
                path=source_path,
                requested_name=requested,
                resolved_name=basename,
                viewer_source="source",
                display_name=display_name,
                resolved_path=source_path,
            )

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
