# Synerise strict 版 ROI 模拟结果说明

## 先说结论

当前项目的数据里没有真实：

- 触达成本
- 优惠券成本
- 用户毛利
- 触达 uplift

所以这里的 ROI 不是“真实业务收益”，而是基于离线 Top-K / threshold 圈选结果，加上一组明确假设之后做的情景模拟。

## 当前默认假设

脚本里预设了 3 个场景：

- `conservative`
- `base`
- `aggressive`

差别主要在于：

- 假设触达对真实流失用户的挽回比例不同
- 假设每个被挽回用户带来的毛利不同
- 假设激励成本不同

固定设置是：

- 每触达 1 个用户，触达成本 `0.5`

其余参数在脚本里定义，见 `src/roi_analysis.py`。

## 公式怎么来的

以 Top 10% 用户为例：

1. 先从离线结果拿到：

- `targeted_users`
- `churn_precision`

2. 估算这批人里本来会流失的用户数：

`expected_true_churners = targeted_users * churn_precision`

3. 假设运营能挽回其中一部分：

`expected_saved_users = expected_true_churners * uplift_on_true_churners`

4. 再估算收益和成本：

- `gross_profit = expected_saved_users * gross_profit_per_saved_user`
- `contact_cost = targeted_users * contact_cost_per_user`
- `incentive_cost = expected_saved_users * incentive_cost_per_saved_user`
- `net_profit = gross_profit - contact_cost - incentive_cost`
- `ROI = net_profit / total_cost`

## strict 版当前离线基础

当前 strict 版核心离线结果是：

- XGBoost `AUC = 0.816`
- `PR-AUC = 0.838`
- `F1 = 0.775`
- Top 10% 用户 `churn_precision = 0.943`
- Top 10% 用户 `lift = 1.71`

## ROI 模拟结果怎么看

在当前默认假设下，脚本会同时评估：

- Top 1% / 2% / 5% / 10% / 20%
- threshold 0.50
- threshold 0.45

从当前输出看：

- 如果看 `expected_net_profit`，更大规模触达通常更高，因为覆盖的人更多
- 如果看 `expected_roi`，Top-K 小档位通常更“精”
- 所以真实业务上不能只看 ROI，还要结合预算上限和运营产能

## 当前 strict 版一个好讲的点

如果你面试时不想讲太复杂，最稳的表达是：

- 我先用 Top-K 分析确定高风险圈选能力
- 再在假设触达成本、券成本和单用户毛利的前提下做 ROI 情景模拟
- 目的不是伪造真实收益，而是帮助业务判断“优先触达多少人更划算”

## 最安全的面试表述

“当前项目基于公开离线数据，没有真实线上触达和订单毛利，所以我没有把 ROI 说成真实收益。我做的是场景模拟：把模型的圈选精度、假设 uplift、单用户价值和触达成本结合起来，估算不同触达规模下的预期净收益和 ROI，从而把项目从离线分类推进到经营策略讨论。”

## 相关输出文件

- `reports/synerise_strict_xgboost_roi_simulation.csv`
- `reports/synerise_strict_xgboost_roi_summary.csv`
- `reports/roi_simulation_explainer_cn.docx`
- `reports/ab_test_plan_strict_cn.docx`
