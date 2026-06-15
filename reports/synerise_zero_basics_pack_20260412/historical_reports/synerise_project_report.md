# Synerise Churn Project Report

Source of truth: this Markdown file is the canonical running report for the project.
Word export: `reports/synerise_project_report.docx` is generated from this file and should be refreshed after major updates.
Maintenance rule: all future project changes, fixes, results, and noteworthy decisions should be appended to this report.

## Report Status

- Last updated: 2026-04-08
- Workspace: `D:\Pycharm_workplace\新建文件夹`
- Project: Synerise RecSys 2025 user-level 14-day churn prediction
- Current status: official raw dataset extracted, baseline and stricter active-user experiments completed, threshold and top-k strategy analysis completed

## Project Goal

Build a user-level churn prediction project on the official Synerise RecSys 2025 raw dataset.

Task definition used in the implemented pipeline:
- Sample unit: `client_id`
- Observation window: past 30 days
- Prediction window: next 14 days
- Label: `churn = 1` if the active user has no `product_buy` in the next 14 days, else `0`

Important implementation note:
- For the official raw-data run, the active user definition was aligned to users who had at least one historical `product_buy` before the snapshot.
- This choice was made because it is closer to the official churn framing and keeps the official raw run computationally tractable.

## Dataset Acquisition Log

### Official raw archive

- Official source page: <https://recsys.synerise.com/data-set>
- Official raw archive: <https://data.recsys.synerise.com/dataset/synerise_dataset.tar.gz>
- Archive size after successful user download: `2,062,884,710` bytes

### Download history

- Multiple direct programmatic downloads were attempted from the official host on 2026-04-07.
- The official host repeatedly terminated the connection mid-download.
- The host did not support HTTP byte-range resume, so interrupted downloads could not be resumed safely.
- A validation-based downloader was implemented to avoid treating partial files as complete files.
- The user later downloaded the complete archive manually and placed it in `data/`.
- The archive was then moved to `data/raw/synerise_dataset.tar.gz` and validated successfully as a readable tar archive.

### Extraction

- Extracted location: `data/raw/synerise_dataset`
- Extracted files confirmed:
- `product_buy.parquet`
- `add_to_cart.parquet`
- `remove_from_cart.parquet`
- `page_visit.parquet`
- `search_query.parquet`
- `product_properties.parquet`

## Raw Dataset Observations

The official raw dataset differs from the earlier planning assumptions in a few important ways:

- `search_query.parquet` contains raw string queries, not embedding vectors.
- `product_properties.parquet` contains `sku`, `category`, `price`, and `name`.
- `page_visit.parquet` is extremely large and contains about `199,451,980` rows.

Observed row counts:
- `product_buy`: `2,318,502`
- `add_to_cart`: `7,541,117`
- `remove_from_cart`: `2,688,894`
- `page_visit`: `199,451,980`
- `search_query`: `13,223,769`
- `product_properties`: `1,534,050`

## Engineering Changes Implemented

### Initial project scaffolding

The project was created from scratch with the following components:
- dataset download module
- feature engineering module
- model training module
- evaluation module
- EDA module
- mock-data generator
- pipeline runner
- interview summary notes

### Model expansion

The original implementation included:
- Logistic Regression
- Random Forest
- LightGBM

Then XGBoost was added as an additional model and integrated into the same training and evaluation pipeline.

### Memory and scalability fixes for the official raw dataset

A direct pandas-based full read of `page_visit.parquet` failed with memory errors.
To solve this, the feature pipeline was refactored substantially:

- Raw feature engineering was rewritten to use DuckDB over parquet files.
- Aggregations are now computed in SQL directly on the parquet data.
- Search features were adapted to real raw-data fields using query string statistics instead of embeddings.
- EDA was rewritten to read parquet metadata for event counts instead of loading full event tables.
- Training was guarded with model-specific row caps to keep large-model fitting stable on the current machine.

### Search feature change

Because the raw dataset has text queries rather than embeddings, the implemented search features now include:
- search counts over 1/3/7/14/30 days
- search recency
- average query length
- average query word count
- search-to-cart within 1 day count
- search-to-buy within 1 day count

## Official Feature Table

Official full-run feature table:
- File: `data/processed/synerise_official_feature_table.parquet`
- Rows: `4,281,892`
- Feature count: `67`
- Snapshot count: `9`

Split sizes:
- train: `1,667,886`
- valid: `1,171,906`
- test: `1,442,100`

Observed label rate:
- churn positive rate: about `0.9454`

## Official Model Results

Validation/Test model comparison:

- XGBoost valid: AUC `0.7302`, PR-AUC `0.9735`, F1 `0.9729`
- LightGBM valid: AUC `0.7274`, PR-AUC `0.9731`, F1 `0.8787`
- Logistic Regression valid: AUC `0.7274`, PR-AUC `0.9733`, F1 `0.8675`
- Random Forest valid: AUC `0.7226`, PR-AUC `0.9729`, F1 `0.9067`

- XGBoost test: AUC `0.7327`, PR-AUC `0.9733`, F1 `0.9725`
- LightGBM test: AUC `0.7301`, PR-AUC `0.9729`, F1 `0.8806`
- Logistic Regression test: AUC `0.7303`, PR-AUC `0.9732`, F1 `0.8712`
- Random Forest test: AUC `0.7257`, PR-AUC `0.9727`, F1 `0.9073`

Best refit model:
- Model: XGBoost
- Split: `test_refit`
- AUC: `0.7330`
- PR-AUC: `0.9734`
- Precision: `0.9474`
- Recall: `0.9990`
- F1: `0.9725`
- Top 10% churn recall: `0.1033`

Interpretation note:
- The churn positive rate is very high under this label definition, so PR-AUC is naturally inflated.
- In interviews, AUC, time-based splitting, label definition, and error analysis are better focal points than PR-AUC alone.

## Top Feature Importance From Best Model

Top XGBoost refit features observed:
- `active_days_30d`
- `add_to_cart_days_30d`
- `product_buy_days_30d`
- `add_to_cart_distinct_category_30d`
- `page_visit_days_30d`
- `page_visit_recency_days`
- `product_buy_distinct_sku_30d`
- `search_query_recency_days`
- `page_visit_count_3d`
- `add_to_cart_distinct_sku_30d`

High-level takeaway:
- User activeness, breadth of recent cart behavior, recent purchase depth, and behavioral recency are the strongest churn indicators in the current implementation.

## Key Output Files

Core outputs currently available:
- `data/raw/synerise_dataset.tar.gz`
- `data/raw/synerise_dataset/`
- `data/processed/synerise_official_feature_table.parquet`
- `reports/synerise_official_feature_metadata.json`
- `reports/synerise_official_metrics.csv`
- `reports/synerise_official_best_model_test_metrics.csv`
- `reports/synerise_official_feature_importance_xgboost_refit.csv`
- `reports/synerise_official_xgboost_test_predictions.csv`
- `reports/figures/synerise_official_event_type_share.png`
- `reports/figures/synerise_official_churn_label_distribution.png`
- `reports/interview_talk_track.md`

## Future Update Rule

When the project changes later, append updates in this report instead of creating scattered notes.
Recommended format for future additions:
- date
- what changed
- why it changed
- files affected
- result or impact

## Change Log

### 2026-04-07 - Project initialized

- Created end-to-end churn prediction project structure from an empty workspace.
- Added modules for download, preprocessing, feature engineering, training, evaluation, EDA, and mock-data generation.
- Added LR, RF, LightGBM baselines.

### 2026-04-07 - XGBoost added

- Installed `xgboost` and integrated it into the training registry.
- Updated documentation and interview notes accordingly.

### 2026-04-07 - Official raw data integrated

- Validated and moved the manually downloaded official raw archive into `data/raw/`.
- Extracted the raw dataset and verified expected parquet files.

### 2026-04-07 - Official raw pipeline refactor

- Replaced pandas-heavy full-data feature generation with DuckDB-based parquet SQL aggregation.
- Adapted search features from embedding-based assumptions to real raw query strings.
- Updated EDA to avoid loading very large raw event tables into memory.
- Added model-specific training row caps for stability on large datasets.

### 2026-04-07 - Official full run completed

- Built the official full feature table successfully.
- Trained Logistic Regression, Random Forest, XGBoost, and LightGBM on the official raw dataset.
- Selected XGBoost as the best current model based on validation performance.


## Experiment Update - 2026-04-08

### Active User Definition Comparison

A stricter active-user experiment was added to address the business concern that the original sample definition might be too broad.

Compared definitions:
- `historical_buyers`: user had at least one `product_buy` before the snapshot
- `recently_active_buyers`: user had at least one `product_buy` before the snapshot and at least one `page_visit` / `add_to_cart` / `product_buy` in the observation window

Observed impact:
- Baseline sample rows: `4,281,892`
- Stricter sample rows: `2,423,390`
- Row reduction: `1,858,502`
- Baseline churn positive rate: `0.9461`
- Stricter churn positive rate: `0.9110`
- Positive-rate reduction: `0.0351`

Model comparison takeaway:
- Both definitions still selected XGBoost as the best model.
- Baseline test-refit AUC: `0.7330`
- Stricter test-refit AUC: `0.7066`
- Baseline test-refit F1: `0.9725`
- Stricter test-refit F1: `0.9538`

Interpretation:
- The stricter definition makes the task more business-aligned because the sampled users are behaviorally active near the prediction date, not just historical purchasers.
- It also lowers the churn positive rate, which makes it easier to explain why the earlier label distribution was so extreme.
- The stricter definition reduces sample size materially and lowers AUC somewhat, which is a reasonable trade-off when moving toward a cleaner business definition.

### Threshold Optimization

Threshold analysis was added on the best validation model and then applied to the corresponding test split.

Results:
- Baseline best threshold by validation F1: `0.45`
- Baseline default threshold: `0.50`
- Stricter best threshold by validation F1: `0.45`
- Stricter default threshold: `0.50`

Interpretation:
- In both experiments, the validation-optimal F1 threshold moved only slightly from `0.50` to `0.45`.
- The improvement over the default threshold was very small.
- This suggests the model already ranks most users as high-risk under the current churn definition, so threshold tuning alone is not the most informative business lever.

### Top-K Targeting Strategy

Top-K analysis was added to better answer the operational question: if the business can only intervene on the highest-risk users, how much real churn can be covered?

Stricter active-user definition, XGBoost, test split:
- Top 1% users: precision `0.9738`, churn recall `0.0107`, lift `1.0689`
- Top 5% users: precision `0.9674`, churn recall `0.0531`, lift `1.0619`
- Top 10% users: precision `0.9630`, churn recall `0.1057`, lift `1.0570`

Baseline active-user definition, XGBoost, test split:
- Top 10% users: precision `0.9764`, churn recall `0.1032`, lift `1.0319`

Operational takeaway:
- The stricter active-user definition gives a slightly more meaningful lift over the base churn rate in Top-K targeting.
- Even though absolute churn precision stays high in both settings, the stricter definition is easier to justify to an interviewer because it maps better to a realistic "currently active user" population.
- For interviews, Top-K framing is stronger than threshold-only framing because it sounds like a real CRM or retention workflow.

### New Output Files From This Update

- `reports/active_user_definition_comparison.csv`
- `reports/synerise_official_xgboost_valid_threshold_sweep.csv`
- `reports/synerise_official_xgboost_test_threshold_sweep.csv`
- `reports/synerise_official_xgboost_threshold_strategy_summary.csv`
- `reports/synerise_official_xgboost_test_topk_strategy.csv`
- `reports/synerise_recent_active_metrics.csv`
- `reports/synerise_recent_active_best_model_test_metrics.csv`
- `reports/synerise_recent_active_xgboost_valid_threshold_sweep.csv`
- `reports/synerise_recent_active_xgboost_test_threshold_sweep.csv`
- `reports/synerise_recent_active_xgboost_threshold_strategy_summary.csv`
- `reports/synerise_recent_active_xgboost_test_topk_strategy.csv`

### 2026-04-08 - Active-user and strategy experiments added

- Added configurable active-user definitions to the feature pipeline.
- Ran an official raw-data comparison between `historical_buyers` and `recently_active_buyers`.
- Added validation-based threshold optimization and test-time threshold comparison.
- Added Top-K targeting analysis to support retention-operations storytelling.
- Refreshed the running project report and Word export.

### 2026-04-08 - Interview documentation package added

- Added a full Chinese project guide at `reports/synerise_project_complete_guide.md` and exported `reports/synerise_project_complete_guide.docx`.
- Refreshed the Chinese interview talk track at `reports/interview_talk_track.md` and exported `reports/interview_talk_track.docx`.
- Added an extensive Chinese interview question bank at `reports/synerise_interview_question_bank.md` and exported `reports/synerise_interview_question_bank.docx`.
- The new documentation package covers end-to-end project explanation, the stricter active-user experiment, threshold and top-k strategy storytelling, and a large set of likely interview follow-up questions.

### 2026-04-08 - Final interview-ready materials added

- Added a concise 3-minute memorization script at `reports/synerise_interview_3min_brief.md` and exported `reports/synerise_interview_3min_brief.docx`.
- Added a standard-answer quick reference sheet at `reports/synerise_interview_quick_reference.md` and exported `reports/synerise_interview_quick_reference.docx`.
- The project now has a complete interview document package: full guide, long question bank, talk track, 3-minute brief, and quick-reference answers.
