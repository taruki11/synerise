# Synerise strict 版项目总讲稿（含 ROI 与 A/B）

## 这份稿子的定位

这是一版适合面试主讲的总讲稿，重点把 4 件事串起来：

- 严格时序用户流失预测
- 大规模日志特征工程
- 离线模型与 Top-K 圈选
- ROI 模拟与 A/B 设计

## 90 秒版本

我做的是一个基于官方 Synerise 电商行为日志的用户流失预测项目，不是推荐排序。任务目标是用用户过去 30 天的行为，预测未来 14 天会不会停止购买，从而给运营提供优先召回名单。

这套数据是 6 个月真实零售行为日志，总量大约 2.25 亿条，其中 `page_visit` 接近 2 亿行，所以项目一个核心难点不是调模型，而是怎么把原始 parquet 日志稳定地聚合成用户级特征表。这里我用了 DuckDB on Parquet，直接用 SQL 对原始数据做多时间窗聚合，而不是把全量数据先读进 pandas。

样本单位是 `client_id + snapshot_date`。我严格按时间切分，不做随机切分；特征主要包括 1/3/7/14/30 天行为频次、recency、活跃天数、SKU 和类目多样性、价格统计、漏斗转化以及趋势特征。后面我又把 active user 和 churn 定义收紧成 strict 版，让任务更接近真实经营场景。

最终 strict 版下，XGBoost 测试集 `AUC = 0.816`、`PR-AUC = 0.838`、`F1 = 0.775`，Top 10% 高风险用户的 `lift` 大约是 `1.71`。在这基础上，我又补了 ROI 情景模拟和 A/B 实验方案，让项目不只停留在离线分类，而是能回答“应该触达多少人、值不值得投放、如果上线怎么验证 uplift”。

## 3 分钟主线版本

我做的是一个用户级 14 天流失预测项目，数据来自官方 Synerise RecSys 2025 数据集。虽然这个数据集来自推荐系统比赛，但我没有去做候选召回或排序，而是把它用在经营建模场景，目标是识别未来 14 天可能停止购买的用户。

数据层面，这套日志大约有 2.25 亿条原始行为，包括 `page_visit`、`search_query`、`add_to_cart`、`remove_from_cart` 和 `product_buy`，另外还有 `product_properties` 商品属性表。由于 `page_visit` 接近 2 亿行，直接用 pandas 做全量特征聚合会有明显的内存和速度问题，所以我这里用 DuckDB on Parquet 直接写 SQL 聚合。这个工程处理其实是项目非常重要的一部分。

在样本设计上，我把每一行样本定义成 `client_id + snapshot_date`。对每个 snapshot，用过去 30 天做特征，用未来 14 天打标签。为了避免时间泄漏，全流程都按时间顺序切 train、valid、test，不做随机切分。strict 版里，我把 active user 定义成 `recent_engaged_buyers`，要求用户观察窗内至少买过一次，并且最近 7 天至少还有一次访问、加购或购买；churn 定义成 `no_buy_and_low_future_activity`，要求未来 14 天不但没买，而且未来活跃天数不超过 1 天才算流失。

特征工程上，我主要做了 4 大类。第一类是多时间窗频次特征，比如 1/3/7/14/30 天的浏览、加购、购买和搜索次数。第二类是 recency 和活跃度，比如最近一次访问距今天数、活跃天数、购买天数。第三类是商品和漏斗相关特征，比如 SKU/类目多样性、价格统计、buy per cart、buy per visit。第四类是趋势特征，比如最近 7 天和前 23 天相比，行为是在变活跃还是在衰减。strict 版最终一共是 100 个特征。

模型上我对比了 Logistic Regression、Random Forest、LightGBM 和 XGBoost，最终 XGBoost 最优。strict 版测试集 refit 指标大约是 `AUC 0.816`、`PR-AUC 0.838`、`F1 0.775`。除了单次切分结果，我还做了 rolling backtest，测试折 `AUC mean` 大约是 `0.806`，说明模型在多个时间片上相对稳定。另外，Top 10% 高风险用户的 `churn_precision` 约 `0.943`，`lift` 约 `1.71`，说明模型对高风险圈选是有业务价值的。

考虑到公开数据没有真实线上触达成本和订单毛利，我没有硬说自己做了真实 ROI，而是补了一套离线 ROI 情景模拟。做法是把不同触达档位下的 `targeted_users` 和 `churn_precision`，跟假设的触达成本、激励成本、单用户毛利和 uplift 结合起来，估算预期净收益和 ROI。然后我又设计了一套 A/B 实验方案，核心是针对 Top-K 高风险用户做 Treatment / Control 对照，验证 14 天复购 uplift 是否真实存在。这样项目就从离线分类器，往经营策略闭环又推进了一步。

## 最安全的 ROI 讲法

面试时建议你直接这么说：

“当前项目基于公开离线数据，没有真实流量、发券成本和用户毛利，所以我没有把 ROI 说成真实线上收益。我做的是场景模拟：把模型圈选精度、预算约束和 uplift 假设结合起来，估算不同触达规模下的预期净收益与 ROI，目的是辅助运营确定更合理的触达档位。” 

## A/B 设计怎么讲

最稳的讲法是：

“虽然我没有真实线上实验环境，但我补了一版上线方案。最直接的实验是选 Top 10% 高风险用户做 Treatment / Control 分组，Treatment 发券或 Push，Control 不触达，主指标看 14 天复购率 uplift，护栏指标看触达成本、退订率和券成本。这样能验证模型圈到的高风险用户，是否真的值得被经营动作干预。” 

## 如果面试官质疑‘你没有真实线上实验’

你可以这样回答：

“是的，我没有把公开离线项目包装成真实线上项目。我的处理方式是把边界讲清楚：没有真实线上流量，就不声称做过真实 ROI 和 A/B；但为了让项目更贴近业务落地，我补了 ROI 情景模拟和 A/B 设计，这样至少能把离线指标和经营动作连起来。” 

## 你现在最该记住的 6 个数字

- 样本数：`748,347`
- 特征数：`100`
- XGBoost `AUC = 0.816`
- `PR-AUC = 0.838`
- `F1 = 0.775`
- Top 10% `lift = 1.71`

## 相关材料

- `reports/roi_simulation_explainer_cn.docx`
- `reports/roi_simulation_strict_summary_cn.docx`
- `reports/ab_test_plan_strict_cn.docx`
- `reports/synerise_strict_xgboost_roi_summary_realistic_ecommerce.csv`
