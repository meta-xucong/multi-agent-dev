# 多 Agent 协作开发

一个用于 Codex 的通用开发工作流 Skill：主控定界与协调，按需思考处理歧义，执行做最小改动，独立审计凭证据验收。

采用四种逻辑职责、一份任务记录和事件驱动四步流程，重点解决范围跑偏、过度开发，以及“声称遵守约束但实际没有遵守”的问题。完整入口规则见 [SKILL.md](SKILL.md)，详细执行文档见 [references/adaptive-four-role-workflow.md](references/adaptive-four-role-workflow.md)，界面信息位于 [agents/openai.yaml](agents/openai.yaml)。

## 工作流摘要

四种职责不是四个常驻 Agent：主控通常是当前会话；只有需求、架构、契约或验收存在实质歧义时才启用只读的按需思考；执行者在冻结契约和唯一写入边界内工作；独立审计只对固定版本凭可观察证据验收。清晰小任务跳过思考，不允许子 Agent 递归扩编或再派生主控。

状态流为：

```text
定界/基线 → 必要时思考 → 契约冻结 → 执行 → 版本冻结 → 审计
                                      ├→ 通过 / 实现返工 / 补证
                                      └→ 契约回流 / 等待用户
```

事件驱动指主控在交接、决策、差异、审计结论或阻断条件出现后选择下一状态；它不是软件事件系统，也不是定时轮询。审计不得要求或声称看到隐藏推理，而检查额外文件、抽象、字段、变量、方法、依赖、重命名、行为和无新证据的重复尝试等可观察结果。

默认模型策略是：主控 `gpt-5.6-luna/high`，按需思考 `gpt-5.6-sol/max`，执行 `gpt-5.6-luna/high`，独立审计 `gpt-5.6-luna/high`；Sol 只用于按需思考，其他职责只在 Luna High 与 Luna Max 之间升级。阶段门禁、最终门禁、异常裁决、冻结范围内复杂调试或高风险语义审计才按规则升级到 `max`，不能因为“更保险”、普通失败或任务较大自动升级。保守门禁要求：只有能证明任务是单模块、无公共语义变化且无实质歧义时才允许停留在 Luna High；无法证明简单就先升级。Skill 不能强制切换当前主会话模型；显式派发不支持目标配置时必须如实披露。

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

`agents/openai.yaml` 仅是 Codex 的界面元数据，不是模型路由、权限系统或自定义 Agent 配置；本次没有创建自定义 Agent TOML、脚本、依赖或自动化。若确需自定义 Agent，必须遵循官方支持的配置目录和格式，不能把它写进本 Skill 或用 `openai.yaml` 冒充。

确认后，仓库维护者可以提交并推送：

```text
git diff --check
git diff
git add -- SKILL.md agents/openai.yaml README.md references/adaptive-four-role-workflow.md
git commit -m "docs: refine development workflow"
git push origin main
```

仅暂存实际需要发布的文件；新增支持文件时逐项审查后再加入。不要向这个公开仓库提交具体项目代码、私有需求、审计日志、密钥或账户配置。

## 边界

这是工作方法，不是权限隔离系统或自动合规证明器。它不替代项目规则，不自动授权部署、付费调用或 Git 操作；独立审计需要运行环境提供相应能力。格式校验通过也不代表真实开发效果已被完整验证。参考文档只承载协作细则，不改变用户授权、项目契约、章节审批或外部操作边界。
