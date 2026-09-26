# ServerChan 任务结束通知开发文档

## 目标与范围

本能力负责在使用 `multi-agent-dev` 的任务结束、阻断、停止或中断时，向 ServerChan/微信发送一次简短提醒。它不改变开发范围、模型路由、审计结论、提交权限或外部系统授权，也不发送阶段心跳。

适用范围：

- `done`：目标、必要验证、独立审计和最终证据均已完成；
- `blocked`：需要用户决定、凭据、权限或不可替代的外部条件；
- `stopped`：受保护停止、guardrail 触发或等待人工验收。

不发送的唯一情况是任务仍在本轮继续推进：普通开发过程、子 Agent 交接、阶段切换、测试重跑和审计拒收后的范围内返工不单独推送。一旦本轮停止、阻断或结束，必须推送；监测、诊断和评审任务也不再静默豁免。

## 发送时机与 Hook 协作

主控在最终报告前显式调用 `scripts/notify_serverchan.py`，并把任务名、终态、摘要、关键验证结果和用户下一步作为普通命令参数传入。`done` 状态必须提供 `--verification`，或通过显式 `--state-file` 提供带 `result` 的测试记录；只有命令名、没有测试结果不能通过完成通知门禁。最终回复不附加 HTML 注释或其他机器终态标记。

用户级 `hooks.json` 可以把 `Stop`、`Interrupt` 和 `SessionEnd` 接到 `hooks/task_terminal_notify.py`：

- `Stop` 不再把普通回合结束视作任务完成，也不要求最终回复中的标记；它只重试已经持久化的待发送通知。
- 若本轮通过路由 Hook 派发过 Agent，直接通知时传入最近一次成功路由的 `--task-id`。脚本会在发送前登记待通知内容，因此直接发送失败时 Stop Hook 可重试；发送成功后写 receipt 并清除同 task_id 的中断补偿记录，避免重复推送。
- `Interrupt`/`SessionEnd` 在活动任务尚未成功通知时发送 `stopped` 补偿。没有路由派发记录的任务仍由主控直接调用通知脚本，不依赖 Hook。

`status` 只能是 `done`、`blocked` 或 `stopped`。Hook 未信任或未加载时，主控仍应直接调用通知脚本，但重试和中断补偿不可用；通知脚本本身不可用、缺少凭据或网络不可用则按交付阻断风险处理，不能静默伪称送达。

## 凭据和发送方式

调用 `scripts/notify_serverchan.py`。凭据顺序与 `long-running-task` 保持一致：

1. `SCT_SENDKEY` 环境变量；
2. `%USERPROFILE%\.codex\secrets\serverchan_sendkey.txt`。

也支持显式 `--sendkey`，但不应在命令历史、日志、任务记录或最终回复中使用真实值。脚本向 `https://sctapi.ftqq.com/{SENDKEY}.send` 发送 `title`、`short` 和 Markdown `desp`，成功条件为响应 `code == 0`。

默认发送 3 次，每次间隔 2 秒；网络错误、超时、非零响应和缺少凭据都必须返回失败并进入重试。缺少凭据或重试失败不能回滚已经完成的代码。若有已路由的活动任务，脚本会保留待发送记录供 Stop/SessionEnd Hook 重试；所有重试仍失败时，必须把通知失败记录为交付阻断风险并明确说明，不得把通知未送达的任务报告为完整交付。

## 消息最小内容

消息只包含：

- 项目或任务名称；
- `done`、`blocked` 或 `stopped`；
- 完成内容或阻断原因；
- 最重要的测试/审计结果；
- 用户下一步。

不要发送完整日志、隐藏推理、SendKey、私有凭据或大段差异。为避免同一项目中不同任务串状态，脚本不会自动读取 `.codex-longrun/state.json`；只有显式传入 `--state-file` 时才读取目标、阶段、最近测试和阻断项。状态测试记录须包含 `result`；同时包含 `command` 时，通知会优先显示结果并附上命令。未传入 state file 时，通过 `--verification` 显式写入结果，通过 `--message` 写入终态摘要。

## 调用示例

```powershell
python "$env:USERPROFILE\.codex\skills\multi-agent-dev\skills\multi-agent-dev\scripts\notify_serverchan.py" `
  --project . --status blocked --title "多 Agent 任务已阻断" `
  --verification "独立审计发现契约缺口，无法通过验收" `
  --short "需要人工决定" `
  --message "审计发现契约缺口，已停止代码写入；请确认下一步范围。" `
  --task-id "madv1_serverchan_20260926_001"
```

如果任务没有通过路由 Hook 派发子 Agent，则省略 `--task-id`。若传入，必须使用本轮最近一次成功路由的唯一 task ID；示例 ID 不能原样复用。该参数只用于本机通知 Hook 的重试/去重，不会作为消息内容发送给 ServerChan。

验证消息格式时使用 `--dry-run --sendkey TEST`，不得用真实 SendKey 做自动化测试：

```powershell
python "$env:USERPROFILE\.codex\skills\multi-agent-dev\skills\multi-agent-dev\scripts\notify_serverchan.py" `
  --status done --title "Test" --message "dry run" --verification "1 test passed" --sendkey TEST --dry-run
```

## 门禁

通知必须发生在最终证据固定之后，并且由主控在最终回复前显式触发。审计员不发送“通过”通知；审计拒收只有在本轮停止时才按 `blocked` 通知。通知成功不等于代码验收通过，代码验收仍以独立审计和版本绑定证据为准。通知失败也不能被模型口头声明覆盖。
