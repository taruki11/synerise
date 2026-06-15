# Synerise Churn Prediction

User-level churn prediction project built on the official **Synerise RecSys 2025** e-commerce behavior dataset.

This project uses a 30-day observation window to predict whether an active user will churn in the next 14 days. Beyond standard offline classification, it also includes stricter business-ready churn definitions, rolling backtests, Top-K targeting analysis, ROI simulation, and an A/B test plan.

## Why This Repo

- Uses a real large-scale e-commerce event log instead of toy CSV data
- Builds samples at the `client_id + snapshot_date` level with strict time-based splitting
- Uses `DuckDB + Parquet` to aggregate large raw logs efficiently
- Compares `Logistic Regression`, `Random Forest`, `LightGBM`, and `XGBoost`
- Extends the project from offline modeling to strategy analysis and retention targeting

## Task Definition

- Sample unit: `client_id + snapshot_date`
- Observation window: past `30` days
- Prediction window: next `14` days
- Active user definition: at least one historical purchase in the observation window, plus recent engagement in the last `7` days
- Churn definition: no `product_buy` in the next 14 days and future activity spans at most `1` active day

Older and wider label definitions are also kept in the repo for comparison experiments.

## Final Strict-Version Results

The main portfolio version uses the stricter label setting: `recent_engaged_buyers + no_buy_and_low_future_activity`.

| Metric | Value |
|---|---:|
| Sample rows | 748,347 |
| Features | 100 |
| Best model | XGBoost |
| Test AUC | 0.816 |
| Test PR-AUC | 0.838 |
| Test F1 | 0.775 |
| Top 10% churn precision | 0.943 |
| Top 10% lift | 1.71 |
| Rolling backtest AUC mean | 0.806 |

## Pipeline Overview

```text
Raw parquet logs
  -> active user filtering by snapshot
  -> 30-day feature aggregation with DuckDB
  -> 14-day future-label construction
  -> strict train/valid/test split by time
  -> model comparison
  -> Top-K threshold strategy analysis
  -> ROI simulation and A/B plan
```

## Repository Structure

```text
.
|-- README.md
|-- requirements.txt
|-- docs/
|   `-- PORTFOLIO_GUIDE.md
|-- scripts/
|   |-- run_pipeline.py
|   |-- run_rolling_backtest.py
|   |-- run_strategy_analysis.py
|   `-- run_roi_simulation.py
|-- src/
|   |-- feature_engineering.py
|   |-- train.py
|   |-- evaluate.py
|   |-- backtest.py
|   |-- strategy_analysis.py
|   `-- roi_analysis.py
`-- reports/
    `-- markdown documentation and interview materials
```

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the main pipeline:

```bash
python scripts/run_pipeline.py --dataset-root data/raw/synerise_dataset --output-prefix synerise_strict
```

Run rolling backtest:

```bash
python scripts/run_rolling_backtest.py --feature-table data/processed/synerise_strict_feature_table.parquet
```

Run strategy analysis:

```bash
python scripts/run_strategy_analysis.py --predictions-path reports/synerise_strict_predictions.csv
```

Run ROI simulation:

```bash
python scripts/run_roi_simulation.py
```

## Documentation Guide

- Project walkthrough: [reports/synerise_project_complete_guide.md](reports/synerise_project_complete_guide.md)
- Portfolio navigation: [docs/PORTFOLIO_GUIDE.md](docs/PORTFOLIO_GUIDE.md)
- 3-minute interview brief: [reports/synerise_interview_3min_brief.md](reports/synerise_interview_3min_brief.md)
- ROI explanation: [reports/roi_simulation_explainer_cn.md](reports/roi_simulation_explainer_cn.md)
- A/B test plan: [reports/ab_test_plan_strict_cn.md](reports/ab_test_plan_strict_cn.md)

## Notes

- The public repo does **not** track raw data, processed feature tables, model binaries, large generated CSV or JSON outputs, or Word exports.
- Those artifacts remain local for offline experimentation, while GitHub stays focused on code and readable documentation.
- Most interview-facing documentation is written in Chinese because the project was prepared for internship applications in the Chinese market.
