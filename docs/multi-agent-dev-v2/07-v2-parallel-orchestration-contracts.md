# multi-agent-dev V2.1：并发编排协议与数据契约

状态：开发前契约冻结候选稿
适用对象：controller、worker、deterministic guard、semantic guard、independent audit 和主会话
依赖：06-controlled-parallel-orchestration-development.md

## 1. 协议原则

1. 所有状态转移必须绑定 run、task、manifest、state revision 和 actor。
2. 所有写入必须绑定 namespace、write_set 和未过期 lease。
3. 所有结果必须绑定 base revision、result revision、diff 或 artifact hash。
4. 任何新用户要求、范围变化或公共契约变化都生成新的 manifest revision。
5. digest 只证明完整性，不代表语义批准、质量通过或模型真实运行。
6. 结构化 handoff 不携带隐藏推理，只携带可复核事实、假设和未决项。
7. Agent 不能直接写 ledger、伪造 receipt、越过 controller 推进状态或自行合并。

## 2. Contract revision

当前并发协议建议使用：

contract_rev: v2.1.0-controlled-parallel

向后兼容要求：

- V2.0 route marker 仍按原 V2 契约解析。
- 新的并发字段不得被旧 V2 Hook 当作 V1/V2 route marker。
- controller 拒绝未知 contract_rev，不静默降级到旧语义。
- 兼容读取不等于兼容写入；写入方必须使用当前 revision。

## 3. ScopeManifest

ScopeManifest 逻辑字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| run_id | safe id | 是 | 一次完整编排运行 |
| parent_run_id | safe id/null | 否 | 由哪次运行派生 |
| manifest_revision | 正整数 | 是 | 同一 run 的范围版本 |
| manifest_hash | sha256 | 是 | 规范化 manifest 完整性摘要 |
| base_revision | string | 是 | 起始代码或文件版本 |
| base_tree_hash | sha256/string | 是 | 起始树摘要 |
| contract_rev | string | 是 | 当前协议版本 |
| goal | string | 是 | 用户目标摘要 |
| non_goals | string[] | 是 | 明确不做事项 |
| allowed_paths | path[] | 是 | 允许写入目录或文件 |
| forbidden_paths | path[] | 是 | 禁止写入范围 |
| D | D0/D1 | 是 | 设计歧义 |
| I | I0/I1/I2/I3 | 是 | 实现难度 |
| A | A0/A1/A2 | 是 | 审计风险 |
| task_specs | TaskTemplate[] | 是 | 任务 DAG 模板；模板内不包含 manifest_hash/scope_hash |
| concurrency_limit | integer | 是 | 最大 worker 数 |
| evidence_requirements | string[] | 是 | 必须提供的证据 |
| hard_constraints | object[] | 是 | 用户/项目硬约束及来源引用 |
| rule_sources | object[] | 是 | 规则、来源和固定版本引用 |
| read_paths | path[] | 是 | 允许读取范围 |
| stage | enum | 是 | PRE_CONTRACT、CONTRACT_FROZEN、VERSION_FROZEN、INTEGRATION |
| owners | object | 是 | main、integrator、schema owner 和审计 owner |
| notification_policy | object | 是 | 通知方式和授权引用 |
| side_effect_policy | enum | 是 | none、local、external-held |
| route_status | enum | 是 | PROFILE_VERIFIED、EXPLICIT_ROUTE_VERIFIED、ROUTE_UNVERIFIED、ROUTE_MISMATCH |
| hook_status | enum | 是 | HOOK_ENFORCED、HOOK_UNAVAILABLE、HOOK_UNVERIFIED |
| guard_policy | object | 是 | Guard 触发和 fail-closed 规则 |
| audit_policy | object | 是 | 独立审计档位和证据要求 |
| created_by | actor id | 是 | 创建者 |
| created_at | timestamp | 是 | 创建时间 |

Manifest 规范化规则：

1. 字段按固定顺序编码。
2. 数组按声明顺序保留，不按自然语言排序。
3. 路径使用相对 POSIX 表示。
4. 空值按 schema 规则编码，不能临时省略必填字段。
5. 对规范化 UTF-8 字节做 SHA-256。
6. manifest_hash 不写回参与自身 hash 的字段内容。

## 4. TaskSpec

TaskSpec 逻辑字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| task_id | safe id | 任务唯一标识 |
| parent_task_id | safe id/null | 父任务 |
| manifest_hash | sha256 | 运行时绑定的当前 ScopeManifest hash；不参与 ScopeManifest 自身 hash |
| state_revision | integer | 创建时的状态版本 |
| role | think/execute/test/guard/audit/integrate | 职责 |
| stage | PRE_CONTRACT/CONTRACT_FROZEN/VERSION_FROZEN/INTEGRATION | 阶段 |
| D/I/A | enum | 路由三轴 |
| requested_model | string | 请求模型，不是运行凭证 |
| requested_effort | string | 请求 effort，不是运行凭证 |
| sandbox_mode | string | read-only、workspace-write 或项目允许值 |
| read_set | path[] | 只读输入 |
| write_set | path[] | 可写范围 |
| namespace | string[] | 受 lease 保护的可变命名空间 |
| dependency_ids | safe id[] | 必须完成的前置任务 |
| concurrency_group | string | 并发隔离组 |
| idempotency_key | safe id | 同一尝试的幂等键 |
| timeout_seconds | integer | 有界超时 |
| max_retries | integer | 最大重试次数 |
| side_effect_class | enum | none、local-write、external |
| acceptance_checks | string[] | 任务级检查 |
| evidence_requirements | string[] | 任务级证据 |

ScopeManifest 的 hash 先对不含自身 hash、且 task_specs 为无 hash TaskTemplate 的 payload 计算；随后 Controller 将该 hash 注入运行时 TaskSpec.manifest_hash。TaskSpec 冻结后，manifest_hash、write_set、namespace、side_effect_class 和 acceptance_checks 不能被执行 Agent 修改。

## 5. Lease

Lease 字段：

lease_id、task_id、namespace、owner_actor、issued_revision、issued_at、expires_at、last_heartbeat、status。

Lease 状态：

AVAILABLE、ACTIVE、EXPIRED、REVOKED、RELEASED。

规则：

- 一个 namespace 同时最多一个 ACTIVE lease。
- lease 过期后，任务先进入 UNKNOWN。
- 未确认旧进程停止时，不能发放新 lease。
- release 必须携带 task result revision。
- 迟到 heartbeat 或回写的 lease_id 不匹配时拒绝。
- lease 不能通过普通 prompt 约定替代。

## 6. HandoffPacket

HandoffPacket 必填字段：

task_id、parent_task_id、manifest_hash、state_revision、lease_id、base_revision、result_revision、status、changed_paths、diff_hash、artifact_hashes、test_receipts、evidence_refs、audit_receipt、route_provenance、hook_status、guard_decision、assumptions、open_questions、next_allowed_actions、budget_usage。初始 Handoff 的 audit_receipt 必须为 null；Controller 固定结果后进入 AUDIT_PENDING，独立审计再生成并附加 receipt；只有附加成功的 receipt 才允许 AUDIT_PENDING→ACCEPTED，避免 worker 与审计循环依赖。

status 取值：

SUCCEEDED、INCOMPLETE、BLOCKED、FAILED、CANCELLED、UNKNOWN。

Handoff 最低放行条件：

- status 为 SUCCEEDED；
- manifest_hash 与当前 run 一致；
- state_revision 没有过期；
- changed_paths 属于 write_set；
- diff 或 artifact hash 可复算；
- 必需测试有命令、退出码和结果；
- 没有未解决的 BLOCKED、UNKNOWN 或 open_questions；
- next_allowed_actions 不越过当前阶段；
- route_provenance 缺失时显式写 ROUTE_UNVERIFIED；实际值不符时写 ROUTE_MISMATCH。

## 7. GuardDecision

GuardDecision 字段：

guard_id、target_type、target_id、manifest_hash、state_revision、decision、reason_codes、findings、evidence_refs、checked_paths、checked_diff_hash、route_status、hook_status、created_at。

decision：

ALLOW、WARN、BLOCK、NEEDS_USER_DECISION。

硬阻断 reason codes：

SCOPE_DRIFT、WRITE_CONFLICT、LEASE_STALE、UNKNOWN_WRITER、INVALID_STAGE、CONTRACT_MISMATCH、MISSING_EVIDENCE、UNSAFE_SIDE_EFFECT、ROUTE_MISMATCH、AUDIT_REQUIRED。

软警告 reason codes：

ROUTE_UNVERIFIED、HOOK_UNVERIFIED、BUDGET_NEAR_LIMIT、OPTIONAL_CHECK_UNRUN。

RETRY_WITHOUT_NEW_EVIDENCE 是阈值型 reason：同一 task/attempt 第一次请求为 WARN，第二次及以后为 BLOCK 或 NEEDS_USER_DECISION。

Guard 不能返回 ACCEPTED、RELEASED 或通过整体验收的结论。

## 8. AuditReceipt

AuditReceipt 字段：

audit_id、auditor_actor、target_manifest_hash、target_result_revision、target_diff_hash、scope_result、behavior_result、evidence_result、route_result、findings、required_corrections、decision、provenance、created_at。

decision：

PASS、HOLD、REJECT、DEGRADED。

规则：

- AuditReceipt 必须来自未参与被审文件写入的只读审计责任人。
- 纠察 Agent 不能为同一版本签发独立 AuditReceipt。
- target_manifest_hash、result_revision 和 diff_hash 任一不匹配时，receipt 失效。
- PASS 只表示固定版本满足该审计范围，不自动代表真实运行路由通过。
- 缺少实际 model/effort provenance 时 route_result 必须是 ROUTE_UNVERIFIED。
- 审计发现需要修正时，修正后的版本必须重新生成 receipt。

## 9. StateEvent

StateEvent 字段：

event_id、run_id、task_id、manifest_hash、expected_state_revision、new_state_revision、actor_id、lease_id、from_state、to_state、reason、evidence_refs、idempotency_key、created_at。run、task、lease 各自拥有独立 revision；并发任务只 CAS 自己的 task_revision，run_revision 仅由 Controller 在 run 汇合时 CAS。event_seq 负责全局排序，不作为 worker 的 CAS 锁。

写入规则：

1. controller 在同一持久化事务内校验 CAS、更新实体、追加 event 和写入 outbox。
2. 事务提交后才向调用者返回成功；任何一步失败全部回滚，禁止出现 CAS 已提交但 event 缺失。
3. event_id 和 idempotency_key 重复时返回原结果，不重复执行。
4. 对应 entity revision 不匹配时拒绝并返回 STALE_REVISION；无关 task 的完成不能互相拒绝。
5. 任何外部副作用都先写 pending intent，必须记录 side_effect_class 和结果。

## 10. 事件与触发

必须触发 Deterministic Guard：

- task lease 创建、续租、释放；
- task 状态转移；
- changed_paths 产生；
- handoff 提交；
- retry 请求；
- merge 前；
- manifest revision 变化。

必须触发 Semantic Guard 或 Independent Audit：

- D/I/A 重新计算；
- 公共 schema、配置或共享状态变化；
- 外部副作用；
- lease 冲突或旧 writer 状态不明；
- 连续失败或没有新证据的重复重试；
- A1/A2 任务；
- 发布或用户要求验收。

## 11. 证据索引

每项证据索引至少有：

evidence_id、kind、source、manifest_hash、base_revision、result_revision、artifact_hash、command_or_ui_step、exit_code、observed_at、limitations、redaction_status。

证据类型：

TEST_RECEIPT、DIFF_RECEIPT、HASH_RECEIPT、GUARD_RECEIPT、AUDIT_RECEIPT、ROUTE_PROVENANCE、HOOK_PROBE、PROFILE_PROBE、USER_DECISION。

没有绑定固定版本的证据不能用于 RELEASED。没有 provenance 的模型配置只能说明 requested route。

## 12. 状态转移门禁

- DESIGN_PENDING → SCOPE_FROZEN：D 结论、非目标、路径和验收齐全。
- SCOPE_FROZEN → DISPATCHABLE：TaskSpec、依赖、concurrency_limit 和 guard policy 齐全。
- DISPATCHABLE → RUNNING：lease 和入口能力满足。
HANDOFF_READY 只表示 Task 已提交结构化 HandoffPacket 的证据条件，不是持久化 Run 或 Task 状态；满足校验后执行 Task RUNNING/CHECKPOINTED→WAITING_HANDOFF→AUDIT_PENDING。Run 状态门禁遵循 06 的 canonical flow：

- INTAKE → DESIGN_PENDING：收到目标但尚未冻结设计。
- DESIGN_PENDING → SCOPE_FROZEN：D 结论、非目标、路径和验收齐全。
- SCOPE_FROZEN → DISPATCHABLE：TaskSpec、依赖、concurrency_limit 和 guard policy 齐全。
- DISPATCHABLE → RUNNING：lease 和入口能力满足。
- RUNNING → EVIDENCE_COLLECTION：任务结果开始汇合。
- EVIDENCE_COLLECTION → AUDIT_HOLD：required 任务或证据缺失，需要阻断或补证。
- EVIDENCE_COLLECTION → READY_TO_MERGE：所有 required task 的 Guard/Audit 前置证据齐全。
- READY_TO_MERGE → INTEGRATED：main integrator 串行整合并通过受影响回归。
- INTEGRATED → RELEASED：全局测试、最终审计、必需 provenance 和通知证据齐全。

Task 状态使用 06 的 canonical flow：PLANNED → LEASED → RUNNING → CHECKPOINTED → WAITING_HANDOFF → AUDIT_PENDING → ACCEPTED；RETRYABLE、FAILED、HELD、UNKNOWN、SUPERSEDED、CANCELLED 是旁路状态。HANDOFF_READY 是 evidence condition，不是额外的持久化 Run 状态。

SUCCEEDED 只表示单个 Handoff 完成，不表示 Task ACCEPTED 或 Run 完成。可选检查必须在 manifest 中明确为 out-of-scope，不能用阶段通过冒充总验收。
