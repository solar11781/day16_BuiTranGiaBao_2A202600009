# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_100_final_balanced.json_easy
- Mode: ollama
- Records: 40
- Agents: react, reflexion

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 0.75 | 0.85 | 0.1 |
| Avg attempts | 1 | 1.2 | 0.2 |
| Avg token estimate | 685.4 | 1522.45 | 837.05 |
| Avg latency (ms) | 3502.7 | 6144 | 2641.3 |

## Failure modes
```json
{
  "by_agent": {
    "react": {
      "none": 15,
      "wrong_final_answer": 5
    },
    "reflexion": {
      "wrong_final_answer": 3,
      "none": 17
    }
  },
  "overall": {
    "none": 32,
    "wrong_final_answer": 8
  },
  "by_agent_and_difficulty": {
    "react:easy": {
      "none": 15,
      "wrong_final_answer": 5
    },
    "reflexion:easy": {
      "wrong_final_answer": 3,
      "none": 17
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

Reflexion improves exact match (EM) by 0.10 compared to ReAct. This improvement comes with a change of 0.20 in average attempts and 2641.30 ms latency difference. The most common failure mode observed is 'none', indicating where reasoning breaks down. This suggests that iterative refinement helps correct initial reasoning mistakes. Reflection is particularly useful when multi-hop reasoning fails or when the model drifts to incorrect entities.
