"""Model cascading and cost tracking for LLM optimization.

Provides intelligent model selection based on task complexity to reduce costs:
- Simple tasks (sentiment, classification): Use cheapest model
- Medium tasks (summarization, Q&A): Use balanced model
- Complex tasks (synthesis, reasoning): Use most capable model

Cost savings: 40-85% reduction in LLM costs.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional
import threading
import logging

logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """Task complexity levels for model selection."""

    SIMPLE = "simple"  # Classification, extraction, yes/no
    MEDIUM = "medium"  # Summarization, Q&A with context
    COMPLEX = "complex"  # Multi-step reasoning, synthesis


@dataclass
class ModelConfig:
    """Configuration for a model tier."""

    name: str
    cost_per_1k_input: float  # USD per 1K input tokens
    cost_per_1k_output: float  # USD per 1K output tokens
    max_tokens: int
    supports_tools: bool = False


class ModelCascade:
    """Smart model selection based on task complexity.

    Cost savings: 40-85% reduction in LLM costs by using
    smaller models for simpler tasks.
    """

    # Gemini model configurations (2025 pricing)
    MODELS = {
        TaskComplexity.SIMPLE: ModelConfig(
            name="gemini-2.0-flash-lite",
            cost_per_1k_input=0.000075,  # $0.075 per 1M
            cost_per_1k_output=0.0003,  # $0.30 per 1M
            max_tokens=8192,
        ),
        TaskComplexity.MEDIUM: ModelConfig(
            name="gemini-2.0-flash",
            cost_per_1k_input=0.0001,  # $0.10 per 1M
            cost_per_1k_output=0.0004,  # $0.40 per 1M
            max_tokens=32768,
            supports_tools=True,
        ),
        TaskComplexity.COMPLEX: ModelConfig(
            name="gemini-2.5-pro",
            cost_per_1k_input=0.00125,  # $1.25 per 1M
            cost_per_1k_output=0.01,  # $10 per 1M
            max_tokens=65536,
            supports_tools=True,
        ),
    }

    # Map task types to complexity levels
    TASK_COMPLEXITY = {
        # Simple tasks - use cheapest model
        "sentiment_classification": TaskComplexity.SIMPLE,
        "sentiment_batch": TaskComplexity.SIMPLE,
        "entity_extraction": TaskComplexity.SIMPLE,
        "yes_no_question": TaskComplexity.SIMPLE,
        "simple_qa": TaskComplexity.SIMPLE,
        # Medium tasks - use balanced model
        "summarization": TaskComplexity.MEDIUM,
        "qa_with_context": TaskComplexity.MEDIUM,
        "news_analysis": TaskComplexity.MEDIUM,
        "chat": TaskComplexity.MEDIUM,
        "tool_calling": TaskComplexity.MEDIUM,
        # Complex tasks - use most capable model
        "research_synthesis": TaskComplexity.COMPLEX,
        "multi_step_reasoning": TaskComplexity.COMPLEX,
        "portfolio_analysis": TaskComplexity.COMPLEX,
        "theme_research": TaskComplexity.COMPLEX,
    }

    @classmethod
    def get_model_for_task(cls, task_type: str) -> ModelConfig:
        """Get optimal model for task type."""
        complexity = cls.TASK_COMPLEXITY.get(task_type, TaskComplexity.MEDIUM)
        return cls.MODELS[complexity]

    @classmethod
    def get_complexity(cls, task_type: str) -> TaskComplexity:
        """Get complexity level for task type."""
        return cls.TASK_COMPLEXITY.get(task_type, TaskComplexity.MEDIUM)

    @classmethod
    def estimate_cost(
        cls, task_type: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Estimate cost for a task in USD."""
        model = cls.get_model_for_task(task_type)
        input_cost = (input_tokens / 1000) * model.cost_per_1k_input
        output_cost = (output_tokens / 1000) * model.cost_per_1k_output
        return input_cost + output_cost


@dataclass
class CostTracker:
    """Track and alert on LLM costs.

    Provides:
    - Daily cost tracking with automatic reset
    - Budget alerts at 80% threshold
    - Cost history for analysis
    """

    daily_budget_usd: float = 10.0  # Default $10/day
    _daily_cost: float = field(default=0.0, repr=False)
    _cost_history: List[Dict] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _current_date: date = field(default_factory=date.today)
    _alert_sent: bool = field(default=False, repr=False)

    def record(
        self,
        task_type: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
    ):
        """Record a cost event."""
        with self._lock:
            # Reset daily counter if new day
            today = date.today()
            if today != self._current_date:
                self._daily_cost = 0.0
                self._current_date = today
                self._alert_sent = False

            self._daily_cost += cost

            # Store history (keep last 1000 entries)
            self._cost_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "task_type": task_type,
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost": cost,
                }
            )
            if len(self._cost_history) > 1000:
                self._cost_history = self._cost_history[-1000:]

            # Check budget alert (log at 80%)
            if not self._alert_sent and self._daily_cost >= self.daily_budget_usd * 0.8:
                self._send_budget_alert()
                self._alert_sent = True

    def _send_budget_alert(self):
        """Send alert when approaching budget limit."""
        remaining = self.daily_budget_usd - self._daily_cost
        logger.warning(
            "LLM cost alert: $%.4f spent today, $%.4f remaining of $%.2f budget",
            self._daily_cost,
            remaining,
            self.daily_budget_usd,
        )

    @property
    def daily_cost(self) -> float:
        """Current day's cost."""
        with self._lock:
            today = date.today()
            if today != self._current_date:
                return 0.0
            return self._daily_cost

    @property
    def is_over_budget(self) -> bool:
        """Check if over daily budget."""
        return self.daily_cost >= self.daily_budget_usd

    @property
    def budget_remaining(self) -> float:
        """Remaining daily budget."""
        return max(0.0, self.daily_budget_usd - self.daily_cost)

    def get_summary(self) -> dict:
        """Get cost summary for monitoring."""
        with self._lock:
            # Aggregate by model
            by_model: Dict[str, float] = {}
            by_task: Dict[str, float] = {}
            for entry in self._cost_history:
                model = entry.get("model", "unknown")
                task = entry.get("task_type", "unknown")
                cost = entry.get("cost", 0)
                by_model[model] = by_model.get(model, 0) + cost
                by_task[task] = by_task.get(task, 0) + cost

            return {
                "daily_cost": self._daily_cost,
                "daily_budget": self.daily_budget_usd,
                "budget_remaining": self.budget_remaining,
                "is_over_budget": self.is_over_budget,
                "by_model": by_model,
                "by_task": by_task,
                "total_calls": len(self._cost_history),
            }


# Global instances
_cost_tracker: Optional[CostTracker] = None
_tracker_lock = threading.Lock()


def get_cost_tracker() -> CostTracker:
    """Get or create the global cost tracker."""
    global _cost_tracker
    if _cost_tracker is None:
        with _tracker_lock:
            if _cost_tracker is None:
                _cost_tracker = CostTracker()
    return _cost_tracker


def estimate_tokens(text: str) -> int:
    """Rough token estimation (4 chars per token average)."""
    return len(text) // 4
