# 基于 Synerise 2025 电商行为日志的用户流失预测项目

这个项目围绕官方 **Synerise RecSys 2025** 数据集实现一个完整的用户级 churn prediction 流水线：从官方数据下载、用户级特征构造、时间切分、模型训练评估，到 EDA 和错误分析。

## 项目目标

- 样本单位：`client_id`
- 观察窗口：过去 30 天
- 预测窗口：未来 14 天
- 当前默认 active user 口径：观察窗口内至少有一次 `product_buy`，且最近 7 天至少有一次 `page_visit` / `add_to_cart` / `product_buy`
- 当前默认 churn 定义：未来 14 天没有任何 `product_buy`，且未来行为活跃天数不超过 1 天，则 `churn=1`
- 兼容旧口径：仍可通过命令行切回更宽松的 active user 和 churn 定义做对比实验
- 当前版本额外加入趋势特征和 rolling backtest，用于评估模型在多个时间切片上的稳定性

## 工程结构

```text
.
├── data/
│   ├── raw/
│   ├── processed/
│   └── sample/
├── models/
├── reports/
│   └── figures/
├── scripts/
│   ├── generate_mock_data.py
│   └── run_pipeline.py
├── src/
│   ├── config.py
│   ├── data_utils.py
│   ├── download_data.py
│   ├── eda.py
│   ├── evaluate.py
│   ├── feature_engineering.py
│   ├── train.py
│   └── utils.py
└── README.md
```

## 快速开始

### 1. 生成一份可运行的本地 mock 数据并验证流水线

```powershell
python scripts/generate_mock_data.py
python scripts/run_pipeline.py --dataset-root data/sample/mock_synerise_dataset --output-prefix mock_run --generate-eda
```

### 2. 下载官方原始数据集

```powershell
python -m src.download_data --variant raw --extract
```

官方来源：

- 数据集页：[Synerise dataset](https://recsys.synerise.com/data-set)
- 原始包直链：[raw version](https://data.recsys.synerise.com/dataset/synerise_dataset.tar.gz)

### 3. 使用官方数据跑完整项目

```powershell
python scripts/run_pipeline.py --dataset-root data/raw/synerise_dataset --output-prefix synerise_raw --generate-eda
```

### 4. 如果机器内存有限

```powershell
python scripts/run_pipeline.py --dataset-root data/raw/synerise_dataset --output-prefix synerise_sample --sample-frac 0.1 --max-snapshots 4 --generate-eda
```

### 5. 显式使用更宽松的旧 baseline 口径

```powershell
python scripts/run_pipeline.py --dataset-root data/raw/synerise_dataset --output-prefix synerise_baseline --active-user-definition historical_buyers --churn-definition no_buy_in_label_window
```

### 6. 运行 rolling backtest

```powershell
python scripts/run_rolling_backtest.py --feature-path data/processed/synerise_raw_feature_table.parquet --output-prefix synerise_raw --model-name xgboost
```

## 输出结果

- `data/processed/<prefix>_feature_table.parquet`：用户级训练表
- `reports/<prefix>_metrics.csv`：LR / RF / XGBoost / LGBM 指标对比
- `reports/<prefix>_best_model_test_metrics.csv`：最佳模型测试集指标
- `reports/<prefix>_feature_metadata.json`：active user / churn 口径与快照统计
- `reports/<prefix>_feature_importance_*.csv`：特征重要性
- `reports/<prefix>_error_profile_*.csv`：错误分析
- `reports/<prefix>_*_rolling_backtest.csv`：rolling backtest 分 fold 指标
- `reports/<prefix>_*_rolling_backtest_summary.csv`：rolling backtest 汇总指标
- `reports/figures/*.png`：EDA 图表
- `models/<prefix>_*.joblib`：训练后的模型

## 面试讲述重点

- 只做用户级 churn prediction，不把项目复杂度带偏到完整推荐系统
- 明确使用时间切分，避免日志数据时间穿越
- 主动收紧 active user 和 churn 定义，避免把问题做得过宽过浅
- 以用户为粒度聚合 1/3/7/14/30 天多窗口行为特征
- 加入趋势特征，刻画短期行为相对中期基线的衰减或回升
- 使用 LR 作为基线，RF/XGBoost/LightGBM 作为表格特征的强基线
- 使用 rolling backtest 验证模型在不同 snapshot 上的稳定性，而不是只看一次切分
- 指标同时覆盖 AUC、PR-AUC、Precision、Recall、F1 和 Top-K churn recall
- 对假阳性 / 假阴性做画像分析，而不是只报一个分数
