from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class PipelineConfig:
    dataset_root: Path
    processed_dir: Path = Path("data/processed")
    reports_dir: Path = Path("reports")
    figures_dir: Path = Path("reports/figures")
    models_dir: Path = Path("models")
    observation_days: int = 30
    label_days: int = 14
    window_days: List[int] = field(default_factory=lambda: [1, 3, 7, 14, 30])
    snapshot_step_days: int = 14
    max_snapshots: int | None = None
    sample_frac: float | None = None
    random_state: int = 42
    output_prefix: str = "synerise_churn"
    active_user_definition: str = "recent_engaged_buyers"
    churn_definition: str = "no_buy_and_low_future_activity"

    def ensure_directories(self) -> None:
        for directory in (
            self.processed_dir,
            self.reports_dir,
            self.figures_dir,
            self.models_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
