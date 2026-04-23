from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from .mock_runtime import FAILURE_MODE_BY_QID, actor_answer, classify_failure_mode, evaluator, reflector
from .schemas import AttemptTrace, QAExample, ReflectionEntry, RunRecord

@dataclass
class BaseAgent:
    agent_type: Literal["react", "reflexion"]
    max_attempts: int = 1

    def resolve_max_attempts(self, example: QAExample) -> int:
        return self.max_attempts

    def run(self, example: QAExample) -> RunRecord:
        reflection_memory: list[str] = []
        reflections: list[ReflectionEntry] = []
        traces: list[AttemptTrace] = []
        final_answer = ""
        final_score = 0
        allowed_attempts = self.resolve_max_attempts(example)
        print(f"[{self.__class__.__name__}] Running {example.qid} (max_attempts={allowed_attempts})")

        for attempt_id in range(1, allowed_attempts + 1):
            print(f"  Attempt {attempt_id}...")
            actor_result = actor_answer(example, attempt_id, self.agent_type, reflection_memory)
            answer = actor_result.content
            judge = evaluator(example, answer)
            # TODO: Replace with actual token count from LLM response
            token_estimate = actor_result.token_count + judge.token_count
            # TODO: Replace with actual latency measurement
            latency_ms = actor_result.latency_ms + judge.latency_ms
            trace = AttemptTrace(attempt_id=attempt_id, answer=answer, score=judge.score, reason=judge.reason, token_estimate=token_estimate, latency_ms=latency_ms)
            final_answer = answer
            final_score = judge.score
            if judge.score == 1:
                traces.append(trace)
                break
            
            # TODO: Học viên triển khai logic Reflexion tại đây
            # 1. Kiểm tra nếu agent_type là 'reflexion' và chưa hết số lần attempt
            # 2. Gọi hàm reflector để lấy nội dung reflection
            # 3. Cập nhật reflection_memory để Actor dùng cho lần sau
            if self.agent_type == "reflexion" and attempt_id < allowed_attempts:
                reflection = reflector(example, attempt_id, judge)
                reflections.append(reflection)
                reflection_memory.append(f"Lesson: {reflection.lesson}")
                reflection_memory.append(f"Next strategy: {reflection.next_strategy}")
                trace.reflection = reflection
                trace.token_estimate += reflection.token_count
                trace.latency_ms += reflection.latency_ms
            traces.append(trace)
        total_tokens = sum(t.token_estimate for t in traces)
        total_latency = sum(t.latency_ms for t in traces)
        failure_mode = "none" if final_score == 1 else FAILURE_MODE_BY_QID.get(example.qid, classify_failure_mode(traces[-1].reason, final_answer, self.agent_type, len(traces), allowed_attempts))
        return RunRecord(qid=example.qid, question=example.question, gold_answer=example.gold_answer, difficulty=example.difficulty, agent_type=self.agent_type, predicted_answer=final_answer, is_correct=bool(final_score), attempts=len(traces), token_estimate=total_tokens, latency_ms=total_latency, failure_mode=failure_mode, reflections=reflections, traces=traces)

class ReActAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(agent_type="react", max_attempts=1)

class ReflexionAgent(BaseAgent):
    def __init__(self, max_attempts: int = 3, adaptive_attempts: bool = True) -> None:
        super().__init__(agent_type="reflexion", max_attempts=max_attempts)
        self.adaptive_attempts = adaptive_attempts

    def resolve_max_attempts(self, example: QAExample) -> int:
        if not self.adaptive_attempts:
            return self.max_attempts
        difficulty_budget = {"easy": 2, "medium": 3, "hard": 4}
        return min(max(1, self.max_attempts), difficulty_budget.get(example.difficulty, self.max_attempts))
