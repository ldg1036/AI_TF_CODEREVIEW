import json
import os
import re
import socket
import urllib.error
import urllib.request
from typing import Dict, List, Optional
from urllib.parse import urlparse, urlunparse

from core.errors import ReviewerError, ReviewerResponseError, ReviewerTimeoutError, ReviewerTransportError


class LLMReviewer:
    """Live/mock AI reviewer (Ollama first, fail-soft)."""

    @staticmethod
    def _safe_int(value, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def __init__(self, ai_config: Optional[Dict] = None, base_dir: Optional[str] = None):
        cfg = ai_config if isinstance(ai_config, dict) else {}
        self.base_dir = base_dir or os.getcwd()

        self.provider = str(cfg.get("provider", "ollama") or "ollama").lower()
        self.model_name = str(cfg.get("model_name", "qwen2.5-coder:3b"))
        self.ollama_url = str(cfg.get("ollama_url", "http://localhost:11434/api/generate"))

        # Keep backward compatibility with existing key `timeout`.
        self.timeout_sec = self._safe_int(cfg.get("timeout_sec", cfg.get("timeout", 30)) or 30, 30)
        self.fail_soft = bool(cfg.get("fail_soft", True))
        self.enabled_default = bool(cfg.get("enabled_default", False))

        self.options = cfg.get("options", {}) if isinstance(cfg.get("options"), dict) else {}
        self.system_prompt = self._load_system_prompt(cfg.get("system_prompt", ""))
        prompt_mode = str(cfg.get("prompt_mode", "todo_compact") or "todo_compact").strip().lower()
        self.prompt_mode = prompt_mode if prompt_mode in ("todo_compact", "issue_context") else "todo_compact"

    def _load_system_prompt(self, prompt_path: str) -> str:
        if not prompt_path:
            return ""
        candidate = prompt_path
        if not os.path.isabs(candidate):
            candidate = os.path.join(self.base_dir, candidate)
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""

    def _post_json(self, url: str, payload: Dict) -> Dict:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                data = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise ReviewerTransportError(
                f"AI request failed with HTTP {getattr(exc, 'code', 'unknown')}",
                details={"url": url, "status": getattr(exc, "code", None)},
            ) from exc
        except urllib.error.URLError as exc:
            if self._is_timeout_error(exc):
                raise ReviewerTimeoutError(f"AI request timed out after {self.timeout_sec}s", details={"url": url}) from exc
            raise ReviewerTransportError(f"AI request failed: {exc}", details={"url": url}) from exc
        except TimeoutError as exc:
            raise ReviewerTimeoutError(f"AI request timed out after {self.timeout_sec}s", details={"url": url}) from exc
        except OSError as exc:
            if self._is_timeout_error(exc):
                raise ReviewerTimeoutError(f"AI request timed out after {self.timeout_sec}s", details={"url": url}) from exc
            raise ReviewerTransportError(f"AI request failed: {exc}", details={"url": url}) from exc
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ReviewerResponseError("Invalid AI response payload", details={"url": url}) from exc
        if not isinstance(parsed, dict):
            raise ReviewerResponseError("Invalid AI response payload", details={"url": url})
        return parsed

    def _get_json(self, url: str) -> Dict:
        req = urllib.request.Request(url=url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                data = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise ReviewerTransportError(
                f"AI request failed with HTTP {getattr(exc, 'code', 'unknown')}",
                details={"url": url, "status": getattr(exc, "code", None)},
            ) from exc
        except urllib.error.URLError as exc:
            if self._is_timeout_error(exc):
                raise ReviewerTimeoutError(f"AI request timed out after {self.timeout_sec}s", details={"url": url}) from exc
            raise ReviewerTransportError(f"AI request failed: {exc}", details={"url": url}) from exc
        except TimeoutError as exc:
            raise ReviewerTimeoutError(f"AI request timed out after {self.timeout_sec}s", details={"url": url}) from exc
        except OSError as exc:
            if self._is_timeout_error(exc):
                raise ReviewerTimeoutError(f"AI request timed out after {self.timeout_sec}s", details={"url": url}) from exc
            raise ReviewerTransportError(f"AI request failed: {exc}", details={"url": url}) from exc
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ReviewerResponseError("Invalid AI response payload", details={"url": url}) from exc
        if not isinstance(parsed, dict):
            raise ReviewerResponseError("Invalid AI response payload", details={"url": url})
        return parsed

    @staticmethod
    def _is_timeout_error(exc: BaseException) -> bool:
        if isinstance(exc, (TimeoutError, socket.timeout)):
            return True
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return True
        text = str(reason if reason is not None else exc).strip().lower()
        return "timed out" in text or "timeout" in text

    def _ollama_tags_url(self) -> str:
        parsed = urlparse(self.ollama_url)
        path = parsed.path or "/api/generate"
        if path.endswith("/generate"):
            path = path[: -len("/generate")] + "/tags"
        else:
            path = "/api/tags"
        return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))

    @staticmethod
    def _trim_text(value: str, max_len: int) -> str:
        text = str(value or "")
        return text if len(text) <= max_len else text[: max_len - 3] + "..."

    def _build_context_line(self, context_payload: Optional[Dict]) -> str:
        if not isinstance(context_payload, dict):
            return "Context: N/A"
        if not context_payload.get("enabled", False):
            return "Context: N/A"

        project = context_payload.get("project", {})
        if not isinstance(project, dict):
            project = {}
        drivers = context_payload.get("drivers", [])
        if not isinstance(drivers, list):
            drivers = []

        project_name = project.get("projectName") or project.get("name") or "unknown"
        site = project.get("site") or project.get("plant") or "-"
        env = project.get("environment") or project.get("env") or "-"
        driver_names = []
        for item in drivers[:20]:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("id") or item.get("driver")
            if name:
                driver_names.append(str(name))
        driver_text = ", ".join(driver_names[:10]) if driver_names else "none"
        return (
            "Context: "
            f"project={self._trim_text(project_name, 60)}, "
            f"site={self._trim_text(site, 40)}, "
            f"env={self._trim_text(env, 20)}, "
            f"drivers={self._trim_text(driver_text, 220)}"
        )

    def _build_prompt(
        self,
        code: str,
        violations: List[Dict],
        use_context: bool = False,
        context_payload: Optional[Dict] = None,
        focus_snippet: str = "",
        issue_context: Optional[Dict] = None,
        todo_prompt_context: Optional[Dict] = None,
    ) -> Optional[str]:
        context_line = "Context: N/A"
        if use_context:
            context_line = self._build_context_line(context_payload=context_payload)
        issue_ctx = issue_context if isinstance(issue_context, dict) else {}
        primary = issue_ctx.get("primary", {}) if isinstance(issue_ctx.get("primary"), dict) else {}
        linked = issue_ctx.get("linked_findings", []) if isinstance(issue_ctx.get("linked_findings"), list) else []
        todo_ctx = todo_prompt_context if isinstance(todo_prompt_context, dict) else {}
        snippet = str(todo_ctx.get("snippet") or focus_snippet or "").strip()
        todo_comment = str(todo_ctx.get("todo_comment") or "").strip()
        if self.prompt_mode == "todo_compact" and snippet:
            code_section = (
                "[TODO Comment]\n"
                f"{todo_comment or primary.get('message', '')}\n\n"
                "[Focused Code Snippet]\n"
                f"{snippet}\n\n"
            )
        elif snippet:
            code_section = (
                "[Code Snippet (focus area)]\n"
                f"{snippet}\n\n"
                "[Full Code]\n"
                f"{code}\n\n"
            )
        else:
            code_section = (
                "[Code]\n"
                f"{code}\n\n"
            )
        primary_summary = {
            "source": str(primary.get("source", "") or ""),
            "issue_id": str(primary.get("issue_id", "") or ""),
            "rule_id": str(primary.get("rule_id", "") or ""),
            "line": int(primary.get("line", 0) or 0),
            "file": str(primary.get("file", "") or ""),
            "object": str(primary.get("object", "") or ""),
            "event": str(primary.get("event", "") or ""),
            "severity": str(primary.get("severity", "") or ""),
            "message": str(primary.get("message", "") or ""),
        }
        if todo_comment:
            primary_summary["todo_comment"] = todo_comment
        if self.prompt_mode == "todo_compact":
            linked_summaries = []
            for item in linked[:2]:
                if not isinstance(item, dict):
                    continue
                linked_rule = str(item.get("rule_id", "") or "").strip()
                linked_message = str(item.get("message", "") or "").strip()
                linked_line = self._safe_int(item.get("line", 0), 0)
                parts = [part for part in [linked_rule, linked_message] if part]
                label = " - ".join(parts[:2]) if parts else "linked finding"
                if linked_line > 0:
                    label = f"line {linked_line}: {label}"
                linked_summaries.append(label)
            linked_section = "\n".join(f"- {item}" for item in linked_summaries) if linked_summaries else "- none"
            primary_line = (
                f"source={primary_summary['source']}, "
                f"rule={primary_summary['rule_id']}, "
                f"line={primary_summary['line']}, "
                f"object={primary_summary['object'] or primary_summary['file']}, "
                f"severity={primary_summary['severity']}"
            )
            return (
                "[Task] Fix only the WinCC OA issue described below with the smallest safe code change.\n"
                f"[{context_line}]\n\n"
                f"{code_section}"
                "[Primary Finding]\n"
                f"{primary_line}\n"
                f"message={primary_summary['message']}\n\n"
                "[Linked Findings]\n"
                f"{linked_section}\n\n"
                "[Requirements]\n"
                "1. Respond in Korean.\n"
                "2. Keep the fix local to the shown snippet.\n"
                "3. Do not redesign the function or add broad refactors.\n"
                "4. Reuse the exact identifiers, datapoint names, variables, and literal values from the shown snippet.\n"
                "5. Do not invent placeholder names, sample object paths, or before/after markers such as =>.\n"
                "6. Output only one short summary sentence and one cpp code block.\n"
                "7. Avoid explanations, lists, risk sections, or extra headings.\n\n"
                "[Output Format]\n"
                "요약: <한 문장>\n\n"
                "코드:\n"
                "```cpp\n"
                "<직접 수정 예시 코드>\n"
                "```\n"
            )
        return (
            "[Task] Apply a minimal code improvement for the existing P1/P2 findings in WinCC OA control code.\n"
            f"[{context_line}]\n\n"
            f"{code_section}"
            "[Primary Parent Finding]\n"
            f"{json.dumps(primary_summary, ensure_ascii=False)}\n\n"
            "[Linked Findings]\n"
            f"{json.dumps(linked, ensure_ascii=False)}\n\n"
            "[Detected Violations]\n"
            f"{json.dumps(violations, ensure_ascii=False)}\n\n"
            "[Requirements]\n"
            "1. Respond in Korean.\n"
            "2. Reuse the exact identifiers, datapoint names, variables, and literal values from the shown snippet.\n"
            "3. Do not invent placeholder names, sample object paths, or before/after markers such as =>.\n"
            "4. Output only one short summary sentence and one code block.\n"
            "5. Do NOT output sections such as Critical Risks, Mitigation Guidance, numbered lists, or broad code review.\n"
            "6. Focus only on directly improving the parent finding and any linked P2 findings.\n"
            "7. Keep the change minimal and within the parent issue scope.\n"
            "8. Keep function/API names in original English.\n\n"
            "[Output Format]\n"
            "요약: <한 문장>\n\n"
            "코드:\n"
            "```cpp\n"
            "<직접 수정 예시 코드>\n"
            "```\n\n"
            "[Review]\n"
        )

    @staticmethod
    def _extract_first_code_block(text: str) -> str:
        match = re.search(r"```(?:[A-Za-z0-9_+-]+)?\s*\n(.*?)```", str(text or ""), flags=re.DOTALL)
        if not match:
            return ""
        return match.group(1).strip()

    @classmethod
    def _normalize_review_code_block(cls, text: str) -> str:
        code = cls._extract_first_code_block(text)
        if not code:
            return ""
        lines = code.splitlines()
        if any("=>" in str(line or "") for line in lines):
            normalized = []
            saw_arrow = False
            for raw in lines:
                line = str(raw or "").rstrip()
                stripped = line.strip()
                if not stripped:
                    if saw_arrow and normalized and normalized[-1] != "":
                        normalized.append("")
                    continue
                if "=>" in stripped:
                    saw_arrow = True
                    after = stripped.split("=>", 1)[1].strip()
                    if after:
                        normalized.append(after)
                    continue
                if saw_arrow:
                    normalized.append(line)
            if normalized:
                lines = normalized
        return "\n".join(lines).strip()

    @staticmethod
    def _extract_summary_line(text: str) -> str:
        raw = str(text or "").strip()
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.lower().startswith("요약:"):
                return stripped
            if stripped.startswith("#") or stripped.startswith("###"):
                continue
            if stripped.startswith("```"):
                continue
            return f"요약: {stripped}"
        return "요약: 신고된 위반 항목에 맞는 최소 수정 코드를 적용하세요."

    def _normalize_review_output(self, text: str) -> str:
        summary = self._extract_summary_line(text)
        code = self._normalize_review_code_block(text)
        if not code:
            code = "// TODO: 위반 항목에 맞는 최소 수정 코드를 여기에 작성하세요."
        return f"{summary}\n\n코드:\n```cpp\n{code}\n```"

    def list_models(self) -> List[str]:
        if self.provider != "ollama":
            return []
        payload = self._get_json(self._ollama_tags_url())
        models = payload.get("models", [])
        if not isinstance(models, list):
            return []
        out: List[str] = []
        for item in models:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "") or "").strip()
            if name:
                out.append(name)
        return out

    def _call_ollama(self, prompt: str, *, model_name: Optional[str] = None) -> str:
        payload = {
            "model": str(model_name or self.model_name),
            "prompt": prompt,
            "stream": False,
            "options": self.options,
        }
        if self.system_prompt:
            payload["system"] = self.system_prompt
        response = self._post_json(self.ollama_url, payload)
        text = str(response.get("response", "")).strip()
        if not text:
            raise ReviewerResponseError("Empty AI response", details={"url": self.ollama_url})
        return text

    def generate_review(
        self,
        code: str,
        violations: List[Dict],
        use_context: bool = False,
        context_payload: Optional[Dict] = None,
        focus_snippet: str = "",
        issue_context: Optional[Dict] = None,
        todo_prompt_context: Optional[Dict] = None,
        model_name: Optional[str] = None,
    ) -> str:
        try:
            if self.provider != "ollama":
                raise ReviewerError(
                    f"Unsupported AI provider: {self.provider}",
                    error_code="AI_REVIEW_UNSUPPORTED_PROVIDER",
                    details={"provider": self.provider},
                )
            prompt = self._build_prompt(
                code,
                violations,
                use_context=use_context,
                context_payload=context_payload,
                focus_snippet=focus_snippet,
                issue_context=issue_context,
                todo_prompt_context=todo_prompt_context,
            )
            return self._normalize_review_output(self._call_ollama(prompt, model_name=model_name))
        except ReviewerError as exc:
            if self.fail_soft:
                msg = f"AI live review failed: {exc}"
                print(f"[!] AI live review skipped (fail-soft): {exc}")
                return msg

            raise

    @staticmethod
    def get_mock_review(
        code: str,
        violations: List[Dict],
        issue_context: Optional[Dict] = None,
        todo_prompt_context: Optional[Dict] = None,
    ) -> str:
        primary = issue_context.get("primary", {}) if isinstance(issue_context, dict) and isinstance(issue_context.get("primary"), dict) else {}
        rule_id = str(primary.get("rule_id", "") or "")
        source = str(primary.get("source", "") or "P1")
        message = str(primary.get("message", "") or "")
        todo_comment = str((todo_prompt_context or {}).get("todo_comment", "") or "").strip()
        summary_target = todo_comment or rule_id or message or "기존 지적사항"
        return (
            f"요약: {source} 기준 {summary_target} 개선을 위해 최소 범위 수정으로 정리하세요.\n\n"
            "코드:\n```cpp\n"
            f"// TODO: {summary_target} 개선을 위한 최소 수정\n"
            "if (isValid) {\n"
            "  // apply update\n"
            "}\n"
            "```"
        )

    @classmethod
    def extract_review_code_block(cls, review_text: str) -> str:
        return cls._extract_first_code_block(review_text)

    @classmethod
    def extract_review_summary(cls, review_text: str) -> str:
        return cls._extract_summary_line(review_text)
