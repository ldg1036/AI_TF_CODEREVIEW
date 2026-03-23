import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple, cast

from core.errors import ReviewerError

logger = logging.getLogger(__name__)


class LiveAIReviewMixin:
    """Live AI review helpers extracted from backend/main.py."""

    def _build_todo_prompt_context(self, code_content: str, context_item: Dict[str, Any]) -> Dict[str, Any]:
        issue_context = context_item.get("issue_context", {}) if isinstance(context_item, dict) else {}
        primary = issue_context.get("primary", {}) if isinstance(issue_context, dict) else {}
        primary_violation = primary if isinstance(primary, dict) else {}
        todo_comment = self.reporter.build_todo_comment(primary_violation)
        snippet = self._build_focus_snippet(
            code_content,
            [primary_violation] if primary_violation else [],
            window_lines=self.ai_todo_prompt_window_lines,
            max_lines=self.ai_todo_prompt_max_lines,
        )
        linked_findings = issue_context.get("linked_findings", []) if isinstance(issue_context, dict) else []
        linked_summary = []
        for item in linked_findings[:4]:
            if not isinstance(item, dict):
                continue
            linked_summary.append(
                {
                    "source": str(item.get("source", "") or ""),
                    "rule_id": str(item.get("rule_id", "") or ""),
                    "line": self._safe_int(item.get("line", 0), 0),
                    "message": str(item.get("message", "") or ""),
                }
            )
        return {
            "todo_comment": todo_comment,
            "snippet": snippet,
            "line": self._safe_int(primary_violation.get("line", 0), 0),
            "object": str(primary_violation.get("object", context_item.get("object", "")) or ""),
            "event": str(primary_violation.get("event", context_item.get("event", "")) or ""),
            "linked_findings": linked_summary,
        }

    def list_ai_models(self) -> Dict[str, Any]:
        try:
            models = self.ai_tool.list_models()
            return {
                "provider": str(self.ai_tool.provider or "ollama"),
                "available": bool(models),
                "models": models,
                "default_model": str(self.ai_tool.model_name or ""),
            }
        except ReviewerError as exc:
            return {
                "provider": str(self.ai_tool.provider or "ollama"),
                "available": False,
                "models": [],
                "default_model": str(self.ai_tool.model_name or ""),
                "error": str(exc),
                "error_code": str(exc.error_code or ""),
            }
        except Exception as exc:
            return {
                "provider": str(self.ai_tool.provider or "ollama"),
                "available": False,
                "models": [],
                "default_model": str(self.ai_tool.model_name or ""),
                "error": str(exc),
            }

    @staticmethod
    def _normalize_issue_text(value: Any) -> str:
        return " ".join(str(value or "").split()).strip().lower()

    @staticmethod
    def _severity_rank(value: Any) -> int:
        normalized = str(value or "").strip().lower()
        if normalized == "critical":
            return 3
        if normalized in ("warning", "warn", "high", "medium", "performance", "style", "information"):
            return 2
        if normalized in ("info", "information", "low"):
            return 1
        return 0

    def _live_ai_parent_context_key(self, context_item: Dict[str, Any]) -> Tuple[str, str, str, int, str]:
        return (
            str(context_item.get("parent_source", "") or ""),
            str(context_item.get("parent_issue_id", "") or ""),
            str(context_item.get("parent_rule_id", "") or ""),
            self._safe_int(context_item.get("parent_line", 0), 0),
            str(context_item.get("parent_file_path", context_item.get("parent_file", "")) or ""),
        )

    def _eligible_live_ai_parent_issue_contexts(self, contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(contexts, list) or not contexts:
            return []
        minimum_rank = self._severity_rank(self.live_ai_min_review_severity)
        eligible: List[Dict[str, Any]] = []
        for context in contexts:
            if not isinstance(context, dict):
                continue
            if self._severity_rank(context.get("severity", "")) < minimum_rank:
                continue
            eligible.append(context)

        def sort_key(item: Dict[str, Any]) -> Tuple[int, int, int, str]:
            linked_findings = cast(List[Dict[str, Any]], item.get("issue_context", {}).get("linked_findings", []))
            return (
                -self._severity_rank(item.get("severity", "")),
                -len(linked_findings),
                self._safe_int(item.get("parent_line", 0), 0),
                str(item.get("parent_issue_id", "") or item.get("parent_rule_id", "") or ""),
            )

        eligible.sort(key=sort_key)
        return eligible

    def _select_live_ai_parent_issue_contexts(self, contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        eligible = self._eligible_live_ai_parent_issue_contexts(contexts)
        return eligible[: self._recommended_live_ai_parent_review_limit(eligible)]

    @staticmethod
    def _rule_family(rule_id: Any) -> str:
        text = str(rule_id or "").strip().upper()
        if not text:
            return ""
        parts = [part for part in text.split("-") if part]
        return parts[0] if parts else text

    def _recommended_live_ai_parent_review_limit(self, eligible: List[Dict[str, Any]]) -> int:
        if not isinstance(eligible, list) or not eligible:
            return 0
        hard_cap = max(1, int(self.live_ai_max_parent_reviews_per_file))
        if hard_cap == 1 or len(eligible) == 1:
            return 1

        critical_count = 0
        hotspot_keys = set()
        rule_families = set()
        for item in eligible:
            if not isinstance(item, dict):
                continue
            if self._severity_rank(item.get("severity", "")) >= 3:
                critical_count += 1
            hotspot_keys.add(
                (
                    str(item.get("object", "") or item.get("parent_file", "") or ""),
                    str(item.get("event", "") or "Global"),
                )
            )
            family = self._rule_family(item.get("parent_rule_id", "") or item.get("rule_id", ""))
            if family:
                rule_families.add(family)

        recommended = 2 if len(eligible) >= 2 else 1
        if len(eligible) >= 3 and (critical_count >= 1 or len(hotspot_keys) >= 2 or len(rule_families) >= 2):
            recommended = 3
        if len(eligible) >= 4 and (critical_count >= 2 or (critical_count >= 1 and len(rule_families) >= 3)):
            recommended = 4
        if len(eligible) >= 5 and critical_count >= 2 and len(rule_families) >= 4:
            recommended = 5
        return min(hard_cap, recommended)

    def _run_live_ai_review_for_context(
        self,
        code_content: str,
        filename: str,
        context_item: Dict[str, Any],
        *,
        ai_with_context: bool,
        context_payload: Any,
        ai_model_name: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], int, Dict[str, Any]]:
        primary = cast(Dict[str, Any], context_item.get("issue_context", {}).get("primary", {}))
        focus_violations = [primary]
        todo_prompt_context = context_item.get("todo_prompt_context", {}) if isinstance(context_item, dict) else {}
        focus_snippet = str((todo_prompt_context or {}).get("snippet", "") or "")
        if not focus_snippet:
            focus_snippet = self._build_focus_snippet(
                code_content,
                focus_violations,
                window_lines=self.ai_todo_prompt_window_lines if self.ai_prompt_mode == "todo_compact" else None,
                max_lines=self.ai_todo_prompt_max_lines if self.ai_prompt_mode == "todo_compact" else None,
            )

        ai_started = self._perf_now()
        with self._live_ai_semaphore:
            review = self.ai_tool.generate_review(
                code_content,
                focus_violations,
                use_context=bool(ai_with_context),
                context_payload=context_payload,
                focus_snippet=focus_snippet,
                issue_context=context_item.get("issue_context", {}),
                todo_prompt_context=todo_prompt_context,
                model_name=ai_model_name,
            )
        elapsed_ms = self._elapsed_ms(ai_started)
        status_meta = self._new_ai_review_status_entry(
            context_item,
            filename=filename,
            status="generated",
            reason="generated",
        )
        if not review:
            status_meta["status"] = "failed"
            status_meta["reason"] = "empty_response"
            return None, elapsed_ms, status_meta
        if isinstance(review, str) and review.startswith("AI live review failed:"):
            status_meta["status"] = "failed"
            status_meta["reason"] = self._classify_ai_review_failure_reason(review)
            status_meta["detail"] = str(review or "")
            return None, elapsed_ms, status_meta
        return (
            {
                "file": str(context_item.get("file", filename) or filename),
                "file_path": str(context_item.get("file_path", context_item.get("file", filename)) or filename),
                "object": str(context_item.get("object", filename) or filename),
                "event": str(context_item.get("event", "Global") or "Global"),
                "review": review,
                "source": "live",
                "status": "Pending",
                "parent_source": str(context_item.get("parent_source", "P1") or "P1"),
                "parent_issue_id": str(context_item.get("parent_issue_id", "") or ""),
                "parent_rule_id": str(context_item.get("parent_rule_id", "") or ""),
                "parent_file": str(context_item.get("parent_file", filename) or filename),
                "parent_file_path": str(context_item.get("parent_file_path", context_item.get("parent_file", filename)) or filename),
                "parent_line": self._safe_int(context_item.get("parent_line", 0), 0),
            },
            elapsed_ms,
            status_meta,
        )

    def _new_ai_review_status_entry(
        self,
        context_item: Dict[str, Any],
        *,
        filename: str,
        status: str,
        reason: str,
        detail: str = "",
        selected_rank: Optional[int] = None,
        selected_cap: Optional[int] = None,
    ) -> Dict[str, Any]:
        selected_rank_value = self._safe_int(
            selected_rank if selected_rank is not None else context_item.get("selected_rank", context_item.get("_selected_rank", 0)),
            0,
        )
        selected_cap_value = self._safe_int(
            selected_cap if selected_cap is not None else context_item.get("selected_cap", context_item.get("_selected_cap", 0)),
            0,
        )
        payload = {
            "status": str(status or "").strip() or "unknown",
            "reason": str(reason or "").strip() or "unknown",
            "detail": str(detail or "").strip(),
            "parent_source": str(context_item.get("parent_source", "P1") or "P1"),
            "parent_issue_id": str(context_item.get("parent_issue_id", "") or ""),
            "parent_rule_id": str(context_item.get("parent_rule_id", "") or ""),
            "parent_file": str(context_item.get("parent_file", filename) or filename),
            "parent_file_path": str(context_item.get("parent_file_path", context_item.get("parent_file", filename)) or filename),
            "parent_line": self._safe_int(context_item.get("parent_line", 0), 0),
            "file": str(context_item.get("file", filename) or filename),
            "file_path": str(context_item.get("file_path", context_item.get("file", filename)) or filename),
            "object": str(context_item.get("object", filename) or filename),
            "event": str(context_item.get("event", "Global") or "Global"),
            "severity": str(context_item.get("severity", "") or ""),
            "message": str(context_item.get("message", "") or ""),
        }
        if selected_rank_value > 0:
            payload["selected_rank"] = selected_rank_value
        if selected_cap_value > 0:
            payload["selected_cap"] = selected_cap_value
        return payload

    @staticmethod
    def _classify_ai_review_failure_reason(review_text: Any) -> str:
        text = str(review_text or "").strip().lower()
        if "timed out" in text or "timeout" in text:
            return "timeout"
        if "invalid ai response payload" in text or "normalize review" in text or "json" in text:
            return "response_parse_failed"
        return "fail_soft_skip"

    @staticmethod
    def _rule_requires_domain_hint(parent_rule_id: Any) -> bool:
        rule = str(parent_rule_id or "").strip().upper()
        return rule in {
            "PERF-SETMULTIVALUE-ADOPT-01",
            "PERF-GETMULTIVALUE-ADOPT-01",
            "PERF-DPSET-BATCH-01",
            "PERF-DPGET-BATCH-01",
        }

    @staticmethod
    def _domain_hint_instruction(parent_rule_id: Any) -> str:
        rule = str(parent_rule_id or "").strip().upper()
        if rule == "PERF-SETMULTIVALUE-ADOPT-01":
            return (
                "반복 setValue 호출은 하나의 setMultiValue 호출로 묶어 제안하세요. "
                "반드시 WinCC OA CONTROL fenced code block을 포함하고 before/after 예시를 보여주세요.\n"
                "setValue(\"obj_auto_sel1\", \"enabled\", false);\n"
                "setValue(\"obj_auto_sel2\", \"enabled\", false);\n"
                "=>\n"
                "setMultiValue(\"obj_auto_sel1\", \"enabled\", false,\n"
                "              \"obj_auto_sel2\", \"enabled\", false);"
            )
        if rule == "PERF-GETMULTIVALUE-ADOPT-01":
            return (
                "반복 getValue 호출은 하나의 getMultiValue 호출로 묶어 제안하세요. "
                "반드시 WinCC OA CONTROL fenced code block을 포함하고 before/after 예시를 보여주세요.\n"
                "getValue(\"obj_auto_sel1\", \"enabled\", bSel1);\n"
                "getValue(\"obj_auto_sel2\", \"enabled\", bSel2);\n"
                "=>\n"
                "getMultiValue(\"obj_auto_sel1\", \"enabled\", bSel1,\n"
                "              \"obj_auto_sel2\", \"enabled\", bSel2);"
            )
        if rule == "PERF-DPSET-BATCH-01":
            return (
                "반복 dpSet 호출은 하나의 grouped dpSet 호출로 묶어 제안하세요. "
                "dpSetWait 같은 다른 함수로 바꾸지 말고, 여러 DPE/value 쌍을 한 번의 dpSet 호출에 넣는 "
                "WinCC OA CONTROL 예시를 보여주세요.\n"
                "dpSet(\"System1:Obj1.enabled\", false);\n"
                "dpSet(\"System1:Obj2.enabled\", false);\n"
                "=>\n"
                "dpSet(\"System1:Obj1.enabled\", false,\n"
                "      \"System1:Obj2.enabled\", false);"
            )
        if rule == "PERF-DPGET-BATCH-01":
            return (
                "반복 dpGet 호출은 하나의 grouped dpGet 호출로 묶어 제안하세요. "
                "dpGetAll 같은 다른 함수로 바꾸지 말고, 여러 DPE/target 쌍을 한 번의 dpGet 호출에 넣는 "
                "WinCC OA CONTROL 예시를 보여주세요.\n"
                "dpGet(\"System1:Obj1.enabled\", bObj1);\n"
                "dpGet(\"System1:Obj2.enabled\", bObj2);\n"
                "=>\n"
                "dpGet(\"System1:Obj1.enabled\", bObj1,\n"
                "      \"System1:Obj2.enabled\", bObj2);"
            )
        return ""

    @staticmethod
    def _extract_review_code_blocks(review_text: Any) -> List[str]:
        text = str(review_text or "")
        if not text:
            return []
        blocks = re.findall(r"```(?:[\w#+.-]+)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
        return [str(block or "").strip() for block in blocks if str(block or "").strip()]

    @staticmethod
    def _has_grouped_dp_call(block_text: Any, function_name: str) -> bool:
        block = str(block_text or "")
        func = str(function_name or "").strip()
        if not block or not func:
            return False
        pattern = rf"{re.escape(func)}\s*\(([\s\S]*?)\);"
        for match in re.finditer(pattern, block, flags=re.IGNORECASE):
            args = str(match.group(1) or "")
            if args.count(",") >= 3:
                return True
        return False

    @staticmethod
    def _review_has_multi_call_example(parent_rule_id: Any, review_text: Any) -> bool:
        text = str(review_text or "")
        rule = str(parent_rule_id or "").strip().upper()
        if not text or not rule:
            return False
        blocks = LiveAIReviewMixin._extract_review_code_blocks(text)
        lowered = [block.lower() for block in blocks]
        if rule == "PERF-SETMULTIVALUE-ADOPT-01":
            return any("setmultivalue(" in block for block in lowered)
        if rule == "PERF-GETMULTIVALUE-ADOPT-01":
            return any("getmultivalue(" in block for block in lowered)
        if rule == "PERF-DPSET-BATCH-01":
            return any(LiveAIReviewMixin._has_grouped_dp_call(block, "dpSet") for block in blocks)
        if rule == "PERF-DPGET-BATCH-01":
            return any(LiveAIReviewMixin._has_grouped_dp_call(block, "dpGet") for block in blocks)
        return True

    def _review_has_domain_hint(self, parent_rule_id: Any, review_text: Any) -> bool:
        text = str(review_text or "").strip().lower()
        rule = str(parent_rule_id or "").strip().upper()
        if not text or not rule:
            return False
        if rule == "PERF-SETMULTIVALUE-ADOPT-01":
            return ("setmultivalue" in text) and self._review_has_multi_call_example(rule, review_text)
        if rule == "PERF-GETMULTIVALUE-ADOPT-01":
            return ("getmultivalue" in text) and self._review_has_multi_call_example(rule, review_text)
        if rule == "PERF-DPSET-BATCH-01":
            return ("dpset" in text) and self._review_has_multi_call_example(rule, review_text)
        if rule == "PERF-DPGET-BATCH-01":
            return ("dpget" in text) and self._review_has_multi_call_example(rule, review_text)
        return True

    @staticmethod
    def _domain_hint_instruction(parent_rule_id: Any) -> str:
        rule = str(parent_rule_id or "").strip().upper()
        shared = (
            "반드시 focused snippet에 이미 나온 식별자, DP 이름, 변수명, literal 값을 그대로 사용하세요. "
            "obj_auto_sel1, obj_auto_sel2, System1:Obj1 같은 placeholder를 새로 만들지 마세요. "
            "before/after 설명이나 '=>' 마커를 출력하지 말고, 최종 수정 코드만 WinCC OA CONTROL fenced code block으로 제시하세요."
        )
        if rule == "PERF-SETMULTIVALUE-ADOPT-01":
            return (
                f"{shared} "
                "반복된 setValue 호출이 보이면 snippet에 나온 동일한 호출들을 하나의 setMultiValue 호출로 묶어 제시하세요."
            )
        if rule == "PERF-GETMULTIVALUE-ADOPT-01":
            return (
                f"{shared} "
                "반복된 getValue 호출이 보이면 snippet에 나온 동일한 호출들을 하나의 getMultiValue 호출로 묶어 제시하세요."
            )
        if rule == "PERF-DPSET-BATCH-01":
            return (
                f"{shared} "
                "반복된 dpSet 호출이 보이면 dpSetWait 같은 다른 API로 바꾸지 말고, snippet에 나온 동일한 DPE/value 쌍을 하나의 grouped dpSet 호출로 묶어 제시하세요."
            )
        if rule == "PERF-DPGET-BATCH-01":
            return (
                f"{shared} "
                "반복된 dpGet 호출이 보이면 dpGetAll 같은 다른 API로 바꾸지 말고, snippet에 나온 동일한 DPE/target 쌍을 하나의 grouped dpGet 호출로 묶어 제시하세요."
            )
        return ""

    @staticmethod
    def _review_has_example_artifacts(review_text: Any) -> bool:
        text = str(review_text or "")
        if not text:
            return False
        if re.search(r"(^|\n)\s*=>\s*", text):
            return True
        placeholder_patterns = (
            r"\bobj_auto_sel\d+\b",
            r"\bSystem1:Obj\d+(?:\.[A-Za-z_][\w]*)?\b",
            r"\bbSel\d+\b",
        )
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in placeholder_patterns)

    def _resolve_violation_target_path(self, violation: Dict[str, Any]) -> str:
        file_path = str((violation or {}).get("file_path", "") or "").strip()
        file_name = str((violation or {}).get("file", "") or "").strip()
        candidates: List[str] = []
        if file_path:
            candidates.append(file_path)
        if file_name:
            candidates.append(file_name)
            candidates.append(os.path.join(self.data_dir, os.path.basename(file_name)))
        normalized = [os.path.normpath(candidate) for candidate in candidates if candidate]
        for candidate in normalized:
            if os.path.isfile(candidate):
                return candidate
        raise FileNotFoundError(f"Input file not found for violation: {file_path or file_name or '(unknown)'}")

    def _build_single_violation_context(self, target_path: str, violation: Dict[str, Any]) -> Dict[str, Any]:
        source = str((violation or {}).get("source", (violation or {}).get("priority_origin", "P1")) or "P1").strip().upper()
        if source not in ("P1", "P2"):
            source = "P1"
        basename = os.path.basename(str((violation or {}).get("file", "") or target_path))
        parent_issue_id = str((violation or {}).get("issue_id", "") or "").strip()
        parent_rule_id = str((violation or {}).get("rule_id", "") or "").strip()
        parent_line = self._safe_int((violation or {}).get("line", 0), 0)
        message = str((violation or {}).get("message", "") or "").strip()
        object_name = str((violation or {}).get("object", "") or basename).strip() or basename
        event_name = str((violation or {}).get("event", "Global") or "Global").strip() or "Global"
        severity = str((violation or {}).get("severity", "") or "").strip()
        if not parent_issue_id:
            parent_issue_id = f"{source}-{parent_rule_id or 'UNKNOWN'}-{self._sha256_text(f'{basename}:{parent_line}:{message}')[:10]}"
        normalized_target = os.path.normpath(str(target_path))
        return {
            "parent_source": source,
            "parent_issue_id": parent_issue_id,
            "parent_rule_id": parent_rule_id,
            "parent_file": basename,
            "parent_file_path": normalized_target,
            "parent_line": parent_line,
            "file": basename,
            "file_path": normalized_target,
            "object": object_name,
            "event": event_name,
            "severity": severity,
            "message": message,
            "issue_context": {
                "primary": {
                    "source": source,
                    "issue_id": parent_issue_id,
                    "rule_id": parent_rule_id,
                    "line": parent_line,
                    "file": basename,
                    "file_path": normalized_target,
                    "object": object_name,
                    "event": event_name,
                    "severity": severity,
                    "message": message,
                },
                "linked_findings": [],
            },
        }

    def generate_ai_review_for_violation(
        self,
        violation: Dict[str, Any],
        *,
        enable_live_ai: Optional[bool] = None,
        ai_model_name: Optional[str] = None,
        ai_with_context: bool = False,
        output_dir: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not isinstance(violation, dict):
            raise ValueError("violation must be an object")
        target_path = self._resolve_violation_target_path(violation)
        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            code_content = f.read()
        context_item = self._build_single_violation_context(target_path, violation)
        context_item["todo_prompt_context"] = self._build_todo_prompt_context(code_content, context_item)
        use_live_ai = self._resolve_toggle(self.live_ai_enabled_default, enable_live_ai)

        review_item: Optional[Dict[str, Any]] = None
        status_meta: Dict[str, Any]
        domain_warning = ""

        if use_live_ai:
            review_item, _elapsed_ms, status_meta = self._run_live_ai_review_for_context(
                code_content,
                os.path.basename(target_path),
                context_item,
                ai_with_context=bool(ai_with_context),
                context_payload=None,
                ai_model_name=ai_model_name,
            )
            parent_rule_id = context_item.get("parent_rule_id", "")
            needs_hint = self._rule_requires_domain_hint(parent_rule_id)
            has_hint = self._review_has_domain_hint(parent_rule_id, (review_item or {}).get("review", ""))
            has_artifacts = self._review_has_example_artifacts((review_item or {}).get("review", ""))
            if review_item and needs_hint and (not has_hint or has_artifacts):
                reinforced = dict(context_item)
                reinforced_todo = dict((context_item.get("todo_prompt_context") or {}))
                hint_text = self._domain_hint_instruction(parent_rule_id)
                todo_comment = str(reinforced_todo.get("todo_comment", "") or "").strip()
                snippet = str(reinforced_todo.get("snippet", "") or "").strip()
                if hint_text:
                    if hint_text not in todo_comment:
                        reinforced_todo["todo_comment"] = (f"{todo_comment}\n{hint_text}" if todo_comment else hint_text).strip()
                    if hint_text not in snippet:
                        reinforced_todo["snippet"] = (f"{snippet}\n// Domain hint: {hint_text}" if snippet else f"// Domain hint: {hint_text}").strip()
                reinforced["todo_prompt_context"] = reinforced_todo
                retried_review_item, _elapsed_ms_retry, retried_status_meta = self._run_live_ai_review_for_context(
                    code_content,
                    os.path.basename(target_path),
                    reinforced,
                    ai_with_context=bool(ai_with_context),
                    context_payload=None,
                    ai_model_name=ai_model_name,
                )
                if retried_review_item:
                    review_item = retried_review_item
                    status_meta = retried_status_meta
                if (
                    not self._review_has_domain_hint(parent_rule_id, (review_item or {}).get("review", ""))
                    or self._review_has_example_artifacts((review_item or {}).get("review", ""))
                ):
                    domain_warning = (
                        "도메인 가이드 검증 경고: 멀티 API 변환 키워드 또는 묶음 처리 코드 예시(setMultiValue/getMultiValue, dpSetWait/dpGetAll)가 부족합니다."
                    )
            if domain_warning and ("dpSetWait/dpGetAll" in str(domain_warning) or "setMultiValue/getMultiValue" in str(domain_warning)):
                domain_warning = (
                    "도메인 가이드 검증 경고: 멀티 API 변환 키워드 또는 묶음 처리 코드 예시(setMultiValue/getMultiValue, grouped dpSet/dpGet)가 부족합니다."
                )
            if domain_warning:
                status_meta["detail"] = (
                    f"{status_meta.get('detail', '').strip()} {domain_warning}".strip()
                    if str(status_meta.get("detail", "")).strip()
                    else domain_warning
                )
        else:
            primary = cast(Dict[str, Any], context_item.get("issue_context", {}).get("primary", {}))
            review = self.ai_tool.get_mock_review(
                code_content,
                [primary],
                issue_context=context_item.get("issue_context", {}),
                todo_prompt_context=context_item.get("todo_prompt_context", {}),
            )
            status_meta = self._new_ai_review_status_entry(
                context_item,
                filename=os.path.basename(target_path),
                status="generated" if review else "failed",
                reason="mock_generated" if review else "empty_response",
            )
            if review:
                review_item = {
                    "file": str(context_item.get("file", os.path.basename(target_path)) or os.path.basename(target_path)),
                    "file_path": str(context_item.get("file_path", target_path) or target_path),
                    "object": str(context_item.get("object", os.path.basename(target_path)) or os.path.basename(target_path)),
                    "event": str(context_item.get("event", "Global") or "Global"),
                    "review": review,
                    "source": "mock",
                    "status": "Pending",
                    "parent_source": str(context_item.get("parent_source", "P1") or "P1"),
                    "parent_issue_id": str(context_item.get("parent_issue_id", "") or ""),
                    "parent_rule_id": str(context_item.get("parent_rule_id", "") or ""),
                    "parent_file": str(context_item.get("parent_file", os.path.basename(target_path)) or os.path.basename(target_path)),
                    "parent_file_path": str(context_item.get("parent_file_path", target_path) or target_path),
                    "parent_line": self._safe_int(context_item.get("parent_line", 0), 0),
                }

        persisted = False
        session_output_dir = os.path.normpath(str(output_dir or "").strip()) if str(output_dir or "").strip() else ""
        if session_output_dir and (review_item or status_meta):
            persisted = self._persist_generated_ai_review(
                target_output_dir=session_output_dir,
                violation=violation,
                review_item=review_item,
                status_item=status_meta,
            )

        review_source = str((review_item or {}).get("source", "") or "").strip().lower()
        review_text = str((review_item or {}).get("review", "") or "").strip()
        status_value = str((status_meta or {}).get("status", "generated" if review_item else "failed") or "").strip() or ("generated" if review_item else "failed")
        status_reason = str((status_meta or {}).get("reason", "") or "").strip()
        status_reason_text = str((status_meta or {}).get("detail", "") or "").strip()

        result = {
            "request_id": str(request_id or uuid.uuid4().hex),
            "available": bool(review_item),
            "message": "P3 review generated" if review_item else str(status_meta.get("detail", "") or "P3 review unavailable"),
            "review_item": review_item,
            "status_item": status_meta,
            "status": status_value,
            "status_reason": status_reason,
            "status_reason_text": status_reason_text,
            "review_source": review_source,
            "review_text_present": bool(review_text),
            "review_substantive": bool(review_text),
            "mock_review": review_source == "mock",
        }
        if session_output_dir:
            result["session_id"] = session_output_dir
            result["output_dir"] = session_output_dir
            result["cached_session_updated"] = bool(persisted)
        return result

    @staticmethod
    def _generated_ai_review_key(item: Dict[str, Any]) -> Tuple[str, str, str, str]:
        if not isinstance(item, dict):
            return ("", "", "", "")
        return (
            str(item.get("parent_issue_id", "") or "").strip(),
            str(item.get("object", "") or "").strip(),
            str(item.get("event", "Global") or "Global").strip(),
            str(item.get("review", "") or "").strip(),
        )

    @staticmethod
    def _generated_ai_status_key(item: Dict[str, Any]) -> Tuple[str, str, str, str]:
        if not isinstance(item, dict):
            return ("", "", "", "")
        return (
            str(item.get("parent_issue_id", "") or "").strip(),
            str(item.get("status", "") or "").strip(),
            str(item.get("reason", "") or "").strip(),
            str(item.get("detail", "") or "").strip(),
        )

    def _persist_generated_ai_review(
        self,
        *,
        target_output_dir: str,
        violation: Dict[str, Any],
        review_item: Optional[Dict[str, Any]],
        status_item: Optional[Dict[str, Any]],
    ) -> bool:
        file_hint = str((violation or {}).get("file_path", "") or (violation or {}).get("file", "") or "").strip()
        if not file_hint:
            return False
        try:
            _session_output_dir, session, resolved_cache_key, cached = self._resolve_review_session_and_file(
                file_name=file_hint,
                output_dir=target_output_dir,
            )
        except Exception:
            return False

        report_data = cached.get("report_data")
        if not isinstance(report_data, dict):
            return False

        file_lock = self._get_session_file_lock(session, resolved_cache_key)
        with file_lock:
            changed = False

            if isinstance(review_item, dict):
                ai_reviews = report_data.setdefault("ai_reviews", [])
                if isinstance(ai_reviews, list):
                    target_key = self._generated_ai_review_key(review_item)
                    replace_idx = -1
                    for idx, item in enumerate(ai_reviews):
                        if self._generated_ai_review_key(item if isinstance(item, dict) else {}) == target_key:
                            replace_idx = idx
                            break
                    if replace_idx >= 0:
                        ai_reviews[replace_idx] = json.loads(json.dumps(review_item, ensure_ascii=False))
                    else:
                        ai_reviews.append(json.loads(json.dumps(review_item, ensure_ascii=False)))
                    changed = True

            if isinstance(status_item, dict):
                ai_statuses = report_data.setdefault("ai_review_statuses", [])
                if isinstance(ai_statuses, list):
                    target_key = self._generated_ai_status_key(status_item)
                    replace_idx = -1
                    for idx, item in enumerate(ai_statuses):
                        if self._generated_ai_status_key(item if isinstance(item, dict) else {}) == target_key:
                            replace_idx = idx
                            break
                    if replace_idx >= 0:
                        ai_statuses[replace_idx] = json.loads(json.dumps(status_item, ensure_ascii=False))
                    else:
                        ai_statuses.append(json.loads(json.dumps(status_item, ensure_ascii=False)))
                    changed = True

            if changed:
                cached["updated_at"] = self._iso_now()
                self._touch_review_session(session)
            return changed

    def _build_parent_issue_contexts(
        self,
        filename: str,
        source_path: str,
        internal_violations: List[Dict[str, Any]],
        global_violations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        contexts: List[Dict[str, Any]] = []

        for group in internal_violations or []:
            if not isinstance(group, dict):
                continue
            object_name = str(group.get("object", filename) or filename)
            event_name = str(group.get("event", "Global") or "Global")
            for violation in group.get("violations", []) or []:
                if not isinstance(violation, dict):
                    continue
                issue_id = str(violation.get("issue_id", "") or "").strip()
                rule_id = str(violation.get("rule_id", "") or "").strip()
                line_no = self._safe_int(violation.get("line", 0), 0)
                message = str(violation.get("message", "") or "").strip()
                contexts.append(
                    {
                        "parent_source": "P1",
                        "parent_issue_id": issue_id,
                        "parent_rule_id": rule_id,
                        "parent_file": filename,
                        "parent_file_path": source_path,
                        "parent_line": line_no,
                        "file": filename,
                        "file_path": source_path,
                        "object": object_name,
                        "event": event_name,
                        "severity": str(violation.get("severity", "") or ""),
                        "message": message,
                        "issue_context": {
                            "primary": {
                                "source": "P1",
                                "issue_id": issue_id,
                                "rule_id": rule_id,
                                "line": line_no,
                                "file": filename,
                                "file_path": source_path,
                                "object": object_name,
                                "event": event_name,
                                "severity": str(violation.get("severity", "") or ""),
                                "message": message,
                            },
                            "linked_findings": [],
                        },
                    }
                )

        matched_p2_indexes = set()
        for idx, violation in enumerate(global_violations or []):
            if not isinstance(violation, dict):
                continue
            file_name = os.path.basename(str(violation.get("file", "") or filename)) or filename
            file_path = str(violation.get("file_path", "") or violation.get("file", "") or source_path)
            line_no = self._safe_int(violation.get("line", 0), 0)
            rule_id = str(violation.get("rule_id", "") or "").strip()
            message = str(violation.get("message", "") or "").strip()
            target_issue_id = str(violation.get("issue_id", "") or "").strip()
            normalized_message = self._normalize_issue_text(message)

            best_context = None
            best_score = -1
            for context in contexts:
                primary = context.get("issue_context", {}).get("primary", {})
                score = 0
                if os.path.basename(str(primary.get("file", "") or filename)) == file_name:
                    score += 4
                if target_issue_id and target_issue_id == str(primary.get("issue_id", "") or ""):
                    score += 10
                primary_line = self._safe_int(primary.get("line", 0), 0)
                if line_no > 0 and primary_line > 0:
                    delta = abs(line_no - primary_line)
                    if delta == 0:
                        score += 5
                    elif delta <= 3:
                        score += 4
                    elif delta <= 10:
                        score += 3
                    elif delta <= 25:
                        score += 1
                primary_rule = str(primary.get("rule_id", "") or "").strip()
                if rule_id and primary_rule:
                    if rule_id == primary_rule:
                        score += 4
                    elif rule_id.split("-", 1)[0] == primary_rule.split("-", 1)[0]:
                        score += 2
                primary_message = self._normalize_issue_text(primary.get("message", ""))
                if normalized_message and primary_message:
                    if normalized_message == primary_message:
                        score += 3
                    elif normalized_message in primary_message or primary_message in normalized_message:
                        score += 1
                if score > best_score:
                    best_score = score
                    best_context = context

            if best_context and best_score >= 6:
                linked = {
                    "source": "P2",
                    "issue_id": target_issue_id,
                    "rule_id": rule_id,
                    "line": line_no,
                    "file": file_name,
                    "file_path": file_path,
                    "object": str(violation.get("object", file_name) or file_name),
                    "event": str(violation.get("event", "Global") or "Global"),
                    "severity": str(violation.get("severity", violation.get("type", "")) or ""),
                    "message": message,
                }
                cast(Dict[str, Any], best_context["issue_context"]).setdefault("linked_findings", []).append(linked)
                matched_p2_indexes.add(idx)

        for idx, violation in enumerate(global_violations or []):
            if idx in matched_p2_indexes or not isinstance(violation, dict):
                continue
            file_name = os.path.basename(str(violation.get("file", "") or filename)) or filename
            file_path = str(violation.get("file_path", "") or violation.get("file", "") or source_path)
            rule_id = str(violation.get("rule_id", "") or "").strip()
            line_no = self._safe_int(violation.get("line", 0), 0)
            issue_id = str(violation.get("issue_id", "") or f"P2::{file_name}:{rule_id}:{line_no}") or f"P2::{file_name}:{rule_id}:{line_no}"
            message = str(violation.get("message", "") or "").strip()
            object_name = str(violation.get("object", file_name) or file_name)
            event_name = str(violation.get("event", "Global") or "Global")
            contexts.append(
                {
                    "parent_source": "P2",
                    "parent_issue_id": issue_id,
                    "parent_rule_id": rule_id,
                    "parent_file": file_name,
                    "parent_file_path": file_path,
                    "parent_line": line_no,
                    "file": file_name,
                    "file_path": file_path,
                    "object": object_name,
                    "event": event_name,
                    "severity": str(violation.get("severity", violation.get("type", "")) or ""),
                    "message": message,
                    "issue_context": {
                        "primary": {
                            "source": "P2",
                            "issue_id": issue_id,
                            "rule_id": rule_id,
                            "line": line_no,
                            "file": file_name,
                            "file_path": file_path,
                            "object": object_name,
                            "event": event_name,
                            "severity": str(violation.get("severity", violation.get("type", "")) or ""),
                            "message": message,
                        },
                        "linked_findings": [],
                    },
                }
            )
        return contexts
