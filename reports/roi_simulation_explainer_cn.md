# ROI 模拟是什么

## 一句话解释

ROI 模拟不是“真实赚了多少钱”，而是基于离线模型圈选结果，在一组明确假设下估计：

- 触达多少人
- 其中大概多少人本来真的会流失
- 如果触达能挽回其中一部分，可能带来多少收益
- 扣掉触达成本和优惠成本后，净收益和 ROI 大概是多少

## 为什么这个项目需要它

当前数据是公开离线数据，没有真实：

- 发券成本
- 短信成本
- 用户客单价
- 真实 uplift
- 真实线上转化

所以不能硬说“项目已经证明带来多少收益”。但完全不谈业务闭环也会让项目显得停在离线指标层面。

ROI 模拟的作用就是：

- 老老实实承认没有真实线上数据
- 但给出一套基于假设的经营估算框架

## 当前脚本里用的公式

对某个策略档位，比如 Top 10% 用户：

1. 先拿离线结果里的 `targeted_users`
2. 再拿 `churn_precision`
3. 估算这批人中真正高风险用户数：

`expected_true_churners = targeted_users * churn_precision`

4. 假设运营触达能挽回其中一部分：

`expected_saved_users = expected_true_churners * uplift_on_true_churners`

5. 再估算收益和成本：

- `expected_contact_cost = targeted_users * contact_cost_per_user`
- `expected_incentive_cost = expected_saved_users * incentive_cost_per_saved_user`
- `expected_gross_profit = expected_saved_users * gross_profit_per_saved_user`
- `expected_net_profit = expected_gross_profit - expected_contact_cost - expected_incentive_cost`
- `expected_roi = expected_net_profit / expected_total_cost`

## 为什么这里需要假设

因为公开数据里没有：

- 每个挽回用户的真实毛利
- 每次短信/Push/发券的真实成本
- 触达后真实 uplift

所以这些值只能按场景假设。

## 当前默认做了哪 3 个情景

- `conservative`
- `base`
- `aggressive`

它们主要区别在于：

- 假设 uplift 大小不同
- 假设单个挽回用户带来的毛利不同
- 假设激励成本不同

## 面试时怎么说才稳

最稳的说法是：

“这部分不是线上真实 ROI，而是离线场景模拟。我用模型的 Top-K 圈选结果乘上业务假设，估计不同运营策略的预期收益，目的是帮助选择更合理的触达规模和预算档位。”

## 这比只报 AUC 好在哪里

因为 AUC 只能说明排序能力，而 ROI 模拟会逼着你回答：

- 触达多少人
- 用什么成本触达
- 预期带来多少增量收益
- 哪个策略档位更可能值得投放

这会让项目更像真实经营建模，而不是停留在离线分类。
