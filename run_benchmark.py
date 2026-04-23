from __future__ import annotations
import json
from pathlib import Path
import typer
from rich import print
from src.reflexion_lab.agents import ReActAgent, ReflexionAgent
from src.reflexion_lab.mock_runtime import get_runtime_mode
from src.reflexion_lab.reporting import build_report, save_report
from src.reflexion_lab.utils import load_dataset, save_jsonl
app = typer.Typer(add_completion=False)

@app.command()
def main(dataset: str = "data/hotpot_100_final_balanced.json", out_dir: str = "outputs/run", reflexion_attempts: int = 2) -> None:
    examples = load_dataset(dataset)
    # examples = load_dataset(dataset)[:5]

    # group by difficulty
    groups = {
        "easy": [e for e in examples if e.difficulty == "easy"],
        "medium": [e for e in examples if e.difficulty == "medium"],
        "hard": [e for e in examples if e.difficulty == "hard"],
    }

    react = ReActAgent()
    reflexion = ReflexionAgent(max_attempts=reflexion_attempts)

    all_react = []
    all_reflexion = []

    base_out = Path(out_dir)

    for difficulty, subset in groups.items():
        if not subset:
            continue

        print(f"\n=== Running {difficulty} ({len(subset)} examples) ===")

        react_records = [react.run(example) for example in subset]
        reflexion_records = [reflexion.run(example) for example in subset]

        all_react.extend(react_records)
        all_reflexion.extend(reflexion_records)

        diff_dir = base_out / f"hotpot_{difficulty}"

        # save runs
        save_jsonl(diff_dir / "react_runs.jsonl", react_records)
        save_jsonl(diff_dir / "reflexion_runs.jsonl", reflexion_records)

        # build report ONLY for this difficulty
        all_records = react_records + reflexion_records

        report = build_report(
            all_records,
            dataset_name=f"{Path(dataset).name}_{difficulty}",
            mode=get_runtime_mode()
        )

        json_path, md_path = save_report(report, diff_dir)

        print(f"[green]Saved[/green] {json_path}")
        print(f"[green]Saved[/green] {md_path}")

    # ===== GLOBAL REPORT (ALL DIFFICULTIES COMBINED) =====
    all_records = all_react + all_reflexion

    global_report = build_report(
        all_records,
        dataset_name=Path(dataset).name,
        mode=get_runtime_mode()
    )

    json_path, md_path = save_report(global_report, base_out)

    print(f"[green]Saved GLOBAL[/green] {json_path}")
    print(f"[green]Saved GLOBAL[/green] {md_path}")

if __name__ == "__main__":
    app()
