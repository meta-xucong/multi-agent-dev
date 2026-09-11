# 主回合停滞与协作收敛恢复开发文档

> CONTRACT_REV: `v1.3.1-route-guard`
> MONITOR_REV: `v1.0-observe-gate`
> 状态：契约冻结后实施

## 1. 背景与可复现问题

目标不是增加新的 Agent 角色，而是补齐现有四职责流程在协作运行时的收敛门禁。已观察到以下故障面：

- 主任务保持 `active/inProgress` 很长时间，没有新的助手消息、工具事件或最新工具标记；
- 子智能体已经 `idle/notLoaded/completed`，但主控仍反复等待或显示“无法关闭智能体”；
- 同一个子智能体已经关闭后又重复调用 `closeAgent`，产生失败记录并被误判为仍在运行；
- 主回合状态未知时，主控可能继续派发替代写入者，破坏唯一写入者门禁。
- `wait_threads`、`read_thread`、UI 或列表快照对同一回合给出互相矛盾的状态，监测者无法区分真实活动与旧状态残留。

## 2. 目标与非目标

目标：

1. 区分“主回合停滞”和“子智能体仍活动”；
2. 对关闭失败采用一次状态核验，不做无新证据的机械重试；
3. 在旧写入者状态未知时阻止替代写入者、fork 或继续写入；
4. 提供可复现的恢复状态、停止证据和用户交接条件。

非目标：

- 不新增常驻 Agent、角色或外部监控服务；
- 不改变 `MAD_ROUTE_V1` 的字段、真值表、Hook 输入输出或 `CONTRACT_REV`；
- 不声称 Skill 能强制取消平台内部已经卡住的主回合；
- 不自动归档、删除、重置或改写用户任务与工作区；
- 不把监测期的状态播报变成正式开发期的周期性用户消息。

## 3. 状态判定与证据

主控每次只保存最近一次可观察快照：

```text
ORCH_HEALTHY
ORCH_STALE_SUSPECTED
ORCH_STATE_CONFLICT
ORCH_STOP_REQUESTED
ORCH_BLOCKED_NEEDS_USER
```

- `ORCH_HEALTHY`：主回合有新的助手消息、工具事件、状态变化或明确的完成/失败结果。
- `ORCH_STALE_SUSPECTED`：在一次有界等待窗口后，主回合仍为 `active/inProgress`，且没有新的助手消息、工具事件、最新工具标记或错误；这只是停滞嫌疑，不等于已停止。
- `ORCH_STATE_CONFLICT`：同一任务/回合的可用状态来源互相矛盾，或主回合状态与事件流无法对应；在冲突收敛前不得放行、替代写入或把单一来源当作停止证据。
- `ORCH_STOP_REQUESTED`：一次平台支持的停止/取消或一次“停止并收敛”用户输入已被平台接受/排队，等待状态确认；不得重复发送同一请求。它不等于主回合已经终止。
- `ORCH_BLOCKED_NEEDS_USER`：停止调用不支持、失败、未被接受，读取失败/空结果/无法证明状态，或已接受请求经过一次有界复核后状态仍未知/活动；必须等待用户在界面停止、重启会话或明确下一步。

快照至少绑定：任务/回合 ID、观察时间、主任务状态、最新事件/工具标记、所有子智能体 ID 及状态、当前唯一写入者和 `WRITER_STATUS`。没有快照不能把“看起来没有输出”当作停止证据。

## 3.1 监测模式与状态报告

正式开发默认是 `MONITOR_MODE=DELIVERY_SILENT`：不发送周期性心跳或重复的无变化消息，只在交接、阻断、范围/契约变化和交付时记录必要状态。只有用户明确要求监测/诊断运行中会话时启用 `MONITOR_MODE=OBSERVE`。`OBSERVE` 仍按事件触发，不按固定间隔刷屏。

`OBSERVE` 模式在建立基线、派发/收回子智能体、开始或结束长操作、发现状态冲突和形成最终结论时发送一次 `STATUS_REPORT_V1`。最小字段为：

```text
task_id / turn_id / observed_at
phase / main_status / CONTRACT_REV
child_agents: id, role, status, last_event, expected_until, writer
active_writer / changed_files
last_progress_evidence / tests / audit_status
blockers / next_step / conclusion
```

长操作要记录 `operation_started_at`、`expected_until`、`last_progress_at` 和负责人；在预期窗口内没有消息不构成停滞证据。子智能体“正在工作”必须有最近工具事件、文件变化、测试结果或 `STATUS_REPORT_V1` 等活动凭证，UI 标签或口头声明不能单独证明活动。`wait_threads` 用于唤醒和粗状态，`read_thread` 的事件/工具/文件记录用于活动证据，`list_threads` 仅作导航参考；来源冲突时进入 `ORCH_STATE_CONFLICT`。

`DELIVERY_SILENT` 下可以把状态报告压缩写入现有任务记录或交接记录，不要求向用户重复输出；同一问题只有状态或证据变化时才更新。

## 4. 停滞恢复流程

1. **一次有界观察**：对目标任务执行一次平台允许的有界等待，并记录实际等待参数、游标/修订号和返回状态；随后读取主任务和全部子任务状态。不要无限轮询，等待时长本身不是停止证据。
2. **先对账状态来源**：将 `wait_threads` 的唤醒/粗状态、`read_thread` 的事件/工具/文件记录和 `list_threads` 的导航状态绑定到同一任务/回合快照。来源一致才继续分类；来源矛盾时登记 `ORCH_STATE_CONFLICT`，只允许一次无写入复核，期间不得停止、关闭、fork、替代写入或宣布完成。
3. **区分对象**：若子智能体均为 `inactive/completed/failed`，或为 `idle/notLoaded` 且读取成功、其回合结果没有 `inProgress`、没有进行中写入，但主回合仍 `active/inProgress` 且无新事件，记录 `ORCH_STALE_SUSPECTED`；任何子任务读取失败、空结果或状态无法证明都直接进入 `ORCH_BLOCKED_NEEDS_USER`。问题对象是主回合，不是子智能体。
4. **一次停止请求**：平台有中断能力时只调用一次，并记录返回值；平台只有用户输入能力时只发送一次“停止并收敛”指令。只有平台返回已接受/排队的证据才进入 `ORCH_STOP_REQUESTED`；不支持、失败或未被接受时直接进入 `ORCH_BLOCKED_NEEDS_USER`。已排队但尚未中断的请求只保持 `ORCH_STOP_REQUESTED` 到一次有界复核；复核仍活动才转为 `ORCH_BLOCKED_NEEDS_USER`。不继续派发或修改代码。
5. **关闭失败处理**：`closeAgent` 失败后立即读取同一 `receiverThreadId` 的状态：
   - 已是 `inactive/completed/failed` 且无进行中写入：登记为“重复/旧句柄关闭失败”，不重试，不把它算作活动；
   - 仅为 `idle/notLoaded`：必须读取成功，并确认没有 `inProgress` 回合和进行中写入后，才可登记为重复关闭；读取失败或结果为空则进入 `ORCH_BLOCKED_NEEDS_USER`；
   - 仍活动：记录失败证据，只允许一次平台支持的停止/取消，然后重新核验；
   - 状态未知或读取失败：进入 `ORCH_BLOCKED_NEEDS_USER`，禁止替代写入者。
6. **恢复门禁**：只有主回合和旧写入者都被确认终止，且工作区/基线可核对后，才能 fork 或派发替代者。替代者必须重新读取 Skill、使用当前 `CONTRACT_REV`、合法 `MAD_ROUTE_V1`、非继承 fork 和 receipt；旧会话的旧 marker、`xhigh`、无 receipt 结果全部作废。
7. **用户交接**：平台无法接受停止请求，或已接受的请求经过一次有界复核仍不能中断主回合时，不自动归档、重置或覆盖任务；向用户报告任务/回合 ID、最后快照、已发出的单次停止请求、仍缺少的停止证据，并请求用户在 UI 停止或新建任务。状态只能是 `ORCH_BLOCKED_NEEDS_USER`，不能 `ACCEPTED`。

## 5. 验收矩阵

| 场景 | 预期结论 |
| --- | --- |
| 主回合有新工具事件 | `ORCH_HEALTHY`，继续原流程 |
| 一次有界等待无事件，但子任务终止 | `ORCH_STALE_SUSPECTED`，不得派新写入者 |
| `wait_threads`、`read_thread` 或 UI 状态互相矛盾 | `ORCH_STATE_CONFLICT`，只做一次无写入复核 |
| 关闭已终止子任务再次失败 | 记录重复关闭，不重复重试 |
| 关闭活动子任务失败且状态仍活动 | 一次停止/取消后复核，仍不明则阻断 |
| 主回合无法中断 | `ORCH_BLOCKED_NEEDS_USER`，等待用户，不宣布完成 |
| 主回合和旧写入者均终止 | 可按当前路由门禁重新派发，并重新固定基线 |

验证要求：

- `python -B -m unittest discover -s tests -p "test_*.py" -v`（包含文档状态转换、读取失败和重复关闭证据语义的一致性回归）；
- skill 外部 quick-validate；
- `git diff --check`；
- 逐项检查 SKILL、参考文档和 README 的状态名、停止条件及“不得替代写入”表述一致。
