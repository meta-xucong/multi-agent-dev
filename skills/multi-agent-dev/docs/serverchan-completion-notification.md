# ServerChan 任务结束通知开发文档

## 目标与范围

本能力只负责在多 Agent 实施任务进入终态或需要用户接管时，向 ServerChan/微信发送一次简短提醒。它不改变开发范围、模型路由、审计结论、提交权限或外部系统授权，也不发送阶段心跳。

适用范围：

- `done`：目标、必要验证、独立审计和最终证据均已完成；
- `blocked`：需要用户决定、凭据、权限或不可替代的外部条件；
- `stopped`：受保护停止、guardrail 触发或等待人工验收。

不适用：

- 普通开发过程、子 Agent 交接、阶段切换和每次测试；
- 审计拒收后仍可在冻结契约内修正或补证的回流；
- 只读监测、诊断和评审任务，除非用户明确要求推送。

## 凭据和发送方式

调用 `scripts/notify_serverchan.py`。凭据顺序与 `long-running-task` 保持一致：

1. `SCT_SENDKEY` 环境变量；
2. `%USERPROFILE%\.codex\secrets\serverchan_sendkey.txt`。

也支持显式 `--sendkey`，但不应在命令历史、日志、任务记录或最终回复中使用真实值。脚本向 `https://sctapi.ftqq.com/{SENDKEY}.send` 发送 `title`、`short` 和 Markdown `desp`，成功条件为响应 `code == 0`。

默认发送 3 次，每次间隔 2 秒；网络错误、非零响应和缺少凭据都必须返回失败。缺少凭据或重试失败不能回滚已经完成的代码，但必须把通知失败记录为交付阻断风险，并在最终回复中明确说明；不得无说明地把通知未送达的任务报告为完整交付。

## 消息最小内容

消息只包含：

- 项目或任务名称；
- `done`、`blocked` 或 `stopped`；
- 完成内容或阻断原因；
- 最重要的测试/审计结果；
- 用户下一步。

不要发送完整日志、隐藏推理、SendKey、私有凭据或大段差异。为避免同一项目中不同任务串状态，脚本不会自动读取 `.codex-longrun/state.json`；只有显式传入 `--state-file` 时才读取目标、阶段、最近测试和阻断项。未传入时使用 `--message` 作为通用终态摘要。

## 调用示例

```powershell
python "$env:USERPROFILE\.codex\skills\multi-agent-dev\skills\multi-agent-dev\scripts\notify_serverchan.py" `
  --project . --status blocked --title "多 Agent 任务已阻断" `
  --short "需要人工决定" `
  --message "审计发现契约缺口，已停止代码写入；请确认下一步范围。"
```

验证消息格式时使用 `--dry-run --sendkey TEST`，不得用真实 SendKey 做自动化测试：

```powershell
python "$env:USERPROFILE\.codex\skills\multi-agent-dev\skills\multi-agent-dev\scripts\notify_serverchan.py" `
  --status done --title "Test" --message "dry run" --sendkey TEST --dry-run
```

## 门禁

通知必须发生在最终证据固定之后，并且只由主控在最终交付/阻断路径调用。审计员不发送“通过”通知；审计拒收不会单独触发通知。通知成功不等于代码验收通过，代码验收仍以独立审计和版本绑定证据为准。
