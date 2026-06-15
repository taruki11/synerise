from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RoiScenario:
    name: str
    contact_cost_per_user: float
    incentive_cost_per_saved_user: float
    gross_profit_per_saved_user: float
    uplift_on_true_churners: float


DEFAULT_SCENARIOS = [
    RoiScenario(
        name="conservative",
        contact_cost_per_user=0.5,
        incentive_cost_per_saved_user=12.0,
        gross_profit_per_saved_user=120.0,
        uplift_on_true_churners=0.03,
    ),
    RoiScenario(
        name="base",
        contact_cost_per_user=0.5,
        incentive_cost_per_saved_user=15.0,
        gross_profit_per_saved_user=180.0,
        uplift_on_true_churners=0.05,
    ),
    RoiScenario(
        name="aggressive",
        contact_cost_per_user=0.5,
        incentive_cost_per_saved_user=18.0,
        gross_profit_per_saved_user=240.0,
        uplift_on_true_churners=0.08,
    ),
]


REALISTIC_ECOMMERCE_SCENARIOS = [
    RoiScenario(
        name="realistic_tight",
        contact_cost_per_user=0.6,
        incentive_cost_per_saved_user=20.0,
        gross_profit_per_saved_user=55.0,
        uplift_on_true_churners=0.01,
    ),
    RoiScenario(
        name="realistic_base",
        contact_cost_per_user=0.6,
        incentive_cost_per_saved_user=22.0,
        gross_profit_per_saved_user=80.0,
        uplift_on_true_churners=0.02,
    ),
    RoiScenario(
        name="realistic_strong",
        contact_cost_per_user=0.6,
        incentive_cost_per_saved_user=28.0,
        gross_profit_per_saved_user=120.0,
        uplift_on_true_churners=0.03,
    ),
]


SCENARIO_PRESETS: dict[str, list[RoiScenario]] = {
    "default": DEFAULT_SCENARIOS,
    "realistic_ecommerce": REALISTIC_ECOMMERCE_SCENARIOS,
}


def get_scenarios_for_preset(preset: str) -> list[RoiScenario]:
    if preset not in SCENARIO_PRESETS:
        raise ValueError(f"Unsupported scenario preset: {preset}")
    return SCENARIO_PRESETS[preset]


def _expected_roi_rows(
    strategy_frame: pd.DataFrame,
    scenarios: list[RoiScenario],
    strategy_kind: str,
) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for _, row in strategy_frame.iterrows():
        targeted_users = float(row["targeted_users"])
        churn_precision = float(row["churn_precision"])
        expected_true_churners = targeted_users * churn_precision

        if strategy_kind == "top_k":
            strategy_value = float(row["top_k_pct"])
            strategy_label = f"top_{int(round(strategy_value * 100))}pct"
        else:
            strategy_value = float(row["threshold"])
            strategy_label = f"threshold_{strategy_value:.2f}"

        for scenario in scenarios:
            expected_saved_users = expected_true_churners * scenario.uplift_on_true_churners
            contact_cost = targeted_users * scenario.contact_cost_per_user
            incentive_cost = expected_saved_users * scenario.incentive_cost_per_saved_user
            gross_profit = expected_saved_users * scenario.gross_profit_per_saved_user
            total_cost = contact_cost + incentive_cost
            net_profit = gross_profit - total_cost
            roi = net_profit / total_cost if total_cost > 0 else np.nan
            break_even_saved_users = contact_cost / max(
                scenario.gross_profit_per_saved_user - scenario.incentive_cost_per_saved_user,
                1e-9,
            )
            rows.append(
                {
                    "strategy_kind": strategy_kind,
                    "strategy_label": strategy_label,
                    "strategy_value": strategy_value,
                    "targeted_users": int(targeted_users),
                    "churn_precision": churn_precision,
                    "expected_true_churners": expected_true_churners,
                    "scenario": scenario.name,
                    "contact_cost_per_user": scenario.contact_cost_per_user,
                    "incentive_cost_per_saved_user": scenario.incentive_cost_per_saved_user,
                    "gross_profit_per_saved_user": scenario.gross_profit_per_saved_user,
                    "uplift_on_true_churners": scenario.uplift_on_true_churners,
                    "expected_saved_users": expected_saved_users,
                    "expected_contact_cost": contact_cost,
                    "expected_incentive_cost": incentive_cost,
                    "expected_total_cost": total_cost,
                    "expected_gross_profit": gross_profit,
                    "expected_net_profit": net_profit,
                    "expected_roi": roi,
                    "break_even_saved_users": break_even_saved_users,
                }
            )
    return pd.DataFrame(rows)


def run_roi_simulation(
    reports_dir: Path,
    output_prefix: str,
    model_name: str = "xgboost",
    scenarios: list[RoiScenario] | None = None,
    scenario_preset: str = "default",
) -> dict[str, str]:
    reports_dir = Path(reports_dir)
    scenarios = get_scenarios_for_preset(scenario_preset) if scenarios is None else scenarios

    topk_path = reports_dir / f"{output_prefix}_{model_name}_test_topk_strategy.csv"
    threshold_path = reports_dir / f"{output_prefix}_{model_name}_threshold_strategy_summary.csv"

    topk = pd.read_csv(topk_path)
    threshold = pd.read_csv(threshold_path)

    threshold_for_roi = threshold.rename(columns={"precision": "churn_precision"})[
        ["threshold", "targeted_users", "churn_precision", "strategy"]
    ].copy()

    topk_roi = _expected_roi_rows(topk, scenarios=scenarios, strategy_kind="top_k")
    threshold_roi = _expected_roi_rows(threshold_for_roi, scenarios=scenarios, strategy_kind="threshold")
    roi = pd.concat([topk_roi, threshold_roi], ignore_index=True)

    suffix = "" if scenario_preset == "default" else f"_{scenario_preset}"
    roi_path = reports_dir / f"{output_prefix}_{model_name}_roi_simulation{suffix}.csv"
    roi.to_csv(roi_path, index=False)

    summary = (
        roi.sort_values(["scenario", "expected_net_profit", "expected_roi"], ascending=[True, False, False])
        .groupby("scenario", as_index=False)
        .head(3)
        .reset_index(drop=True)
    )
    summary_path = reports_dir / f"{output_prefix}_{model_name}_roi_summary{suffix}.csv"
    summary.to_csv(summary_path, index=False)

    return {
        "roi_path": str(roi_path),
        "summary_path": str(summary_path),
    }
