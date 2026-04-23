from __future__ import annotations
import json
import random
from pathlib import Path
from collections import Counter

import typer
from datasets import load_dataset

app = typer.Typer(add_completion=False)


def _get_item_id(item: dict, fallback_index: int) -> str:
    for key in ("_id", "id", "qid"):
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return f"hotpot_{fallback_index}"


def _normalize_level(item: dict) -> str:
    level = str(item.get("level", "medium")).strip().lower()
    if level not in {"easy", "medium", "hard"}:
        return "medium"
    return level


def _join_sentences(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(str(part) for part in value if part is not None)
    return str(value)


def _normalize_context(raw_context) -> list[dict[str, str]]:
    context: list[dict[str, str]] = []

    if isinstance(raw_context, dict):
        titles = raw_context.get("title", [])
        sentences = raw_context.get("sentences", raw_context.get("text", []))

        if isinstance(titles, str):
            titles = [titles]
        elif titles is None:
            titles = []

        if isinstance(sentences, str):
            sentences = [sentences]
        elif sentences is None:
            sentences = []

        max_len = max(len(titles), len(sentences))
        for idx in range(max_len):
            title = titles[idx] if idx < len(titles) else f"context_{idx}"
            sentence_group = sentences[idx] if idx < len(sentences) else []
            context.append(
                {
                    "title": str(title),
                    "text": _join_sentences(sentence_group),
                }
            )
        return context

    if isinstance(raw_context, (list, tuple)):
        for idx, chunk in enumerate(raw_context):
            if isinstance(chunk, dict):
                title = chunk.get("title", f"context_{idx}")
                if "text" in chunk:
                    text = _join_sentences(chunk.get("text"))
                else:
                    text = _join_sentences(chunk.get("sentences", []))
                context.append({"title": str(title), "text": text})
                continue

            if isinstance(chunk, (list, tuple)) and len(chunk) >= 2:
                title = chunk[0]
                sentence_group = chunk[1]
                context.append(
                    {
                        "title": str(title),
                        "text": _join_sentences(sentence_group),
                    }
                )
                continue

            context.append({"title": f"context_{idx}", "text": _join_sentences(chunk)})
        return context

    if raw_context is None:
        return context

    return [{"title": "context_0", "text": _join_sentences(raw_context)}]


@app.command()
def main(
    out_path: str = "data/hotpot_100_final_balanced.json",
    split: str = "train",
    config: str = "distractor",
    total: int = 100,
    seed: int = 42,
    easy: int = 33,
    medium: int = 34,
    hard: int = 33,
) -> None:
    rng = random.Random(seed)
    dataset = load_dataset("hotpot_qa", config, split=split)
    items = list(dataset)

    if total <= 0:
        raise typer.BadParameter("total must be greater than 0.")
    if total > len(items):
        raise typer.BadParameter(f"Requested total={total}, but dataset only has {len(items)} examples.")

    buckets: dict[str, list[int]] = {"easy": [], "medium": [], "hard": []}
    for index, item in enumerate(items):
        buckets[_normalize_level(item)].append(index)

    target_counts = {"easy": easy, "medium": medium, "hard": hard}
    if sum(target_counts.values()) != total:
        raise typer.BadParameter("The per-difficulty counts must sum to total.")

    chosen_indices: list[int] = []
    remaining_needed = total

    # ===== BALANCED SAMPLING (FINAL) =====
    chosen_indices = []

    # Target distribution (adjustable)
    target_counts = {
        "easy": min(20, len(buckets["easy"])),
        "medium": min(40, len(buckets["medium"])),
        "hard": min(40, len(buckets["hard"])),
    }

    # Step 1: sample from each difficulty
    for level, count in target_counts.items():
        if count > 0:
            chosen_indices.extend(rng.sample(buckets[level], count))

    # Step 2: fill remaining if total < 100
    remaining_needed = total - len(chosen_indices)

    if remaining_needed > 0:
        used = set(chosen_indices)

        # prefer harder questions for remaining
        priority = ["hard", "medium", "easy"]

        for level in priority:
            if remaining_needed <= 0:
                break

            available = list(set(buckets[level]) - used)
            take = min(len(available), remaining_needed)

            if take > 0:
                chosen_indices.extend(rng.sample(available, take))
                used.update(chosen_indices)
                remaining_needed -= take

    # Step 3: final fallback (safety)
    if remaining_needed > 0:
        pool = list(set(range(len(items))) - set(chosen_indices))
        chosen_indices.extend(rng.sample(pool, remaining_needed))

    rng.shuffle(chosen_indices)

    converted = []
    for index in chosen_indices:
        item = items[index]
        converted.append(
            {
                "qid": _get_item_id(item, index),
                "difficulty": _normalize_level(item),
                "question": str(item["question"]),
                "gold_answer": str(item["answer"]),
                "context": _normalize_context(item.get("context")),
            }
        )

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(converted, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(converted)} examples to {path}")
    print(Counter([_normalize_level(item) for item in items]))


if __name__ == "__main__":
    app()
