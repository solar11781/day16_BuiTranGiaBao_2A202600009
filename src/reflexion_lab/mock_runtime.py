from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, REFLECTOR_SYSTEM
from .schemas import QAExample, JudgeResult, ReflectionEntry
from .utils import normalize_answer

# Historical mock maps are kept for compatibility with the original scaffold and report labels.
FIRST_ATTEMPT_WRONG = {"hp2": "London", "hp4": "Atlantic Ocean", "hp6": "Red Sea", "hp8": "Andes"}
FAILURE_MODE_BY_QID = {"hp2": "incomplete_multi_hop", "hp4": "wrong_final_answer", "hp6": "entity_drift", "hp8": "entity_drift"}

if load_dotenv is not None:  # pragma: no branch - safe optional setup
    load_dotenv()


@dataclass
class LLMCallResult:
    content: str
    token_count: int
    latency_ms: int
    raw_response: str


class OllamaRuntime:
    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.actor_model = os.getenv("OLLAMA_MODEL")
        self.evaluator_model = os.getenv("OLLAMA_EVALUATOR_MODEL", self.actor_model)
        self.reflector_model = os.getenv("OLLAMA_REFLECTOR_MODEL", self.actor_model)
        if not self.actor_model:
            raise RuntimeError(
                "Missing OLLAMA_MODEL in the environment. Add it to .env before running the benchmark."
            )

    def chat(
        self,
        *,
        model: str,
        system: str,
        user: str,
        response_format=None,
        temperature: float = 0.0,
    ) -> LLMCallResult:

        prompt = system.strip() + "\n\n" + user.strip()

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }

        body = json.dumps(payload).encode("utf-8")

        req = request.Request(
            f"{self.base_url}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=300) as resp:
                raw = resp.read().decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"Ollama error: {e}")

        data = json.loads(raw)

        content = data.get("response", "").strip()
        token_count = int(data.get("eval_count", 0))
        latency_ms = int(data.get("total_duration", 0) / 1_000_000)

        return LLMCallResult(
            content=content,
            token_count=token_count,
            latency_ms=latency_ms,
            raw_response=raw,
        )


_RUNTIME: OllamaRuntime | None = None


def get_runtime() -> OllamaRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = OllamaRuntime()
    return _RUNTIME


def get_runtime_mode() -> str:
    return "ollama"


def _format_context(example: QAExample) -> str:
    lines: list[str] = []
    for idx, chunk in enumerate(example.context, start=1):
        lines.append(f"[{idx}] {chunk.title}: {chunk.text}")
    return "\n".join(lines)


def _strip_json_fence(text: str) -> str:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        candidate = candidate.replace("json", "", 1).strip()
    return candidate


def _safe_json_loads(text: str) -> dict[str, Any]:
    candidate = _strip_json_fence(text)
    return json.loads(candidate)


def _json_schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def actor_answer(example: QAExample, attempt_id: int, agent_type: str, reflection_memory: list[str]) -> LLMCallResult:
    runtime = get_runtime()
    reflection_block = "\n".join(f"- {item}" for item in reflection_memory[-3:]) if reflection_memory else "- None"
    user = f"""
Question: {example.question}
Difficulty: {example.difficulty}
Agent type: {agent_type}
Attempt: {attempt_id}

Context:
{_format_context(example)}

Reflection memory from previous attempts:
{reflection_block}

Return only the final answer.
"""
    return runtime.chat(model=runtime.actor_model, system=ACTOR_SYSTEM, user=user, temperature=0.0)


def evaluator(example: QAExample, answer: str) -> JudgeResult:
    runtime = get_runtime()
    schema = _json_schema(
        properties={
            "score": {"type": "integer", "enum": [0, 1]},
            "reason": {"type": "string"},
            "missing_evidence": {"type": "array", "items": {"type": "string"}},
            "spurious_claims": {"type": "array", "items": {"type": "string"}},
            "cited_context_titles": {"type": "array", "items": {"type": "string"}},
        },
        required=["score", "reason", "missing_evidence", "spurious_claims", "cited_context_titles"],
    )
    user = f"""
Question: {example.question}
Gold answer: {example.gold_answer}
Predicted answer: {answer}

Context:
{_format_context(example)}

Return ONLY valid JSON. No explanation, no text outside JSON.
"""
    result = runtime.chat(
        model=runtime.evaluator_model,
        system=EVALUATOR_SYSTEM,
        user=user,
        response_format=schema,
        temperature=0.0,
    )

    normalized_match = int(normalize_answer(example.gold_answer) == normalize_answer(answer))
    try:
        payload = _safe_json_loads(result.content)
        score = int(payload.get("score", normalized_match))
        if normalized_match == 1:
            score = 1
        return JudgeResult(
            score=score,
            reason=str(payload.get("reason", "")) or (
                "Final answer matches the gold answer after normalization."
                if normalized_match == 1
                else "The predicted answer does not match the gold answer."
            ),
            missing_evidence=[str(item) for item in payload.get("missing_evidence", [])],
            spurious_claims=[str(item) for item in payload.get("spurious_claims", [])],
            cited_context_titles=[str(item) for item in payload.get("cited_context_titles", [])],
            token_count=result.token_count,
            latency_ms=result.latency_ms,
            raw_response=result.raw_response,
        )
    except Exception:
        fallback_reason = (
            "Final answer matches the gold answer after normalization."
            if normalized_match == 1
            else "The evaluator response was invalid JSON, so scoring fell back to normalized exact match."
        )
        return JudgeResult(
            score=normalized_match,
            reason=fallback_reason,
            missing_evidence=[] if normalized_match == 1 else ["Evaluator fallback was used due to invalid JSON."],
            spurious_claims=[] if normalized_match == 1 else [answer],
            cited_context_titles=[],
            token_count=result.token_count,
            latency_ms=result.latency_ms,
            raw_response=result.raw_response,
        )


def reflector(example: QAExample, attempt_id: int, judge: JudgeResult) -> ReflectionEntry:
    runtime = get_runtime()
    schema = _json_schema(
        properties={
            "lesson": {"type": "string"},
            "next_strategy": {"type": "string"},
        },
        required=["lesson", "next_strategy"],
    )
    user = f"""
Question: {example.question}
Attempt id: {attempt_id}
Evaluator reason: {judge.reason}
Missing evidence: {json.dumps(judge.missing_evidence, ensure_ascii=False)}
Spurious claims: {json.dumps(judge.spurious_claims, ensure_ascii=False)}

Context:
{_format_context(example)}

Return strict JSON only.
"""
    result = runtime.chat(
        model=runtime.reflector_model,
        system=REFLECTOR_SYSTEM,
        user=user,
        response_format=schema,
        temperature=0.0,
    )
    try:
        payload = _safe_json_loads(result.content)
        lesson = str(payload.get("lesson", "")).strip() or "The previous answer was not fully grounded in the provided context."
        strategy = str(payload.get("next_strategy", "")).strip() or "Re-read the supporting paragraphs and complete the missing reasoning hop."
    except Exception:
        lesson = "The previous answer was not fully grounded in the provided context."
        strategy = "Re-read the supporting paragraphs and complete the missing reasoning hop."
    return ReflectionEntry(
        attempt_id=attempt_id,
        failure_reason=judge.reason,
        lesson=lesson,
        next_strategy=strategy,
        token_count=result.token_count,
        latency_ms=result.latency_ms,
        raw_response=result.raw_response,
    )


def classify_failure_mode(reason: str, answer: str, agent_type: str, attempt_id: int, max_attempts: int) -> str:
    normalized_reason = reason.lower()
    normalized_answer = normalize_answer(answer)
    if "loop" in normalized_reason or (attempt_id >= max_attempts and normalized_answer == ""):
        return "looping"
    if any(term in normalized_reason for term in ["first hop", "second hop", "multi-hop", "intermediate", "partial"]):
        return "incomplete_multi_hop"
    if any(term in normalized_reason for term in ["wrong entity", "unsupported", "not grounded", "drift", "spurious"]):
        return "entity_drift"
    if agent_type == "reflexion" and attempt_id > 1 and any(term in normalized_reason for term in ["still wrong", "repeated", "same mistake"]):
        return "reflection_overfit"
    return "wrong_final_answer"
