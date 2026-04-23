# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_100_final_balanced.json_hard
- Mode: ollama
- Records: 80
- Agents: react, reflexion

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 0.85 | 0.925 | 0.075 |
| Avg attempts | 1 | 1.225 | 0.225 |
| Avg token estimate | 739.05 | 1606.45 | 867.4 |
| Avg latency (ms) | 3408.8 | 6595.15 | 3186.35 |

## Failure modes
```json
{
  "by_agent": {
    "react": {
      "none": 34,
      "wrong_final_answer": 6
    },
    "reflexion": {
      "none": 37,
      "wrong_final_answer": 3
    }
  },
  "overall": {
    "none": 71,
    "wrong_final_answer": 9
  },
  "by_agent_and_difficulty": {
    "react:hard": {
      "none": 34,
      "wrong_final_answer": 6
    },
    "reflexion:hard": {
      "none": 37,
      "wrong_final_answer": 3
    }
  }
}
```

## Extensions implemented

- structured_evaluator
- reflection_memory
- benchmark_report_json
- adaptive_max_attempts

## Discussion

Reflexion improves exact match (EM) by 0.07 compared to ReAct. This improvement comes with a change of 0.23 in average attempts and 3186.35 ms latency difference. The most common failure mode observed is 'none', indicating where reasoning breaks down. This suggests that iterative refinement helps correct initial reasoning mistakes. Reflection is particularly useful when multi-hop reasoning fails or when the model drifts to incorrect entities.
