import json
import os
import re
import urllib.error
import urllib.request
from typing import Dict, List, Optional


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
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            data = resp.read().decode("utf-8")
        parsed = json.loads(data)
        if not isinstance(parsed, dict):
            raise RuntimeError("Invalid AI response payload")
        return parsed

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
    ) -> Optional[str]:
        context_line = "Context: N/A"
        if use_context:
            context_line = self._build_context_line(context_payload=context_payload)
        snippet = str(focus_snippet or "").strip()
        if snippet:
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
        return (
            "[Task] Propose a minimal code improvement for the detected violations in WinCC OA control code.\n"
            f"[{context_line}]\n\n"
            f"{code_section}"
            "[Detected Violations]\n"
            f"{json.dumps(violations, ensure_ascii=False)}\n\n"
            "[Requirements]\n"
            "1. Respond in Korean.\n"
            "2. Output only one short summary sentence and one code block.\n"
            "3. Do NOT output sections such as Critical Risks, Mitigation Guidance, numbered lists, or broad code review.\n"
            "4. Focus only on direct fix ideas for the provided violations.\n"
            "5. Keep function/API names in original English.\n\n"
            "[Output Format]\n"
            "요약: <한 문장>\n\n"
            "코드:\n"
            "```cpp\n"
            "<짧은 수정 예시 코드>\n"
            "```\n\n"
            "[Review]\n"
        )

    @staticmethod
    def _extract_first_code_block(text: str) -> str:
        match = re.search(r"```(?:[A-Za-z0-9_+-]+)?\s*\n(.*?)```", str(text or ""), flags=re.DOTALL)
        if not match:
            return ""
        return match.group(1).strip()

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
        return "요약: 제공된 위반 항목에 맞는 최소 수정 코드를 적용하세요."

    def _normalize_review_output(self, text: str) -> str:
        summary = self._extract_summary_line(text)
        code = self._extract_first_code_block(text)
        if not code:
            code = "// TODO: 위반 항목에 맞는 최소 수정 코드를 여기에 작성하세요."
        return f"{summary}\n\n코드:\n```cpp\n{code}\n```"

    def _call_ollama(self, prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": self.options,
        }
        if self.system_prompt:
            payload["system"] = self.system_prompt
        response = self._post_json(self.ollama_url, payload)
        text = str(response.get("response", "")).strip()
        if not text:
            raise RuntimeError("Empty AI response")
        return text

    def generate_review(
        self,
        code: str,
        violations: List[Dict],
        use_context: bool = False,
        context_payload: Optional[Dict] = None,
        focus_snippet: str = "",
    ) -> str:
        try:
            if self.provider != "ollama":
                raise RuntimeError(f"Unsupported AI provider: {self.provider}")
            prompt = self._build_prompt(
                code,
                violations,
                use_context=use_context,
                context_payload=context_payload,
                focus_snippet=focus_snippet,
            )
            return self._normalize_review_output(self._call_ollama(prompt))
        except Exception as exc:
            if self.fail_soft:
                msg = f"AI live review failed: {exc}"
                print(f"[!] AI live review skipped (fail-soft): {exc}")
                return msg

            raise

    @staticmethod
    def get_mock_review(code: str, violations: List[Dict]) -> str:
        return (
            "요약: 조건 검증 후 최소 범위만 수정하는 코드로 정리하세요.\n\n"
            "코드:\n```cpp\n"
            "// TODO: 조건 검증 추가 후 필요한 호출만 수행\n"
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
