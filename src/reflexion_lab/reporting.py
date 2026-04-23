from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from .schemas import ReportPayload, RunRecord


def summarize(records: list[RunRecord]) -> dict:
    grouped: dict[str, list[RunRecord]] = defaultdict(list)
    for record in records:
        grouped[record.agent_type].append(record)

    summary: dict[str, dict] = {}
    for agent_type, rows in grouped.items():
        summary[agent_type] = {
            "count": len(rows),
            "em": round(mean(1.0 if r.is_correct else 0.0 for r in rows), 4),
            "avg_attempts": round(mean(r.attempts for r in rows), 4),
            "avg_token_estimate": round(mean(r.token_estimate for r in rows), 2),
            "avg_latency_ms": round(mean(r.latency_ms for r in rows), 2),
        }

    difficulty_summary: dict[str, dict] = {}
    for difficulty in sorted(
        {getattr(r, "difficulty", None) for r in records if hasattr(r, "difficulty")} - {None}
    ):
        difficulty_rows = [r for r in records if getattr(r, "difficulty", None) == difficulty]
        if difficulty_rows:
            difficulty_summary[difficulty] = {
                "count": len(difficulty_rows),
                "em": round(mean(1.0 if r.is_correct else 0.0 for r in difficulty_rows), 4),
            }

    if difficulty_summary:
        summary["by_difficulty"] = difficulty_summary

    if "react" in summary and "reflexion" in summary:
        summary["delta_reflexion_minus_react"] = {
            "em_abs": round(summary["reflexion"]["em"] - summary["react"]["em"], 4),
            "attempts_abs": round(summary["reflexion"]["avg_attempts"] - summary["react"]["avg_attempts"], 4),
            "tokens_abs": round(summary["reflexion"]["avg_token_estimate"] - summary["react"]["avg_token_estimate"], 2),
            "latency_abs": round(summary["reflexion"]["avg_latency_ms"] - summary["react"]["avg_latency_ms"], 2),
        }

    return summary


def failure_breakdown(records: list[RunRecord]) -> dict:
    by_agent: dict[str, Counter] = defaultdict(Counter)
    overall = Counter()
    by_agent_and_difficulty: dict[str, dict[str, int]] = {}

    for record in records:
        by_agent[record.agent_type][record.failure_mode] += 1
        overall[record.failure_mode] += 1

        key = f"{record.agent_type}:{getattr(record, 'difficulty', 'unknown')}"
        by_agent_and_difficulty.setdefault(key, Counter())
        by_agent_and_difficulty[key][record.failure_mode] += 1

    return {
        "by_agent": {agent: dict(counter) for agent, counter in by_agent.items()},
        "overall": dict(overall),
        "by_agent_and_difficulty": {
            bucket: dict(counter) for bucket, counter in by_agent_and_difficulty.items()
        },
    }

def generate_discussion(summary: dict, failure_modes: dict) -> str:
    react = summary.get("react", {})
    reflexion = summary.get("reflexion", {})
    delta = summary.get("delta_reflexion_minus_react", {})

    em_gain = delta.get("em_abs", 0)
    attempt_diff = delta.get("attempts_abs", 0)
    latency_diff = delta.get("latency_abs", 0)

    # Failure patterns
    overall_failures = failure_modes.get("overall", {})
    top_failure = max(overall_failures, key=overall_failures.get) if overall_failures else "unknown"

    discussion = []

    # Core improvement
    discussion.append(
        f"Reflexion improves exact match (EM) by {em_gain:.2f} compared to ReAct."
    )

    # Trade-offs
    discussion.append(
        f"This improvement comes with a change of {attempt_diff:.2f} in average attempts "
        f"and {latency_diff:.2f} ms latency difference."
    )

    # Failure analysis
    discussion.append(
        f"The most common failure mode observed is '{top_failure}', indicating where reasoning breaks down."
    )

    # Interpretation
    if em_gain > 0:
        discussion.append(
            "This suggests that iterative refinement helps correct initial reasoning mistakes."
        )
    else:
        discussion.append(
            "This suggests that reflection did not significantly improve performance in this setting."
        )

    # Reflection behavior
    discussion.append(
        "Reflection is particularly useful when multi-hop reasoning fails or when the model drifts to incorrect entities."
    )

    return " ".join(discussion)


def build_report(records: list[RunRecord], dataset_name: str, mode: str = "mock") -> ReportPayload:
    examples = [
        {
            "qid": r.qid,
            "difficulty": r.difficulty,
            "agent_type": r.agent_type,
            "gold_answer": r.gold_answer,
            "predicted_answer": r.predicted_answer,
            "is_correct": r.is_correct,
            "attempts": r.attempts,
            "failure_mode": r.failure_mode,
            "reflection_count": len(r.reflections),
        }
        for r in records
    ]

    summary = summarize(records)
    failure_modes = failure_breakdown(records)
    discussion_text = generate_discussion(summary, failure_modes)

    extensions = [
        "structured_evaluator",
        "reflection_memory",
        "benchmark_report_json",
        "adaptive_max_attempts",
    ]

    if mode == "mock":
        extensions.append("mock_mode_for_autograding")

    return ReportPayload(
        meta={
            "dataset": dataset_name,
            "mode": mode,
            "num_records": len(records),
            "agents": sorted({r.agent_type for r in records}),
        },
        summary=summary,
        failure_modes=failure_modes,
        examples=examples,
        extensions=extensions,
        discussion=discussion_text,
    )



def save_report(report: ReportPayload, out_dir: str | Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"

    # JSON
    json_path.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")

    # Markdown
    s = report.summary
    react = s.get("react", {})
    reflexion = s.get("reflexion", {})
    delta = s.get("delta_reflexion_minus_react", {})

    ext_lines = "\n".join(f"- {item}" for item in report.extensions)

    md = f"""# Lab 16 Benchmark Report

## Metadata
- Dataset: {report.meta['dataset']}
- Mode: {report.meta['mode']}
- Records: {report.meta['num_records']}
- Agents: {', '.join(report.meta['agents'])}

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | {react.get('em', 0)} | {reflexion.get('em', 0)} | {delta.get('em_abs', 0)} |
| Avg attempts | {react.get('avg_attempts', 0)} | {reflexion.get('avg_attempts', 0)} | {delta.get('attempts_abs', 0)} |
| Avg token estimate | {react.get('avg_token_estimate', 0)} | {reflexion.get('avg_token_estimate', 0)} | {delta.get('tokens_abs', 0)} |
| Avg latency (ms) | {react.get('avg_latency_ms', 0)} | {reflexion.get('avg_latency_ms', 0)} | {delta.get('latency_abs', 0)} |

## Failure modes
```json
{json.dumps(report.failure_modes, indent=2)}
```

## Extensions implemented

{ext_lines}

## Discussion

{report.discussion}
"""

    md_path.write_text(md, encoding="utf-8")

    return json_path, md_path
