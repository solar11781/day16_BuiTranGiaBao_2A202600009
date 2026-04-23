# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_100_final_balanced.json_medium
- Mode: ollama
- Records: 80
- Agents: react, reflexion

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 0.9 | 0.925 | 0.025 |
| Avg attempts | 1 | 1.3 | 0.3 |
| Avg token estimate | 980.45 | 849.35 | -131.1 |
| Avg latency (ms) | 4494.18 | 4566.52 | 72.34 |

## Failure modes
```json
{
  "by_agent": {
    "react": {
      "none": 36,
      "wrong_final_answer": 4
    },
    "reflexion": {
      "none": 37,
      "wrong_final_answer": 3
    }
  },
  "overall": {
    "none": 73,
    "wrong_final_answer": 7
  },
  "by_agent_and_difficulty": {
    "react:medium": {
      "none": 36,
      "wrong_final_answer": 4
    },
    "reflexion:medium": {
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

Reflexion improves exact match (EM) by 0.03 compared to ReAct. This improvement comes with a change of 0.30 in average attempts and 72.34 ms latency difference. The most common failure mode observed is 'none', indicating where reasoning breaks down. This suggests that iterative refinement helps correct initial reasoning mistakes. Reflection is particularly useful when multi-hop reasoning fails or when the model drifts to incorrect entities.
