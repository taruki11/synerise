# Git 和 GitHub 最短上手

## 先分清楚

- `git`：本地版本管理工具，用来记录代码历史、查看变更、回退版本、做分支
- `GitHub`：远程托管平台，用来备份仓库、展示项目、协作和投递面试项目

你可以只用 `git` 不传 GitHub。
但如果这是面试项目，建议最终传到 GitHub。

## 这台机器当前状态

当前环境里没有可用的 `git` 命令，所以我没法直接替你初始化仓库或推送远程。

你装好 git 后，进入项目根目录，按下面顺序执行即可。

## 最短命令流

```powershell
git init
git add .
git commit -m "Initialize Synerise churn project"
```

如果你已经在 GitHub 上新建了空仓库，再继续：

```powershell
git branch -M main
git remote add origin <你的仓库地址>
git push -u origin main
```

## 最常用的 6 个命令

```powershell
git status
git add .
git commit -m "your message"
git log --oneline
git diff
git push
```

## 这个项目建议怎么传

- 传代码、脚本、README、报告 markdown
- 不传 `data/raw/`、`data/processed/`、模型文件和大体积产物
- 当前 `.gitignore` 已经基本帮你排除了这些内容

## 面试时怎么说

可以直接说：

“我把项目代码和文档托管在 GitHub，上面保留了完整工程结构和实验说明；数据和模型文件因为体积较大没有直接上传，而是通过 README 提供复现命令。”
