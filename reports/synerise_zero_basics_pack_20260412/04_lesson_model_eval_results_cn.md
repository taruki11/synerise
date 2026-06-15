# 第 4 课：模型、指标和结果怎么理解

## 一共用了哪些模型

这个项目主要对比了 4 个模型：

- Logistic Regression
- Random Forest
- LightGBM
- XGBoost

## 为什么要这 4 个模型

### Logistic Regression

作用：

- 线性 baseline
- 方便看一个简单模型能做到什么程度

### Random Forest

作用：

- 传统树模型 baseline
- 用来验证非线性特征是否有用

### LightGBM 和 XGBoost

作用：

- 表格数据里的主力模型
- 很适合这种人工聚合特征很多的任务

## 看哪些指标

这里不能只看 Accuracy。

主要看：

- `AUC`
- `PR-AUC`
- `Precision`
- `Recall`
- `F1`
- `Top-K recall`
- `lift`

## 这些指标你怎么用人话解释

- `AUC`：模型整体排序能力强不强
- `PR-AUC`：在正负样本不平衡时，更关注正类识别效果
- `Precision`：被模型圈出来的人里，有多少真的是流失
- `Recall`：真实流失用户里，有多少被模型抓到
- `F1`：Precision 和 Recall 的平衡
- `Top-K`：只圈最高风险的一部分用户时效果怎么样
- `lift`：模型筛出来的人，相对整体平均水平，风险浓度提高了多少倍

## 为什么最新 strict 版更值得背

旧 baseline 版的一个问题是：

- 正例率太高
- 会导致很多指标看起来很漂亮，但业务上解释不够硬

strict 版把 active user 和 churn 定义都收紧之后，任务更合理，也更像真实经营场景。

## 最新 strict 版的核心结果

这才是你现在应该优先背的结果。

数据口径：

- 样本数：`748,347`
- 特征数：`100`
- snapshot 数：`9`
- 正例率：`0.5518`

最佳模型：

- `XGBoost`

测试集 refit 结果：

- `AUC = 0.816`
- `PR-AUC = 0.838`
- `Precision = 0.732`
- `Recall = 0.823`
- `F1 = 0.775`

rolling backtest：

- 测试集 `AUC mean = 0.806`
- 测试集 `PR-AUC mean = 0.844`
- 测试集 `F1 mean = 0.788`

Top-K：

- Top 10% 用户 `lift = 1.71`
- Top 10% 用户 `churn_precision = 0.943`

## 这些结果应该怎么讲

最稳的讲法是：

- 模型有不错的整体排序能力
- 在多个时间折上表现相对稳定
- 如果业务只触达风险最高的 10% 用户，模型筛出来的人群流失密度明显高于整体平均水平

这样讲比只背一个 AUC 更像真实业务项目。

## 为什么 XGBoost 最好

因为这个任务是典型表格二分类问题：

- 人工聚合特征多
- 非线性关系强
- 特征之间有交互

XGBoost 对这类问题通常表现稳定，所以最终成为最优模型是很合理的。

## 旧版结果你要不要记

可以知道，但不要主打。

原因：

- 旧版结果帮助你理解项目演化过程
- strict 版更适合作为面试主版本

## 这一课你应该记住什么

- 最优模型是 XGBoost
- strict 版比旧 baseline 更适合拿去面试
- 重点不是单个分数，而是“时间稳定性 + Top-K 业务价值”
