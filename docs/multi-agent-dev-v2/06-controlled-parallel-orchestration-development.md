# multi-agent-dev V2.1：受控并发编排开发文档

状态：开发前设计冻结稿，待独立文档审计
适用范围：skills/multi-agent-dev-v2/ 的并发调度、状态、纠察和审计扩展
前置版本：V2.0-route-contract
目标：在保留 V2 范围控制、唯一 writer、独立审计和证据放行的基础上，支持多个 Agent 并发执行。

## 1. 目标与成功标准

1. 允许互不依赖的只读调查、测试和分离写入任务并发运行。
2. 所有并发任务由单一持久化调度器推进，Agent 不能自行派发兄弟任务。
3. 每个可变 namespace 在同一时间只有一个活跃 writer。
4. 用户的新指令、范围变化和授权变化都能形成新的 manifest 版本。
5. 旧 writer、过期 lease、重复回写和失败重试不会污染当前 run。
6. 纠察只读检查过程偏航，独立审计只读检查固定版本。
7. 没有精确版本、差异、测试、审计和路由证据时，run 不能进入 RELEASED。
8. 模型和 reasoning effort 只记录为请求配置，除非有独立运行元数据，否则保持 ROUTE_UNVERIFIED。

## 2. 范围与非目标

### 2.1 本轮允许交付

- 并发任务图和依赖协议。
- run、task、lease、checkpoint、handoff 和 event ledger 数据结构。
- 受控 fan-out/fan-in 调度。
- namespace writer lease 和冲突检查。
- 可选的持久化 controller。
- 事件触发的 deterministic guard 和语义纠察 Agent。
- 并发、恢复、竞态、证据和路由测试。
- 与 V1 保留行为兼容的迁移和回归说明。

### 2.2 本轮明确不做

- 不修改 V1 文件及其已有未提交修改。
- 不自动安装 Profile、Hook 或修改用户级配置。
- 不自动切换主会话模型。
- 不提交、推送、部署或执行付费外部操作。
- 不允许 Agent 自行扩大范围、改变验收标准或签发最终通过。
- 不把并发数量、Token 下降或模型强度当作质量证据。
- 不让常驻 LLM 逐工具调用进行全量评论。
- 不用纠察 Agent 替代独立审计 Agent。

## 3. 权威分层

V2 不设置两个平权主控，四类权威分别负责不同事实。

| 权威 | 责任 | 允许动作 |
| --- | --- | --- |
| 意图与授权权威 | 用户和主会话 | 冻结目标、非目标、D 结论、范围变更、最终用户沟通 |
| 调度与状态权威 | 持久化 controller | 推进状态、建立 DAG、发放 lease、fan-out/fan-in、恢复和取消 |
| 写入权威 | 当前 namespace 的唯一 writer 或 main integrator | 在授权路径内产生差异、提交结构化 handoff |
| 审计权威 | 独立只读审计 Agent | 对固定版本出具 PASS、HOLD、REJECT 或 DEGRADED 证据结论 |

主会话可以直接调度低风险短任务。涉及并发、长时间运行、恢复或多个阶段时，主会话把冻结的 manifest 交给 controller。主会话仍保留用户授权和最终交付权。

## 4. 角色、模型与思考强度

下表是请求路由规范，不是实际运行凭证。平台没有提供独立 runtime provenance 时，记录 ROUTE_UNVERIFIED。

| 角色 | 默认模型 | 默认 effort | 权限与触发 |
| --- | --- | --- | --- |
| 主会话 | gpt-6-luna | high | 推荐配置；由用户会话设置，Skill 不自动切换 |
| Controller 状态机 | 无 LLM | 不适用 | 用确定性状态和 CAS 推进，不由模型决定锁和状态 |
| Controller 计划建议 | gpt-6-luna | high | 仅生成任务拆分或重排建议；不能直接写入或放行 |
| Think | gpt-6-sol | xhigh | 仅 D1；只读澄清设计、来源和契约歧义 |
| Execute I0 | gpt-6-luna | low | 严格精确执行；必须满足 I0 全部准入条件 |
| Execute I1 | gpt-6-luna | high | 常规实现；范围和行为契约已冻结 |
| Execute I2 | gpt-6-luna | xhigh | 跨模块交互、恢复分支或竞争路径已被证实 |
| Execute I3 | gpt-6-luna | max | 极少数高后果封闭问题；必须有问题编号和新证据 |
| Test/Verification | gpt-6-luna | high | 只读验证；复杂故障测试按 I2 升为 xhigh |
| Deterministic Guard | 无 LLM | 不适用 | 结构、路径、lease、hash、状态和证据字段检查 |
| Semantic Guard A0 | gpt-6-luna | high | 仅在 barrier、handoff 或异常事件触发 |
| Semantic Guard A1 | gpt-6-luna | xhigh | 跨模块、恢复、严格负面约束 |
| Semantic Guard A2 | gpt-6-luna | max | 隐私、权限、外部副作用、发布门禁 |
| Independent Audit A0 | gpt-6-luna | high | 固定版本只读审计 |
| Independent Audit A1 | gpt-6-luna | xhigh | 深度跨模块和严格范围审计 |
| Independent Audit A2 | gpt-6-luna | max | 高后果最终门禁 |
| Notification | 无 LLM | 不适用 | 确定性脚本和已验证终态通知契约 |

Controller 计划建议不拥有 D/I/A 重分类权。出现 D1 时调用 Think；出现 A1/A2 时调用独立 Guard/Audit。执行 Agent 不能因失败自行升档，升级必须由 controller 依据新证据重新生成 manifest。

## 5. D/I/A 与并发规则

D、I、A 是正交维度。

- D1：先建立设计结论和 ScopeManifest，未冻结前禁止写入。
- I0/I1：可以拆分独立叶子任务，但仍受 writer lease 限制。
- I2/I3：可以并行收集事实和测试；共享契约、恢复状态和主线整合保持串行。
- A0：在任务完成时做轻量检查。
- A1/A2：每个 handoff、共享契约变更、异常重试和 merge 前都必须经过更严格门禁。

范围、契约、公共 schema 或外部副作用变化时，D/I/A 重新计算并创建新 manifest revision。旧任务标记 SUPERSEDED 或 QUARANTINED，不能继续写入。

## 6. ScopeManifest

ScopeManifest 是一次 run 的不可变计划。至少包含：

- run_id、parent_run_id、manifest_revision、manifest_hash。
- base_revision、base_tree_hash 和工作区差异摘要。
- 用户目标、非目标、硬约束和项目规则来源。
- allowed_paths、forbidden_paths、read_paths 和 namespace 列表。
- D/I/A 分数、contract_rev、阶段和验收条件。
- task DAG、并发组、依赖、预算、超时和最大重试次数。
- Hook 状态、Profile 状态、route provenance 状态和降级模式。
- 外部副作用分类、通知策略和审计要求。
- 唯一 writer、integrator、guard 和 audit owner。

Manifest 冻结后只允许生成新 revision，不允许静默追加字段或路径。manifest_hash 是完整性证据，不代表语义批准。

## 7. TaskSpec 与并发组

每个 TaskSpec 至少包含：

- task_id、parent_task_id、manifest_hash、state_revision。
- role、stage、D/I/A、requested_model、requested_effort。
- read_set、write_set、namespace、concurrency_group。
- dependency_ids、idempotency_key、lease_id、lease_expiry。
- input_artifact_refs、acceptance_checks、side_effect_class。
- route_provenance、checkpoint_ref、next_allowed_actions。

并发规则：

1. read-only 任务可以并发读取同一冻结快照。
2. write_set 不重叠且 namespace 不共享时，允许分离 writer 并发。
3. 共享 schema、lockfile、配置、证据文件和状态库必须建立单独串行 owner。
4. writer 必须使用独立 worktree 或受控 patch 区；不能同时直接修改 main 工作树。
5. main integrator 同一时间只能有一个。
6. 同一 task 的重试必须复用或显式替换 idempotency_key，不能产生重复写入。
7. 并发上限由 manifest 固定；默认从 2 个 worker 起步，根据资源和证据调整，不无限扩张。

## 8. Run 与 Task 状态

Run 状态：

INTAKE → DESIGN_PENDING → SCOPE_FROZEN → DISPATCHABLE → RUNNING → EVIDENCE_COLLECTION → AUDIT_HOLD → READY_TO_MERGE → INTEGRATED → RELEASED

Run 旁路状态：

RETRYABLE、HELD、UNKNOWN、SUPERSEDED、QUARANTINED、CANCELLED。

Task 状态：

PLANNED → LEASED → RUNNING → CHECKPOINTED → WAITING_HANDOFF → AUDIT_PENDING → ACCEPTED

Task 旁路状态：

RETRYABLE、FAILED、HELD、UNKNOWN、SUPERSEDED、CANCELLED。

只有 controller 可以推进状态。UNKNOWN、HELD、stale task 或未解决的 lease 冲突不能进入 RELEASED。

## 9. Lease、CAS 与事件账本

每次状态转移必须携带：

- run_id、task_id、manifest_hash。
- expected_state_revision、actor_id、lease_id、event_id。
- transition_reason、evidence_refs、created_at。

controller 在同一持久化事务内按实体 revision 做 CAS、更新实体、追加 append-only event 和 pending outbox；事务任一步失败全部回滚，禁止出现状态已变但 event 缺失。run、task、lease 分开维护 revision；并发 task 只校验自己的 revision，run revision 只在汇合时 CAS。lease 必须有 TTL 和 heartbeat。lease 过期时先标记 UNKNOWN，确认旧 writer 终止后才允许重新派发。

Agent 只能通过受控工具提交 checkpoint、handoff 和状态事件，不能直接修改状态库或伪造 audit receipt。旧 writer 的迟到回写按 lease_id 和 state_revision 拒绝。

## 10. Fan-out、Fan-in 与整合

Fan-out 前 controller 必须确认：

- manifest 已冻结；
- 所有依赖满足；
- writer lease 不冲突；
- side-effect class 可并发；
- 每个任务有明确验收和超时；
- Guard 已返回 ALLOW 或适用的 WARN。

Fan-in 前 controller 必须收集：

- changed_paths 和 diff hash；
- artifact hashes；
- 测试命令、退出码和结果；
- blocker、假设、未决项；
- route provenance 和 Hook 状态；
- 下一允许动作；
- guard decision 和 audit receipt。

只有所有必需任务达到 ACCEPTED，且 Guard/Audit 门禁满足，才能进入 READY_TO_MERGE。整合由 main integrator 串行完成，再重新运行受影响测试。

## 11. HandoffPacket

HandoffPacket 只传结构化状态，不传隐藏推理。必填字段：

task_id、parent_task_id、manifest_hash、state_revision、lease_id、base_revision、result_revision、changed_paths、diff_hash、artifact_hashes、test_receipts、audit_receipt、route_provenance、assumptions、open_questions、next_allowed_actions、budget_usage、status。初始 handoff 的 audit_receipt 必须为 null；Controller 固定结果后才进入 AUDIT_PENDING，独立审计返回 receipt 后附加，附加成功才允许 ACCEPTED。

缺少精确版本、差异、测试或证据引用时，handoff 只能是 INCOMPLETE 或 HOLD。Handoff 不能自行改变 scope、D/I/A、model、effort 或 acceptance。

## 12. 失败、重试与恢复

- 普通失败只进入 RETRYABLE，不自动升级模型。
- 重试必须说明新证据、变化输入或修正动作。
- 连续失败没有新证据时，Guard 返回 BLOCK 或 NEEDS_USER_DECISION。
- 进程崩溃、lease 过期和状态不明进入 UNKNOWN，先恢复 checkpoint，再决定重试。
- 主会话收到新用户指令时，controller 暂停受影响任务并创建新 manifest revision。
- 取消只取消当前 run 中允许取消的任务；共享 writer 和外部副作用任务必须先完成停止确认。
- 通知失败不伪称送达；终态通知仍由现有 V2 notifier 契约处理。

## 13. 纠察与独立审计边界

Deterministic Guard 常驻检查 schema、path、lease、hash、状态和证据字段。Semantic Guard 只在 dispatch、handoff、retry、merge、范围变化和高风险事件触发。

Guard 输出：

ALLOW、WARN、BLOCK、NEEDS_USER_DECISION。

Guard 只能阻断、报警或请求补证，不能写代码、修改 manifest、改变验收标准、合并或签发最终通过。

Independent Audit 输出：

PASS、HOLD、REJECT、DEGRADED。

Guard 与 Audit 不共用 pass 字段。Guard 发现问题后，修正必须产生新 fixed version，再由独立 Audit 复核。

## 14. Hook 不可用时的降级

Hook 是纠错能力，不是状态真相。ledger 记录 HOOK_ENFORCED、HOOK_UNAVAILABLE 或 HOOK_UNVERIFIED。

Hook 不可用时，controller 仍必须执行：

- writer lease；
- tool/path allowlist；
- sandbox 或 dry-run；
- 命令与效果日志；
- manifest 和 state revision 检查；
- Guard 与 Audit 证据门禁。

低风险只读任务可在 degraded_guard 下继续。涉及写入冲突、权限、隐私、外部副作用或发布的任务缺少 Guard/Audit 证据时保持 HOLD。

## 15. 主会话与 Controller 的工作边界

主会话负责用户意图、授权、D1 解歧、范围冻结、范围变更、最终整合和交付。

Controller 负责任务图、队列、lease、并发、依赖、重试、恢复、状态汇总和证据收集。

Controller 的 LLM 只产生结构化计划建议。确定性状态机才是状态和锁的唯一来源。主会话不能成为被动转发器，Controller 也不能成为第二个平权主控。

## 16. 实施顺序

Phase 0：冻结 ScopeManifest、TaskTemplate/TaskSpec、HandoffPacket、GuardDecision、AuditReceipt 和状态转移。
Phase 1：实现确定性 schema、canonical hash、ledger、CAS、lease、并发组和 fan-out/fan-in。
Phase 2：实现只读并发和测试并发，验证取消、恢复、重复回写和冲突。
Phase 3：实现 handoff、deterministic guard、事件触发 Semantic Guard 和独立审计收据边界。
Phase 4：实现分离 worktree writer、worker adapter 和 main integrator。
Phase 5：实现持久化 Controller、checkpoint、outbox、context-lean 恢复和回归。
Phase 6：完成运行时 Hook、Profile、provenance、前向工作流和独立审计验收。

Phase 顺序以本节和 D09 为唯一权威；每个 Phase 只能在前一 Phase 的 exit receipt、独立 Guard 和 required tests 完成后进入。

任何 Phase 未达到 Exit Gate，不得进入下一阶段。

## 17. Exit Gate

- V1 工作区差异未被覆盖。
- Manifest、TaskSpec、状态、lease、handoff 和 guard 字段有唯一 schema。
- 同一 namespace 不存在两个活跃 writer。
- 旧 writer、UNKNOWN、HELD 和 stale task 不能进入 RELEASED。
- 并发冲突、取消、崩溃、迟到回写和重复通知都有回归证据。
- Guard 与 Audit 责任人分离。
- 所有模型和 effort 结论有真实 provenance；缺失时明确 ROUTE_UNVERIFIED；路由 enum 采用 D07 的 PROFILE_VERIFIED、EXPLICIT_ROUTE_VERIFIED、ROUTE_UNVERIFIED、ROUTE_MISMATCH。
- Controller 的 run/task/lease revision 分域，CAS、event 和 outbox 在同一事务内持久化。
- Hook/Profile/五个前向工作流没有实测时，仍保持对应未验证状态。
- 未经用户另行授权，不安装、信任、提交、推送或部署。
