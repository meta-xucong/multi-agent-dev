# meta-xucong Skills

多平台 AI 辅助开发 Skills 仓库，支持 **Codex** (ChatGPT 5.6) 和 **Claude Code** (Claude 5)。每个 Skill 都放在 `skills/<skill-name>/` 下，彼此独立，便于单独安装、审查和迭代。

## 🔀 平台选择指南

| 平台 | 适用版本 | 说明 |
|---|---|---|
| **Codex** | `skills/multi-agent-dev/`<br>`skills/context-lean/` | 原始版本，使用 ChatGPT 5.6 (Sol/Luna)，含完整 Hook 系统 |
| **Claude Code** | `skills/multi-agent-audit-claude-code/` | 新增版本，使用 Claude 5 (Opus/Sonnet/Haiku)，基于 context-lean 原则 |

## 技能目录

### Codex 平台

| Skill | 用途 | 模型要求 | 入口 |
| --- | --- | --- | --- |
| `multi-agent-dev` | 按开发文档组织主控、按需思考、最小执行与独立审计，以证据控制范围和验收；长任务按需伴随 `context-lean` | ChatGPT 5.6 (Sol/Luna) | [`skills/multi-agent-dev/SKILL.md`](skills/multi-agent-dev/SKILL.md) |
| `context-lean` | 优化 Codex 长任务的上下文膨胀、主动压缩、压缩前状态保存和压缩后恢复 | ChatGPT 5.6 | [`skills/context-lean/SKILL.md`](skills/context-lean/SKILL.md) |

### Claude Code 平台

| Skill | 用途 | 模型要求 | 入口 |
| --- | --- | --- | --- |
| `multi-agent-audit-claude-code` | 多模型协作审计工作流：Sonnet 5 (主对话 + 构建验证) + Opus 4.8 (独立审计)，集成八荣八耻工程纪律 | Claude Opus 4.8 + Sonnet 5 | [`skills/multi-agent-audit-claude-code/SKILL.md`](skills/multi-agent-audit-claude-code/SKILL.md) |

## 平台与技术栈

### Codex 平台
- **目标**: Codex 桌面版 + CLI
- **不兼容**: WorkBuddy、Claude Code

### Claude Code 平台
- **目标**: Claude Code 2.x (桌面版 + CLI + Web + IDE 扩展)
- **模型**: Claude 5 系列 (Opus/Sonnet/Haiku)
- **API**: Claude Code Agent tool
- **核心特性**:
  - Context-lean delegation (最小必要上下文)
  - 多模型协作 (不同任务分配不同模型)
  - 八荣八耻工程纪律集成
  - Evidence-based stopping

### Codex 技术栈

- **模型要求**:
  - `gpt-5.6-sol/max` (思考 Agent，复杂设计决策)
  - `gpt-5.6-luna/high` (执行 Agent，简单任务)
  - `gpt-5.6-luna/max` (执行/审计 Agent，复杂任务)

- **核心依赖**:
  - Codex 多 Agent 协作 API: `spawn_agent`, `wait_threads`, `read_thread`, `closeAgent`
  - Codex Hook 系统: `PreToolUse`, `PreCompact`, `SessionStart`, `PostCompact`
  - `MAD_ROUTE_V1` 模型路由硬门禁

### Claude Code 技术栈

- **模型要求**:
  - Opus 4.8 + max effort (独立审计，需要最高强度推理发现隐蔽问题)
  - Sonnet 5 + high effort (主对话协调 + 高标准构建验证)

- **核心依赖**:
  - Claude Code Agent tool: `subagent_type`, `model`, `effort` 参数
  - 无需 Hook 系统 (原生支持)

## 关键特性

### Codex 平台 — `multi-agent-dev`
- **四职责协作模型**: 主控、按需思考、执行、独立审计
- **模型路由真值表**: 按任务复杂度自动路由到 Sol/Luna High/Max
- **停滞检测与恢复**: 处理 `ORCH_STALE_SUSPECTED`、`ORCH_STATE_CONFLICT` 等异常状态
- **ServerChan 微信通知**: 任务终态自动推送（`done`/`blocked`/`stopped`）
- **验收矩阵**: 范围合规、实现方式合规、功能完成、证据绑定

### Codex 平台 — `context-lean`
- **三层压缩优化**: 推迟触发、主动压缩、状态保存与恢复
- **压缩前 5 项清单**: 当前任务、进行中文件、已做决策、阻塞项、下一步
- **Hook 自动化**: `PreCompact` 保存 `PROGRESS.md`，`SessionStart(compact)` 恢复上下文
- **Token 效率规则**: 大输出落盘、精准读文件、探索派子代理、最小 diff 编辑

### Claude Code 平台 — `multi-agent-audit-claude-code`
- **Context-Lean Delegation**: 子代理只接收最小必要上下文（diff + 文件列表）
- **多模型协作**: Sonnet 5 (主对话) + Opus 4.8 (审计) + Opus 5 (验证)
- **八荣八耻工程纪律**: 查档求证、对齐需求、复用存量、完备测例等完整检查清单
- **Evidence-Based Stopping**: 有足够证据就停止收集，避免过度调研
- **Surgical Changes**: 精确修改目标，不做额外重构
- **测试验证**: 已验证文件备份工具场景，1 轮迭代修复通过，Token 消耗 ~24k

## 关于 WorkBuddy 的说明

`context-lean` 的部分设计理念来自 [rohitg00/pro-workflow](https://github.com/rohitg00/pro-workflow) 针对 WorkBuddy 的优化（`context-engineering`、`context-optimizer`、`compact-guard`），但**本仓库的实现已完全适配 Codex 平台**，使用 Codex 专有的 API 和环境变量：

- 环境变量：`$CODEBUDDY_PROJECT_DIR`（Codex 项目根目录）
- 路径约定：`%USERPROFILE%\.codex\` 系列（skills、secrets、配置）
- Hook 实现：Codex Hook 系统，不兼容 WorkBuddy 的 Hook 规范
- 多 Agent 协作：`spawn_agent`、`wait_threads`、`closeAgent` 等 Codex API

**如需在 WorkBuddy 使用类似功能**，请直接参考原始项目 [rohitg00/pro-workflow](https://github.com/rohitg00/pro-workflow)。

## 安装

### Codex 平台

```bash
# 安装 multi-agent-dev
codex skills add skills/multi-agent-dev

# 安装 context-lean
codex skills add skills/context-lean

# 安装后需要重启 Codex 并通过 /hooks 审阅、信任 Hook 配置
```

### Claude Code 平台

```bash
# 方法 1: 直接复制到 skills 目录
cp -r skills/multi-agent-audit-claude-code ~/.claude/skills/multi-agent-audit

# 方法 2: 克隆仓库并链接
git clone https://github.com/meta-xucong/multi-agent-dev.git
ln -s $(pwd)/multi-agent-dev/skills/multi-agent-audit-claude-code ~/.claude/skills/multi-agent-audit

# 使用
/multi-agent-audit "你的任务描述"
```

## 仓库约定

- 一个 Skill 一个目录，入口文件固定为 `SKILL.md`
- Skill 的配套说明、参考资料、脚本和示例配置放在自己的目录内
- 不在仓库根目录放某个 Skill 的专属入口，避免新增 Skill 时发生命名冲突
- 公开提交前检查密钥、令牌、本机绝对路径、完整会话日志和项目私密数据
- 规则变更应同步更新对应 Skill 的说明和验证记录
- `multi-agent-dev` 与 `context-lean` 保持独立目录；主 Skill 只负责条件触发和边界衔接，不复制伴随 Skill 的全部规则
- 未经验证的实验功能标明验证范围，不把模拟测试写成真实平台已验证

## 许可证与责任边界

本仓库中的 Skill 是工作方法和自动化辅助脚本，不是权限隔离、合规证明或安全承诺。使用者仍需根据目标平台、项目规则和实际环境进行审查、授权与验证。

## 贡献与反馈

本仓库为个人使用仓库，如有问题或建议，请通过 GitHub Issues 提交。Pull Request 仅接受 bug 修复和文档改进，功能扩展需先在 Issue 中讨论。

---

**最后更新**: 2026-09-22  
**适配平台**: 
- Codex 2.x + ChatGPT 5.6 系列  
- Claude Code 2.x + Claude 5 系列  

**前置依赖**:
- Codex: 用户级 Hook 配置（需重启 Codex 并通过 `/hooks` 信任）
- Claude Code: 无特殊依赖（原生支持）
