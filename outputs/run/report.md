# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_100_final_balanced.json
- Mode: ollama
- Records: 200
- Agents: react, reflexion

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 0.85 | 0.91 | 0.06 |
| Avg attempts | 1 | 1.25 | 0.25 |
| Avg token estimate | 824.88 | 1286.81 | 461.93 |
| Avg latency (ms) | 3861.73 | 5693.47 | 1831.74 |

## Failure modes
```json
{
  "by_agent": {
    "react": {
      "none": 85,
      "wrong_final_answer": 15
    },
    "reflexion": {
      "wrong_final_answer": 9,
      "none": 91
    }
  },
  "overall": {
    "none": 176,
    "wrong_final_answer": 24
  },
  "by_agent_and_difficulty": {
    "react:easy": {
      "none": 15,
      "wrong_final_answer": 5
    },
    "react:medium": {
      "none": 36,
      "wrong_final_answer": 4
    },
    "react:hard": {
      "none": 34,
      "wrong_final_answer": 6
    },
    "reflexion:easy": {
      "wrong_final_answer": 3,
      "none": 17
    },
    "reflexion:medium": {
      "none": 37,
      "wrong_final_answer": 3
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

Reflexion improves exact match (EM) by 0.06 compared to ReAct. This improvement comes with a change of 0.25 in average attempts and 1831.74 ms latency difference. The most common failure mode observed is 'none', indicating where reasoning breaks down. This suggests that iterative refinement helps correct initial reasoning mistakes. Reflection is particularly useful when multi-hop reasoning fails or when the model drifts to incorrect entities.
