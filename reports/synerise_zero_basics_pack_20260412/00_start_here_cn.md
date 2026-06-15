# Synerise 项目学习包使用说明

## 这是什么

这是一套按“从 0 开始搞懂项目”整理的学习包。

目标不是让你一次看完所有历史文件，而是让你按顺序理解：

- 这个项目到底要解决什么问题
- 样本和标签是怎么定义的
- 特征是怎么做出来的
- 模型和指标应该怎么看
- 旧版报告和最新版结果有什么区别
- 面试时应该怎么讲，哪些地方不能讲错

## 你先看哪几个文件

建议按下面顺序看：

1. `01_lesson_project_goal_and_data_cn.docx`
2. `02_lesson_sample_label_split_cn.docx`
3. `03_lesson_feature_engineering_cn.docx`
4. `04_lesson_model_eval_results_cn.docx`
5. `05_lesson_interview_story_cn.docx`
6. `06_old_vs_new_report_map_cn.docx`

如果你只想先抓主线，先看前四个就够了。

## 旧版和新版怎么区分

这个项目现在有两层材料：

- 历史报告：2026-04-09 左右生成，主要对应 baseline 版和 recent_active 版
- 最新版结果：2026-04-12 生成，主要对应 strict 版，也是你现在更应该背的版本

简单说：

- 历史报告更适合帮你理解“项目是怎么一步步做出来的”
- strict 版更适合你面试时背结果，因为任务定义更合理、指标更健康

## strict 版为什么更重要

最新版 strict 版的默认定义更严格：

- active user：`recent_engaged_buyers`
- churn：`no_buy_and_low_future_activity`

strict 版的核心结果是：

- 样本数：`748,347`
- 特征数：`100`
- XGBoost `test_refit AUC = 0.816`
- `PR-AUC = 0.838`
- `F1 = 0.775`
- Top 10% 用户 `lift = 1.71`
- rolling backtest 测试集 `AUC mean = 0.806`

这比旧 baseline 版更适合作为面试主版本。

## 你不会打开 Markdown 怎么办

你现在不用硬学 Markdown。

最简单的方法：

- 直接打开同名的 `.docx` 文件，用 Word 或 WPS 看

如果以后你想看 `.md`：

- PyCharm 可以直接打开
- VS Code 可以直接打开
- Typora 也可以
- 实在不行，记事本也能打开，只是排版没那么舒服

## 文件夹结构怎么理解

- 当前目录：我为你新整理的“零基础学习包”
- `historical_reports/`：旧版完整报告和过程报告
- `latest_strict_outputs/`：strict 版的关键结果文件
- `interview_materials/`：旧版面试材料和速查材料

## 你现在最应该记住的一句话

这个项目不是推荐排序项目，而是一个基于真实电商行为日志的用户流失预测项目，目标是识别未来 14 天可能停止购买的用户，给运营提供优先干预名单。
