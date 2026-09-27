# multi-agent-dev V2.1：并发编排实施任务分解

状态：R2 开发前实施蓝图，待 D11 独立审计 PASS_FOR_CODE_START 后执行
contract_rev：v2.1.0-controlled-parallel（由 D07 唯一定义）
适用范围：skills/multi-agent-dev-v2/ 内新增或修改的 V2 代码、测试和引用文档
前置文档：01–08；执行顺序由本文件与 D06/D07 共同约束，D06 §16 与本文件 Phase 0–6 必须一致

## 1. 实施边界

1. 只修改 V2 包及本 V2 文档；保留既有 V1 用户修改。
2. 不覆盖、回滚、格式化或重命名 V1 文件。
3. 不安装 Profile，不改动或信任用户全局 Hook，不提交、推送或部署。
4. 不把模拟测试、Agent 自述、任务名或配置文件当作运行时 provenance。
5. 任何公共契约、路径范围、验收标准变化都先更新 ScopeManifest 和文档，再改代码。
6. 每个实施任务都必须有唯一 owner、固定 write_set、明确依赖和可复核 receipt。
7. 任务失败时保留失败证据；不得删除或覆盖以前的结果来伪造成功。

## 2. 角色与路由分工

| 角色 | 责任 | 建议 model/effort | 写入权限 |
| --- | --- | --- | --- |
| 主会话 | 用户意图、授权、范围冻结、最终整合和报告 | gpt-6-luna/high（建议） | 仅用户明确允许的整合范围 |
| Controller 状态机 | DAG、依赖、lease、CAS、重试、恢复 | 无 LLM | 仅状态目录和事件 ledger |
| Controller 计划建议 | 提供拆分建议，不改变状态 | gpt-6-luna/high | 无代码写入、无审批权 |
| Think | 澄清事实、方案和风险 | gpt-6-sol/xhigh | 仅自己的分析 artifact |
| Execute I0 | 小型确定性修改 | gpt-6-luna/low | 任务 write_set |
| Execute I1 | 常规单模块实现 | gpt-6-luna/high | 任务 write_set |
| Execute I2 | 复杂跨模块实现 | gpt-6-luna/xhigh | 任务 write_set，经 lease |
| Execute I3 | 高风险或公共契约实现 | gpt-6-luna/max | 任务 write_set，经用户/审计门禁 |
| Test | 测试、复现和回归 | gpt-6-luna/high；复杂 I2 用 xhigh | 测试 artifact，不改被测实现 |
| Deterministic Guard | 路径、schema、状态、lease 和证据硬检查 | 无 LLM | 只写 guard receipt |
| Semantic Guard A0/A1/A2 | 事件触发的漂移和语义风险检查 | gpt-6-luna/high/xhigh/max | 只写只读 findings |
| Independent Audit A0/A1/A2 | 冻结版本的独立代码、证据和路由审计 | gpt-6-luna/high/xhigh/max | 只写独立 audit receipt |
| 通知器 | 发送并记录通知结果 | 无 LLM | 只写通知状态 |

requested model/effort 只表达目标路由；真实值必须由 runtime provenance 证明。证明缺失时写 ROUTE_UNVERIFIED。

## 3. 目标目录与文件职责

下列为第一实现目标。创建新文件前先确认路径仍在 allowed_paths；若路径变化，先生成新的 manifest revision。

| 目标文件 | 单一职责 | owner |
| --- | --- | --- |
| scripts/parallel_manifest.py | ScopeManifest、规范化和 hash | Controller |
| scripts/task_spec.py | TaskSpec schema、校验和 DAG 依赖 | Controller |
| scripts/lease_store.py | namespace lease、TTL、heartbeat、revoke | Controller |
| scripts/state_store.py | CAS、StateEvent、幂等回放 | Controller |
| scripts/task_scheduler.py | ready queue、并发上限、依赖和 retry | Controller |
| scripts/handoff_contract.py | HandoffPacket、证据索引和状态检查 | Controller |
| scripts/guard_contract.py | GuardDecision、reason code、触发器 | Deterministic Guard |
| scripts/semantic_guard.py | 事件触发的只读语义检查 | Semantic Guard |
| scripts/audit_receipt.py | AuditReceipt schema、目标绑定和失效校验 | Controller（确定性实现） |
| scripts/route_provenance.py | requested/runtime 路由字段和状态 | Controller/Test |
| scripts/notification_state.py | pending intent、去重和失败恢复 | 通知器 |
| references/parallel-orchestration.md | 面向执行 Agent 的操作说明 | 主会话 |
| references/guard-and-audit.md | Guard/Audit 边界和拒绝规则 | 主会话 |
| references/model-effort-routing.md | D/I/A 到 model/effort 的映射和证据要求 | 主会话 |
| tests/test_parallel_manifest.py | manifest/hash/schema 单测 | Test |
| tests/test_task_spec.py | TaskSpec、DAG 和冲突单测 | Test |
| tests/test_lease_store.py | lease 生命周期、冲突和迟到回写 | Test |
| tests/test_state_store.py | CAS、event 去重和崩溃恢复 | Test |
| tests/test_handoff_contract.py | handoff、证据和隐私检查 | Test |
| tests/test_guard_contract.py | Guard 决策和 reason code | Test |
| tests/test_semantic_guard.py | 事件触发和只读语义 findings | Test |
| tests/test_audit_receipt.py | 审计隔离、绑定和失效 | Test |
| tests/test_route_provenance.py | requested/runtime/unknown/mismatch | Test |
| tests/test_concurrency_integration.py | fan-out、fan-in、writer 冲突 | Test |
| tests/test_recovery.py | worker/controller/通知恢复 | Test |
| tests/test_parallel_metadata.py | V2 manifest、证据和 V1 不变性 | Test |

文件名是实现蓝图；若复用现有脚本而不新建文件，必须在实施证据中记录等价映射。

## 4. Phase 0：冻结文档和基线

负责人：主会话 + Controller（无 LLM 状态机）
输入：01–11 审计通过候选、当前 git status、V2 manifest
动作：

1. 复算 V2 包 manifest hash 和 V1 差异摘要。
2. 创建 ScopeManifest revision 1，锁定 goal、non_goals、allowed_paths、forbidden_paths。
3. 生成 task_specs、依赖 DAG、concurrency_limit、evidence_requirements。
4. 写入 baseline receipt 和 document audit receipt。
5. 任何文档冲突、V1 差异变化或路径不明都进入 BLOCK。

输出：scope receipt、manifest hash、base tree hash、初始 DAG、未决问题清单。
退出门：D 结论完成，manifest_revision=1，所有 required 字段存在。

## 5. Phase 1：实现纯 schema 与完整性函数

负责人：Controller；审核：Test；建议执行路由 I1 gpt-6-luna/high
文件：parallel_manifest.py、task_spec.py、route_provenance.py
动作：

1. 实现固定字段顺序和规范化 UTF-8 编码。
2. 实现 safe id、path、D/I/A、contract_rev 校验。
3. 实现 write_set 属于 allowed_paths、read-only 约束和依赖 DAG 校验。
4. 实现 requested/runtime provenance 的区分和 ROUTE_UNVERIFIED/ROUTE_MISMATCH。
5. 禁止 schema 函数读取隐式全局配置或修改文件。

输出：纯函数单测、固定样例 hash、拒绝样例 receipt。
退出门：DOC-PAR-01/03/04/06、纯函数 4.1 通过。

## 6. Phase 2：实现状态、lease 和调度

负责人：Controller；审核：Test；建议执行路由 I2 gpt-6-luna/xhigh
文件：lease_store.py、state_store.py、task_scheduler.py
动作：

1. 实现 ACTIVE lease 唯一性、TTL、heartbeat、revoke 和 UNKNOWN writer。
2. 实现 CAS 状态变更、StateEvent 追加、event/idempotency 去重。
3. 实现依赖就绪、并发上限、retry budget、cancel 和 superseded。
4. 将外部副作用状态设为 pending intent，重启后可恢复。
5. 任何旧 revision 回写必须拒绝并返回可审计错误。

输出：lease/CAS receipt、事件 ledger、恢复 checkpoint、冲突样例。
退出门：纯函数 4.2、CONC-01/03/08/09/11、故障恢复基础项通过。

## 7. Phase 3：实现 handoff、Guard 和审计边界

负责人：Controller/Deterministic Guard；Independent Audit 只读审核；审核：Test；I/A 路由按 manifest
文件：handoff_contract.py、guard_contract.py、semantic_guard.py、audit_receipt.py（Independent Audit 不写实现代码）
动作：

1. 严格校验 changed_paths、diff/artifact hash、result revision 和 evidence refs。
2. 让 Guard 只能产生 ALLOW/WARN/BLOCK/NEEDS_USER_DECISION。
3. 让 Audit 只能审只读冻结版本，绑定目标 hash/revision/diff。
4. 同一 writer、纠察 Agent 和被审实现者不得签发同版本独立 receipt。
5. 在缺少 route provenance、Hook 或 Profile 证据时显式降级，不伪造通过。

输出：Guard receipts、AuditReceipt 样例、BLOCK/WARN/NEEDS_USER_DECISION 样例。
退出门：纯函数 4.3/4.4、DOC-PAR-05、Guard 触发 7、审计隔离通过。

## 8. Phase 4：实现 worker adapter 与隔离执行

负责人：主会话 + Execute；建议 Execute I1/I2 gpt-6-luna high/xhigh；审核：Guard/Test
动作：

1. controller 只派发冻结 TaskSpec；worker 不能自行扩 scope 或创建 sibling task。
2. 为每个可写任务创建隔离 worktree 或等价 namespace。
3. worker 输出结构化 HandoffPacket，包含 command、退出码、diff/hash 和未决项。
4. worker 崩溃、超时或 lease 过期时，停止接受旧 writer 回写。
5. 不在 adapter 中写入 token、SendKey、完整 prompt 或未经脱敏个人路径。

输出：worker launch receipt、隔离目录映射、handoff receipts、隐私扫描结果。
退出门：CONC-02/04/05/07/12、隐私测试和 worker 崩溃恢复通过。

## 9. Phase 5：实现 fan-in、整合和回归

负责人：main integrator（主会话指定，gpt-6-luna high；I2 冲突用 xhigh）；审核：Independent Audit A0/A1/A2 按风险档位
动作：

1. 只接收 Run=READY_TO_MERGE 且 Task=ACCEPTED、拥有完整 Guard/Audit receipt 的候选；READY_TO_MERGE 不是 Task 状态。
2. 按依赖顺序、namespace 和公共 schema owner 串行整合。
3. 每次整合前运行 Guard；整合后更新 result_revision 和 diff hash。
4. 运行 V2 全套测试、V1 回归、compileall 和 git diff --check。
5. 不将测试通过直接写为 runtime Hook/Profile/model/effort 通过。

输出：整合 receipt、V2/V1 测试 receipt、最终差异摘要、受影响路径列表。
退出门：CONC-06/07/10、全局回归和审计前置检查通过。

## 10. Phase 6：运行时探针和验收

负责人：主会话（建议 gpt-6-luna high）；只读参与：Independent Audit A0/A1/A2；Controller 状态机无 LLM
动作：

1. 在新鲜 Codex 会话中完成 Hook、Profile、真实 model/effort provenance 和并发探针。
2. 运行 08 的十个前向工作流（原五个 + 新五个）及 D03 保留的 V2 五个工作流。
3. 将真实证据追加到 05-implementation-evidence.md。
4. 若实际路由不匹配，状态为 ROUTE_MISMATCH；若不可见，状态为 ROUTE_UNVERIFIED。
5. 只有用户授权的外部操作才可执行；默认不安装、信任、提交、推送或部署。

输出：runtime probes、workflow receipts、独立 AuditReceipt、最终状态。
退出门：08 第 12 节全部条件满足；否则保持 HOLD/DEGRADED。

## 11. 单 writer 与共享资源映射

| 资源 | 唯一 owner | 其他任务 |
| --- | --- | --- |
| manifest、ScopeManifest | 主会话/Controller | 只读 |
| state ledger、lease store | Controller | 只读，不直接编辑 |
| shared schema、公共配置 | 指定 schema owner | 依赖后读取 |
| 单个模块文件 | 该模块 Execute task | 不得声明重叠 write_set |
| 测试结果目录 | Test | 其他角色只读 |
| Guard/Audit receipts | 对应 Guard/Audit | 不可代签 |
| 实施证据文档 | 主会话串行 writer | 其他角色提交 append proposal |
| 通知状态 | 通知器 | 只通过 API 更新 |

## 12. 失败、重试和升级

- 可重试错误：暂时不可用、worker 崩溃、无副作用的超时；必须有新 attempt id 和新证据。
- 不可重试错误：范围越界、契约不匹配、旧 writer 回写、route mismatch；直接 BLOCK 或请求用户决定。
- 连续两次无新证据的重试：Semantic Guard 标记 RETRY_WITHOUT_NEW_EVIDENCE。
- worker UNKNOWN：保持 namespace 隔离，不能盲目释放 lease。
- controller UNKNOWN：从最后一个 CAS/event checkpoint 恢复，重复 event 必须幂等。
- 审计没有 receipt：高 A 任务 AUDIT_HOLD；低风险只读可按 manifest 明确降级。
- 任何新要求：创建新 manifest revision，旧任务标记 SUPERSEDED/QUARANTINED。

## 13. 实施顺序与禁止事项

必须按 Phase 0→1→2→3→4→5→6 顺序推进；同一 phase 内可对 disjoint 文件并发，但共享契约先于 worker。

开始代码前必须满足：

- 01–10 文档和 INDEX 的独立审计结论为 PASS_FOR_CODE_START；D11 输出报告、D05 追加证据 receipt。
- INDEX 已更新，所有引用路径存在。
- git status 已记录，V1 差异未被改动。
- 当前 V2 package hash 和文档 hash 已记录。
- 未关闭的用户决定、路径、模型/effort 运行时证据门禁不得被静默跳过。

禁止：两个平权 controller、worker 自行派发 sibling、共享 main 直接并发写、用 prompt 代替 lease、常驻 LLM 纠察、Guard 代替独立 Audit、无 provenance 宣称真实路由通过。

## 14. Phase 路由与 exit receipt

| Phase | owner/model/effort | 必备输出 | Exit gate |
| --- | --- | --- | --- |
| 0 | 主会话 + Controller/无 LLM | baseline、scope_hash、D11 receipt | 文档 PASS、V1 基线固定 |
| 1 | Controller/无 LLM；schema Execute I1 Luna/high | schema golden vectors、纯函数 receipt | D07/UNIT gate 通过 |
| 2 | Controller/无 LLM；实现 I2 Luna/xhigh，Test high | CAS/lease/recovery receipts | STATE/LEASE/SCHED gate 通过 |
| 3 | Controller/无 LLM；Guard/Audit 按 A0/A1/A2 Luna high/xhigh/max | handoff、Guard、Audit receipts | 独立性与绑定通过 |
| 4 | 主会话 + Execute I1/I2 Luna high/xhigh；Test high | adapter、隔离、worker receipts | writer/fence/隐私通过 |
| 5 | Integrator Luna high（I2 xhigh）；Audit A0/A1/A2 | integration、回归和差异 receipts | Run READY_TO_MERGE，Task ACCEPTED |
| 6 | 主会话 Luna high；runtime probes 与 Audit 按 A 档 | Hook/Profile/provenance/workflow receipts | D08 Final gate；未验证保持 HOLD |

## 15. Phase exit receipt 最低字段

phase_id、manifest_hash、input_revision、output_revision、owner_actor、requested_model、requested_effort、route_status、test_receipts、guard_receipts、audit_receipts、changed_paths、diff_hash、open_questions、next_allowed_actions、created_at。

每个 phase exit receipt 都写入 05-implementation-evidence.md 的追加段落；若 route_status 为 ROUTE_UNVERIFIED，不得标记为运行时完成。实施证据只由主会话串行追加，审计人通过独立 receipt 引用，不直接改写 evidence。