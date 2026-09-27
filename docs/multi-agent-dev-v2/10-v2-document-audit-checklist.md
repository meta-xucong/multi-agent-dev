# multi-agent-dev V2.1：开发文档独立审计清单

状态：R2 审计执行协议，代码实施前必须完成
contract_rev：v2.1.0-controlled-parallel（由 D07 唯一定义）
审计对象：docs/multi-agent-dev-v2/01–10，以及 INDEX.md 的 V2 索引。D11 是本审计输出，05 是追加式证据日志；二者不作为自身输入 hash。
审计方式：独立、只读、固定版本；审计人不得修改文档、代码、全局配置或状态

## 1. 审计目的

确认文档可以直接指导 V2.1 并发编排代码实施，且：

1. 目标、非目标、范围、职责、状态和证据定义没有互相矛盾。
2. 主会话、Controller、worker、Guard 和 Independent Audit 的权限边界清楚。
3. 每个职责都有明确的 model/effort 请求值和 provenance 规则。
4. 并发、lease、CAS、隔离、恢复、fan-in 和单 writer 规则可实现。
5. Hook、Profile、真实 model/effort 和前向工作流门禁没有被模拟测试替代。
6. V1 保留要求、禁止事项、实施顺序和验收条件完整。
7. 文档中的路径、字段、状态、reason code、测试 ID 和引用可以互相对应。

审计通过只代表文档具备代码实施条件，不代表代码已经实现、运行时已经验证或 V2 已验收。

## 2. 固定审计输入

审计人必须先记录：

- 审计时间和审计 actor。
- 目标文档路径、文件字节 SHA-256、行数和最后修改时间。
- V2 package manifest hash 和当前 git status。
- 文档审计使用的 contract_rev。
- 审计使用的 model/effort requested 值和可见 runtime provenance。
- 审计命令、退出码和局限。

任何文档在审计期间发生改变，原审计立即失效，必须重新固定版本。

## 3. 结果枚举

| 结果 | 含义 | 后续动作 |
| --- | --- | --- |
| CONFORMING | 当前检查项与冻结契约一致 | 可以继续 |
| INCOMPLETE | 缺字段、缺证据或不能执行 | 不能关闭该门禁 |
| CONFLICT | 文档之间或与用户硬约束冲突 | 修正文档并全量重审 |
| PASS_FOR_CODE_START | 所有必需检查为 CONFORMING，未有未接受 CONFLICT | 允许进入 Phase 0 |
| HOLD_FOR_CODE_START | 有 INCOMPLETE 或用户尚未决定的项 | 不得开始代码 |
| REJECT_FOR_CODE_START | 存在未修复 CONFLICT 或越权规则 | 不得开始代码 |

审计 receipt 必须使用上述枚举；不能把没有运行时证据写成 PASS_FOR_RUNTIME。

## 4. 文档清单

| ID | 文档 | 主要职责 |
| --- | --- | --- |
| D01 | 01-requirements-and-architecture.md | 需求、D/I/A、主会话和原 V2 边界 |
| D02 | 02-development-plan.md | 阶段、顺序、交付和 V1 保护 |
| D03 | 03-verification-and-audit-plan.md | 原 V2 测试、Hook、Profile 和工作流门禁 |
| D04 | 04-v1-preservation-map.md | V1 文件、行为和修改保护 |
| D05 | 05-implementation-evidence.md | 历史与当前实施证据 |
| D06 | 06-controlled-parallel-orchestration-development.md | 并发架构、职责、模型和实现原则 |
| D07 | 07-v2-parallel-orchestration-contracts.md | ScopeManifest、TaskSpec、Lease、Handoff、Guard、Audit、Event |
| D08 | 08-v2-parallel-orchestration-verification-plan.md | 单测、并发、恢复、运行时和最终门禁 |
| D09 | 09-v2-implementation-task-breakdown.md | 目标文件、Phase 0–6、owner 和退出条件 |
| D10 | 10-v2-document-audit-checklist.md | 本审计协议 |
| IDX | INDEX.md | 阅读顺序、冻结原则和文档导航 |

D11 和 05 由主会话在审计完成后追加 receipt；它们的追加不会改变本次被审的 D01–D10/INDEX 输入版本。

## 5. 跨文档一致性矩阵

逐格核对并记录 PASS 或 finding：

| 检查项 | 必须一致的文档 | 核对内容 |
| --- | --- | --- |
| 目标与非目标 | D01/D02/D06/D09 | 并发提高吞吐，但主会话仍掌握用户授权和最终整合 |
| 主会话与 Controller | D01/D06/D09 | 一个意图/授权权威，一个状态/调度权威；不得有两个平权主控 |
| worker 写入边界 | D04/D06/D07/D09 | worktree、write_set、namespace 和 lease 对应 |
| D/I/A | D01/D06/D07/D08/D09 | D 高先冻结；I 越高越需要拆解，但 I0/I1 仅在 disjoint 且无共享状态时并发；A 高增加 Guard/Audit |
| 模型与 effort | D01/D06/D08/D09 | Main Luna/high、Think Sol/xhigh、Execute I0–I3 Luna low/high/xhigh/max、Test Luna/high、Guard/Audit A0–A2 Luna high/xhigh/max |
| 请求值与实际值 | D05/D06/D07/D08/D09 | requested 不等于 runtime provenance；缺失为 ROUTE_UNVERIFIED |
| Contract revision | D06/D07/D08/D09 | D07 唯一定义 v2.1.0-controlled-parallel；其他文档只引用，不重新定义；未知 revision 拒绝 |
| manifest 与 hash | D06/D07/D08/D09 | fixed fields、allowed/forbidden paths、base/result revision、不可自哈希 |
| lease 与 CAS | D06/D07/D08/D09 | 单 namespace ACTIVE、TTL、UNKNOWN writer、旧 revision 拒绝 |
| Handoff | D06/D07/D08/D09 | changed_paths、hash、测试、evidence、next actions、隐私 |
| Guard 与 Audit | D06/D07/D08/D09 | Guard 不签最终验收；Audit 独立只读并绑定版本 |
| Hook/Profile | D03/D05/D08/D09 | unavailable/unverified 显式降级，不能伪造 enforced/pass |
| V1 保护 | D02/D04/D06/D09 | 不改 V1，回归仍需运行 |
| 测试矩阵 | D03/D08/D09 | 原五工作流 + 新并发/恢复工作流，ID 可追踪 |
| 外部副作用 | D01/D06/D07/D08/D09 | 默认不做；需 policy、用户授权和证据 |
| 实施顺序 | D06/D09 | V2.1 Phase 0 冻结→schema→状态→Guard/Audit→adapter→整合→运行时；D02 的阶段仅适用于 V2.0 |

## 6. 逐项检查表

### 6.1 范围与权限

- [ ] 用户目标和明确 non-goals 可从 D01 映射到 D06/D09。
- [ ] allowed_paths、forbidden_paths 和 V1 preservation 不互相冲突。
- [ ] 主会话可冻结范围、指定 integrator 和向用户报告。
- [ ] Controller 可调度状态但不能改变用户目标或越过授权。
- [ ] worker 只能使用冻结 TaskSpec，不得自行派发 sibling 或扩 scope。
- [ ] Guard 只能给出 ALLOW/WARN/BLOCK/NEEDS_USER_DECISION。
- [ ] Independent Audit 不能由被审 writer 或同一 Guard 代签。
- [ ] 提交、推送、部署、安装和信任操作均有用户授权门禁。

### 6.2 并发正确性

- [ ] 每个 TaskSpec 有 read_set、write_set、namespace、依赖、超时和 retry。
- [ ] 同 namespace 的 lease 互斥；过期后旧 writer 不能迟到回写。
- [ ] CAS、state_revision、event_id 和 idempotency_key 的关系明确。
- [ ] 并发上限、ready queue、fan-out、fan-in 和取消行为可实现。
- [ ] 共享 schema、配置、状态库和证据文件有唯一 owner。
- [ ] worker/controller 崩溃恢复不会丢证据或重复副作用。
- [ ] 新用户要求产生新 manifest revision，旧任务隔离。

### 6.3 证据和审计

- [ ] handoff 绑定 manifest、base/result revision、diff/artifact hash。
- [ ] 测试 receipt 有命令、退出码、环境和局限。
- [ ] 运行时 provenance 与配置、Agent 自述和 task name 分开。
- [ ] Hook/Profile 读到但未实际运行时为 UNVERIFIED。
- [ ] route mismatch 不可降级成 unverified 或 pass。
- [ ] AuditReceipt 绑定目标版本，版本变化即失效。
- [ ] 缺证据只能 INCOMPLETE/HOLD/DEGRADED，不能假设通过。

### 6.4 隐私与状态清理

- [ ] 不记录 token、SendKey、完整 prompt 或未脱敏个人路径。
- [ ] pending intent 可恢复，通知失败不会伪造发送成功。
- [ ] lease、临时 worktree 和 checkpoint 在成功、取消、失败、UNKNOWN 后有清理策略。
- [ ] 清理失败保留可审计状态，不静默删除。
- [ ] 证据 redaction_status、limitations 和 source 字段齐全。

### 6.5 开发可执行性

- [ ] D09 每个 phase 都有 owner、模型/effort、文件、输入、动作、输出和退出门。
- [ ] D09 的 Phase 0 前置文档与 D11 审计报告路径一致，D11 缺失时不得开始代码。
- [ ] D08 每个 required 行为都有测试 ID 或运行时探针。
- [ ] D07 字段和状态能直接映射为代码 schema。
- [ ] D07 的 hash、revision、CAS、事务、handoff 和审计依赖没有循环或未定义并发域。
- [ ] D09 目标文件均在 V2 allowed_paths 或有新 manifest 流程。
- [ ] INDEX 能按建议顺序找到全部文档。
- [ ] 任何“可选”检查都不会被用作 required 放行依据。
- [ ] 代码开始前不需要猜测职责、状态、证据或模型档位。

## 7. 可执行性审计抽样

审计人至少执行以下只读动作：

1. 列出文档文件并核对 D01–D10、IDX 存在。
2. 计算所有文档 SHA-256 和行数。
3. 搜索所有 contract_rev、状态、decision、reason code、模型名和 effort。
4. 搜索引用的文件路径、测试 ID 和 phase 名称，确认定义与使用对应。
5. 对 D07 的样例字段与 D08/D09 的名称做精确比对。
6. 检查文档末尾、代码块、表格和列表无截断、重复或乱码。
7. 运行 git diff --check；只读记录，不自动修复。
8. 复算 V2 package manifest；确认文档审计没有改变代码包 hash。

## 8. Finding 分类和修正规则

每个 finding 至少包括：

finding_id、severity、document、section、observed_text、required_change、blocking、evidence_ref。

严重性：

- P0：会导致越权、错误写入、数据丢失或伪造验收；必须修复。
- P1：会阻止正确实现或造成状态/契约不一致；必须修复。
- P2：会造成可执行性歧义、证据缺口或可维护性风险；代码开始前应修复。
- P3：措辞或导航改进；若不影响执行可记录为 non-blocking。

修正规则：

1. 审计人只报告，不修改目标。
2. 主会话一次只修一批最小文档变更。
3. 每次修正重新计算受影响文档 hash，并重跑全量矩阵。
4. 文档 revision 变化会使旧 audit receipt 失效。
5. P0–P2 未关闭不得出具 PASS_FOR_CODE_START。

## 9. 审计 Receipt 最低格式

audit_id：
auditor_actor：
target_docs：
target_doc_hashes：
target_contract_rev：
v2_package_manifest_hash：
git_status_snapshot：
checks_run：
findings：
cross_document_result：
implementation_readiness：
runtime_provenance_status：
limitations：
decision：
created_at：

decision 必须是 PASS_FOR_CODE_START、HOLD_FOR_CODE_START 或 REJECT_FOR_CODE_START。若 auditor 没有真实 model/effort provenance，必须写 ROUTE_UNVERIFIED；这不自动否定文档静态审计，但不能被写成运行时验证。

## 10. 结束条件

只有以下全部满足，文档审计才能给 PASS_FOR_CODE_START：

- D01–D10 和 IDX 存在、可读、无截断。
- 跨文档矩阵没有 P0/P1/P2 冲突。
- 关键字段、状态、模型/effort 和测试 ID 可追踪。
- V1 preservation、全局配置限制和用户授权限制清楚。
- 文档 hash、V2 package hash 和 git status 已记录。
- audit receipt 已追加到 05-implementation-evidence.md。
- 没有把 ROUTE_UNVERIFIED、HOOK_UNVERIFIED 或未运行工作流写成通过。

若静态文档通过但 runtime provenance、Hook/Profile 或前向工作流尚未验证，文档状态仍只能是 PASS_FOR_CODE_START；V2 功能状态仍保持未验收。