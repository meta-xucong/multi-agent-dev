# 多 Agent 协作开发

一个用于 Codex 的通用开发工作流 Skill：主控定界与协调，开发做最小改动，独立审查凭证据验收。

保留三种职责、一份任务记录、四个步骤，重点解决范围跑偏、过度开发，以及“声称遵守约束但实际没有遵守”的问题。完整规则见 [SKILL.md](SKILL.md)，界面信息位于 [agents/openai.yaml](agents/openai.yaml)。

## 安装与使用

将整个仓库作为 `multi-agent-dev` 文件夹放入 Codex 可发现的个人技能目录。当前官方文档列出的用户级路径为 `~/.agents/skills`；已有安装应沿用其实际目录，不要重复安装同名 Skill。[官方位置与加载说明](https://learn.chatgpt.com/zh-Hans/docs/build-skills)

例如，在 Windows PowerShell 中首次安装：

```powershell
git clone https://github.com/meta-xucong/multi-agent-dev.git "$env:USERPROFILE\.agents\skills\multi-agent-dev"
```

目标目录已存在时不要覆盖，先检查它是否是本仓库的 Git 副本。安装后在 Codex 开发任务中使用：

```text
$multi-agent-dev

开发依据：填写开发文档路径
本次任务：填写任务或章节
硬约束：填写本次必须遵守的限制
```

支持按描述自动匹配，也可以显式调用。新安装或更新未显示时，重启 Codex。[官方调用说明](https://learn.chatgpt.com/zh-Hans/docs/build-skills)

## 获取更新

进入实际安装目录，先运行 `git status --short` 检查本地改动。工作区干净时，执行：

```text
git pull --ff-only
```

有本地改动、远端不符或分支分叉时，先核对并处理差异，不强制覆盖、不重置历史。只复制文件安装的副本没有 Git 更新关系。

## 维护与升级

在本仓库的本地副本中修改规则；只在需要调整名称、描述或默认提示时修改 `agents/openai.yaml`。提交前检查实际差异、敏感信息和 Skill 格式，并用与本次修改相关的真实场景验证行为。

确认后，仓库维护者可以提交并推送：

```text
git diff --check
git diff
git add -- SKILL.md agents/openai.yaml README.md .gitignore
git commit -m "docs: refine development workflow"
git push origin main
```

仅暂存实际需要发布的文件；新增支持文件时逐项审查后再加入。不要向这个公开仓库提交具体项目代码、私有需求、审计日志、密钥或账户配置。

## 边界

这是工作方法，不是权限隔离系统或自动合规证明器。它不替代项目规则，不自动授权部署、付费调用或 Git 操作；独立审查需要运行环境提供相应能力。格式校验通过也不代表真实开发效果已被完整验证。
