# 第 6 课：旧版报告和新版结果怎么区分

## 为什么一定要区分

因为这个项目不是一次性定型的，中间经历了：

- baseline 版
- recent_active 版
- strict 版

如果你把不同版本的定义和结果混着讲，面试时会很容易说乱。

## 旧版材料主要是什么

下面这些文档主要是 `2026-04-09` 左右生成的历史材料：

- `historical_reports/synerise_project_complete_guide.docx`
- `historical_reports/synerise_project_report.docx`
- `interview_materials/synerise_interview_3min_brief.docx`
- `interview_materials/synerise_interview_question_bank.docx`
- `interview_materials/synerise_interview_quick_reference.docx`

这些材料的价值是：

- 帮你理解项目怎么搭起来
- 帮你理解 baseline 和 recent_active 两种早期版本
- 帮你了解最初的讲法

## 旧版材料里最容易让你混淆的点

- 很多地方写的是旧版 `67` 个特征
- 很多地方讨论的是 `historical_buyers` 或 `recently_active_buyers`
- churn 旧定义通常是“未来 14 天不买就算 churn”

这些都不是错，只是不是你现在最该背的主版本。

## 最新版 strict 结果是什么

最新版是 `2026-04-12` 跑出来的 strict 版，关键文件在：

- `latest_strict_outputs/synerise_strict_feature_metadata.json`
- `latest_strict_outputs/synerise_strict_best_model_test_metrics.csv`
- `latest_strict_outputs/synerise_strict_xgboost_rolling_backtest_summary.csv`
- `latest_strict_outputs/synerise_strict_xgboost_test_topk_strategy.csv`

## strict 版和旧版最大的区别

### active user

旧版更宽：

- `historical_buyers`
- `recently_active_buyers`

strict 版更严：

- `recent_engaged_buyers`

### churn

旧版更宽：

- 未来 14 天没买就算 churn

strict 版更严：

- 未来 14 天没买
- 并且未来活跃天数不超过 1 天

### 特征

旧版主打：

- `67` 个特征

strict 版主打：

- `100` 个特征
- 加入更多趋势特征

### 结果风格

旧版：

- 正例率高
- 某些指标看起来很高，但任务定义偏宽

strict 版：

- 任务更合理
- 结果更健康
- 更适合作为面试主版本

## 你现在应该怎么用这些材料

最推荐的方法：

1. 用历史报告理解项目背景和演化过程
2. 用 strict 版结果背最新版数字
3. 用面试材料练表达

## 你现在真正该背哪一套

面试主版本请优先背 strict 版：

- 样本数 `748,347`
- 特征数 `100`
- XGBoost `AUC = 0.816`
- Top 10% `lift = 1.71`
- rolling backtest `AUC mean = 0.806`

旧版只需要知道它存在、知道为什么后来要升级，不需要把它当主结果背。

## 这一课你应该记住什么

- 历史报告不是废的，它负责讲过程
- strict 版不是取代全部历史，而是你现在更该讲的主版本
- 面试时不要混用旧版和新版数字
