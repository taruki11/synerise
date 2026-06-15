# 基于 Synerise 2025 电商行为日志的用户流失预测项目完整文档

## 文档定位

- 这份文档是当前项目的总说明，覆盖业务背景、数据、样本标签、特征工程、模型、实验结果、工程实现、面试讲法和复现方式。
- 当前版本基于官方 Synerise RecSys 2025 raw dataset 已完成的正式实验结果生成。
- 建议搭配 `reports/synerise_project_report.md` 一起使用：本文件偏“完整讲述”，运行报告偏“过程留痕”。

## 一句话项目介绍

基于官方 Synerise RecSys 2025 真实电商行为日志，构建用户级 14 天流失预测模型，从 6 个月 raw parquet 数据出发完成大规模特征聚合、时间切分、多模型对比、active user 定义对比和 Top-K 运营策略分析。

## 1. 业务背景与项目目标

- 本项目不做推荐系统排序，而是做增长/经营场景更常见的 churn prediction。
- 目标是识别“当前活跃用户未来 14 天是否会停止购买”，给运营团队提供提前干预名单。
- 业务动作可以是优惠券、短信召回、站内 push、分层运营或会员激活。

## 2. 数据来源与数据规模

- 官方数据页：[Synerise RecSys 2025 Dataset](https://recsys.synerise.com/data-set)
- 数据来源：真实线上零售网站 6 个月行为日志。
- 原始压缩包大小约 1.9 GB，实际落地文件 `data/raw/synerise_dataset.tar.gz` 大小为 2,062,884,710 字节。
- 行为事件总量约 225,224,262 条。

原始表规模如下：

- `page_visit`: 199,451,980
- `search_query`: 13,223,769
- `add_to_cart`: 7,541,117
- `remove_from_cart`: 2,688,894
- `product_buy`: 2,318,502
- `product_properties`: 1,534,050

## 3. 原始数据真实情况与预期差异

- `page_visit.parquet` 远大于其他表，是工程上最主要的瓶颈。
- `search_query.parquet` 里是原始 query 文本，不是 embedding 向量。
- `product_properties.parquet` 里包含 `sku`、`category`、`price`、`name` 等商品元数据。
- 这意味着最初设计里的“搜索 embedding 统计特征”需要落地成“文本长度、词数、搜索后转化”类特征。

## 4. 样本定义、标签定义与时间切分

- 样本单位：`client_id`
- 观察窗口：过去 30 天
- 预测窗口：未来 14 天
- 标签定义：未来 14 天没有任何 `product_buy` 记为 `churn=1`，否则记为 `0`
- 时间切分：严格按 snapshot 时间切分 train / valid / test，不做随机切分
- snapshot 数量：9

为什么一定用时间切分：

- 行为日志数据天然有时间顺序，随机切分会把未来行为模式泄漏到训练阶段。
- 时间切分更贴近线上部署：模型永远只能看到过去，预测未来。
- 这一点是面试里很加分的基础方法论。

## 5. 两种 active user 定义

### 口径 A：historical_buyers

- 定义：用户在 snapshot 之前历史上至少有一次 `product_buy`。
- 作用：更贴近官方 churn framing，也方便构造全量 baseline。

### 口径 B：recently_active_buyers

- 定义：用户在 snapshot 之前历史上至少有一次 `product_buy`，并且观察窗口内至少有一次 `page_visit` / `add_to_cart` / `product_buy`。
- 作用：更接近“当前活跃用户”，业务解释性更强。
## 6. 特征工程设计

### 行为频次特征

- 最近 1/3/7/14/30 天 `page_visit`、`search_query`、`add_to_cart`、`remove_from_cart`、`product_buy` 次数
- 各类行为的天级活跃次数和去重天数

### Recency 与活跃度特征

- 最近一次访问、加购、购买、搜索距 snapshot 多少天
- 30 天活跃天数
- 30 天购买天数
- 30 天加购天数
- 30 天购买去重 SKU 数
- 30 天浏览/加购/购买去重类目数

### 漏斗转化特征

- `add_to_cart / page_visit`
- `product_buy / add_to_cart`
- `product_buy / page_visit`
- `remove_from_cart / add_to_cart`

### 商品属性特征

- 30 天购买价格均值、总和、最大值
- 30 天浏览价格均值、最大值
- 30 天购买/浏览品类数
- 高频购买类目占比

### 搜索行为特征

- 最近 1/3/7/14/30 天搜索次数
- 搜索 recency
- query 平均长度
- query 平均词数
- 搜索后 1 天内加购次数
- 搜索后 1 天内购买次数

- 当前正式训练表维度：4,281,892 行，67 个特征

## 7. 工程实现与踩坑

- 第一版特征工程是 pandas 聚合，到了官方 raw 数据后在 `page_visit.parquet` 上出现明显内存压力。
- 为了稳定处理 2 亿级日志，我把特征工程重写成 DuckDB on Parquet。
- 具体做法是让 DuckDB 直接对 parquet 跑 SQL 聚合，避免把大表完整读进 pandas。
- EDA 也改成更轻量的方式，只读取必要的统计量和汇总结果。
- 模型训练阶段又做了模型级 row cap，保证 RF / XGBoost / LightGBM 在本机上能稳定跑完。

这个点面试里很重要，因为它说明你不是只会“调 sklearn”，而是真正处理过大规模数据的工程约束。

## 8. 模型设计

- Logistic Regression：线性 baseline，稳定、易解释、适合作为参照。
- Random Forest：验证非线性树模型是否优于线性模型。
- XGBoost：强势 boosting 模型，常用于表格数据。
- LightGBM：高效的 GBDT 实现，通常在大规模表格任务上表现稳定。

## 9. 评估指标

- AUC：看排序能力，适合整体比较模型区分度。
- PR-AUC：适合不平衡分类，但要结合基线正例率解读。
- Precision / Recall / F1：看默认阈值下的分类效果。
- Top-10% churn recall：业务资源有限时，更贴近真实圈选场景。

## 10. 正式实验结果

### 10.1 Baseline 口径：historical_buyers

- 样本量：4,281,892
- 特征数：67
- snapshot 数：9
- 流失正例率：94.61%

测试集结果：

- xgboost: AUC 0.7327，PR-AUC 0.9733，Precision 0.9475，Recall 0.9988，F1 0.9725
- lightgbm: AUC 0.7301，PR-AUC 0.9729，Precision 0.9693，Recall 0.8068，F1 0.8806
- logistic_regression: AUC 0.7303，PR-AUC 0.9732，Precision 0.9697，Recall 0.7908，F1 0.8712
- random_forest: AUC 0.7257，PR-AUC 0.9727，Precision 0.9659，Recall 0.8554，F1 0.9073

- 最优 refit 模型：XGBoost，AUC 0.7330，PR-AUC 0.9734，F1 0.9725

### 10.2 更严格口径：recently_active_buyers

- 样本量：2,423,390
- 特征数：67
- snapshot 数：9
- 流失正例率：91.10%

测试集结果：

- xgboost: AUC 0.7058，PR-AUC 0.9525，Precision 0.9137，Recall 0.9974，F1 0.9537
- lightgbm: AUC 0.7036，PR-AUC 0.9518，Precision 0.9491，Recall 0.6779，F1 0.7909
- logistic_regression: AUC 0.6984，PR-AUC 0.9508，Precision 0.9484，Recall 0.6844，F1 0.7950
- random_forest: AUC 0.6959，PR-AUC 0.9507，Precision 0.9431，Recall 0.7546，F1 0.8384

- 最优 refit 模型：XGBoost，AUC 0.7066，PR-AUC 0.9526，F1 0.9538
### 10.3 两种口径对比结论

- 样本量从 4,281,892 降到 2,423,390
- 正例率从 94.61% 降到 91.10%
- XGBoost test_refit AUC 从 0.7330 降到 0.7066
- 结论：更严格口径牺牲了一些数值表现，但换来了更强的业务合理性和更好的解释空间。

## 11. 特征重要性

XGBoost refit 的前 10 个重要特征：

- active_days_30d
- add_to_cart_days_30d
- product_buy_days_30d
- add_to_cart_distinct_category_30d
- page_visit_days_30d
- page_visit_recency_days
- product_buy_distinct_sku_30d
- search_query_recency_days
- page_visit_count_3d
- add_to_cart_distinct_sku_30d

解释思路：

- `active_days_30d`、`page_visit_days_30d` 说明整体活跃度是核心。
- `add_to_cart_days_30d`、`add_to_cart_distinct_category_30d` 说明最近有明确购买意图的用户更不容易流失。
- `product_buy_days_30d`、`product_buy_distinct_sku_30d` 说明最近真实购买深度很关键。
- `page_visit_recency_days`、`search_query_recency_days` 说明行为衰减速度能较好刻画流失风险。

## 12. 新增实验一：更严格 active user 定义对比

这个实验建议你面试时这样讲：

最开始我用了更接近官方定义的 baseline：用户只要在 snapshot 之前历史买过一次就纳入样本。但做完后我发现正例率非常高，所以我担心这个定义过宽，会把一些很久没活跃的历史用户也放进来。于是我追加了一个更严格版本，要求用户历史买过且观察窗内至少还有一次关键行为。这个实验的意义不只是调指标，而是验证样本定义是否真的符合“当前活跃用户”这个业务问题。

你可以补一句定量结果：

- 样本量减少 1,858,502
- 正例率下降 3.51 个百分点
- AUC 下降 0.0264

推荐结论：

- baseline 更贴近挑战任务口径，适合展示“我能对齐公开任务”。
- stricter 口径更贴近业务落地，适合展示“我会质疑标签和样本定义是否合理”。

## 13. 新增实验二：阈值优化与 Top-K 策略

### 阈值优化

- baseline 验证集最优 F1 阈值：0.45
- stricter 验证集最优 F1 阈值：0.45
- 两个实验里最优阈值都只比默认 0.50 略低，收益非常有限。
- 结论：在当前任务设置下，单纯微调阈值不是最有价值的优化方向。

### Top-K 策略

- 更严格口径 Top 5%：precision 0.9674，recall 5.31%，lift 1.0619
- 更严格口径 Top 10%：precision 0.9630，recall 10.57%，lift 1.0570
- baseline 口径 Top 10%：precision 0.9764，recall 10.32%，lift 1.0319

推荐讲法：

- 如果运营只能触达最高风险的 10% 用户，我就优先圈这些人，而不是盯着 0.5 阈值做二分类。
- Top-K 让模型结果更像一个可执行的 CRM 策略，而不是一串静态指标。

## 14. 错误分析怎么讲

- 假阳性：模型预测会流失，但用户其实没有流失。常见原因是用户购买周期本来就长，或者浏览/搜索强但购买延迟。
- 假阴性：模型没识别出流失用户。常见原因是用户在观察窗内仍有访问、搜索、加购，掩盖了真实流失风险。
- 你可以继续按近 30 天购买频次、累计消费、高价值/低价值用户分层，对比 FP/FN 差异。

## 15. 为什么这个项目适合大厂面试

- 数据是真的大，不是玩具数据。
- 问题定义清楚，属于数据挖掘/机器学习常见业务问题。
- 有完整方法链路：数据理解、特征工程、时间切分、模型对比、错误分析、策略分析。
- 有工程难点：DuckDB 替换 pandas，解决 2 亿级日志聚合。
- 有业务化思考：active user 定义对比、阈值优化、Top-K 运营策略。
## 16. 简历项目描述可直接使用

- 基于 Synerise RecSys 2025 官方 raw dataset 构建用户级 14 天流失预测模型，处理 6 个月、2.25 亿级电商行为日志，完成从原始 parquet 到建模评估的全流程。
- 使用 DuckDB on Parquet 重构大规模特征聚合，生成 67 维用户画像特征，并通过时间切分训练 Logistic Regression、Random Forest、XGBoost、LightGBM 四类模型。
- 增加 active user 定义对比、阈值优化与 Top-K 策略分析，使模型从离线评估进一步对接留存运营场景。

## 17. 面试时怎么讲两个新增实验

一句话版本：

- 我不是只停留在跑模型，而是进一步检查样本定义是否合理，并把模型结果翻译成运营可执行的 Top-K 干预策略。

扩展版本：

我新增了两个实验。第一个是 active user 定义对比，因为我发现如果只要求历史买过，样本会过宽，所以我又加了“观察窗内有行为”的严格口径，验证标签分布和模型效果变化。第二个是阈值和 Top-K 分析，因为业务上通常不是对全部用户做干预，而是优先触达最高风险的一小部分用户。结果显示阈值微调收益不大，但 Top-K 策略更适合落地，所以我会把这个模型讲成一个 retention targeting 系统。

## 18. 复现命令

```powershell
python scripts\run_pipeline.py --dataset-root data\raw\synerise_dataset --output-prefix synerise_official --active-user-definition historical_buyers --generate-eda
python scripts\run_pipeline.py --dataset-root data\raw\synerise_dataset --output-prefix synerise_recent_active --active-user-definition recently_active_buyers
python scripts\run_strategy_analysis.py --output-prefix synerise_official
python scripts\run_strategy_analysis.py --output-prefix synerise_recent_active
python scripts\summarize_active_user_definitions.py --prefixes synerise_official synerise_recent_active
```

## 19. 关键产物路径

- `data/processed/synerise_official_feature_table.parquet`
- `data/processed/synerise_recent_active_feature_table.parquet`
- `reports/synerise_official_metrics.csv`
- `reports/synerise_recent_active_metrics.csv`
- `reports/active_user_definition_comparison.csv`
- `reports/synerise_official_xgboost_threshold_strategy_summary.csv`
- `reports/synerise_recent_active_xgboost_threshold_strategy_summary.csv`
- `reports/synerise_recent_active_xgboost_test_topk_strategy.csv`
- `reports/interview_talk_track.md`
- `reports/synerise_interview_question_bank.docx`

## 20. 最后建议

- 面试时先讲业务问题，再讲时间切分，再讲 DuckDB 和特征工程，最后讲两个新增实验。
- 不要一上来堆指标，先让面试官知道你理解的是“留存运营”而不是“比赛刷分”。
- 如果被追问为什么 AUC 没继续刷高，就回答你更重视样本口径合理性和可落地策略，而不是单纯刷离线分数。
