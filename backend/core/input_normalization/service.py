import os
import re
from typing import Any, Dict, List, Tuple


class InputNormalizer:
    TEXT_DECODE_ORDER = ("utf-8-sig", "utf-8", "cp949", "euc-kr")
    REVIEWED_SUFFIX_RE = re.compile(r"_REVIEWED\.txt$", re.IGNORECASE)
    NORMALIZED_PNL_RE = re.compile(r"_pnl\.txt$", re.IGNORECASE)
    NORMALIZED_XML_RE = re.compile(r"_xml\.txt$", re.IGNORECASE)

    @staticmethod
    def basename(value: Any) -> str:
        return os.path.basename(str(value or "").strip())

    @classmethod
    def is_reviewed_txt(cls, name: Any) -> bool:
        return bool(cls.REVIEWED_SUFFIX_RE.search(cls.basename(name)))

    @classmethod
    def strip_reviewed_suffix(cls, name: Any) -> str:
        base = cls.basename(name)
        if not base:
            return ""
        if cls.is_reviewed_txt(base):
            return cls.REVIEWED_SUFFIX_RE.sub(".txt", base)
        return base

    @classmethod
    def is_normalized_txt(cls, name: Any) -> bool:
        base = cls.strip_reviewed_suffix(name)
        lower = base.lower()
        return lower.endswith("_pnl.txt") or lower.endswith("_xml.txt")

    @classmethod
    def is_raw_txt(cls, name: Any) -> bool:
        base = cls.basename(name)
        lower = base.lower()
        return lower.endswith(".txt") and not cls.is_reviewed_txt(base) and not cls.is_normalized_txt(base)

    @classmethod
    def canonical_name_for(cls, name: Any) -> str:
        base = cls.strip_reviewed_suffix(name)
        lower = base.lower()
        if lower.endswith(".pnl"):
            return base[:-4] + "_pnl.txt"
        if lower.endswith(".xml"):
            return base[:-4] + "_xml.txt"
        return base

    @classmethod
    def source_name_for(cls, name: Any) -> str:
        base = cls.strip_reviewed_suffix(name)
        lower = base.lower()
        if lower.endswith("_pnl.txt"):
            return base[:-8] + ".pnl"
        if lower.endswith("_xml.txt"):
            return base[:-8] + ".xml"
        return base

    @classmethod
    def reviewed_name_for(cls, name: Any) -> str:
        canonical = cls.canonical_name_for(name)
        lower = canonical.lower()
        if lower.endswith(".txt") or lower.endswith(".ctl"):
            return canonical[:-4] + "_REVIEWED.txt"
        return ""

    @classmethod
    def source_kind_for(cls, name: Any) -> str:
        base = cls.basename(name)
        lower = base.lower()
        if cls.is_reviewed_txt(base):
            reviewed_base = cls.strip_reviewed_suffix(base)
            return cls.source_kind_for(reviewed_base)
        if lower.endswith(".ctl"):
            return "ctl"
        if lower.endswith(".pnl") or lower.endswith("_pnl.txt"):
            return "converted_pnl"
        if lower.endswith(".xml") or lower.endswith("_xml.txt"):
            return "converted_xml"
        if lower.endswith(".txt"):
            return "raw_txt" if cls.is_raw_txt(base) else "normalized_txt"
        return "unknown"

    @classmethod
    def canonical_file_id_for(cls, name: Any) -> str:
        return cls.canonical_name_for(name)

    @classmethod
    def candidate_names_for(cls, name: Any) -> List[str]:
        base = cls.basename(name)
        if not base:
            return []
        raw = cls.strip_reviewed_suffix(base)
        canonical = cls.canonical_name_for(raw)
        source = cls.source_name_for(raw)
        reviewed = cls.reviewed_name_for(raw)
        candidates: List[str] = []
        for value in (base, raw, canonical, source, reviewed):
            text = cls.basename(value)
            if text and text not in candidates:
                candidates.append(text)
        return candidates

    @classmethod
    def build_descriptor(
        cls,
        requested_name: Any,
        *,
        resolved_name: Any = "",
        detected_encoding: str = "",
        viewer_source: str = "",
        display_name: str = "",
    ) -> Dict[str, Any]:
        requested_base = cls.basename(requested_name)
        resolved_base = cls.basename(resolved_name) or requested_base
        canonical_name = cls.canonical_name_for(resolved_base)
        source_name = cls.source_name_for(resolved_base)
        reviewed_name = cls.reviewed_name_for(resolved_base)
        return {
            "requested_name": requested_base or resolved_base,
            "canonical_name": canonical_name,
            "canonical_file_id": cls.canonical_file_id_for(resolved_base),
            "source_kind": cls.source_kind_for(resolved_base),
            "display_name": str(display_name or canonical_name or requested_base or resolved_base),
            "detected_encoding": str(detected_encoding or ""),
            "viewer_source": str(viewer_source or ""),
            "source_name": source_name,
            "reviewed_name": reviewed_name,
        }

    @classmethod
    def read_text_file(cls, path: str) -> Tuple[str, str]:
        with open(path, "rb") as handle:
            data = handle.read()
        for encoding in cls.TEXT_DECODE_ORDER:
            try:
                return data.decode(encoding), encoding
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace"), "utf-8-replace"
