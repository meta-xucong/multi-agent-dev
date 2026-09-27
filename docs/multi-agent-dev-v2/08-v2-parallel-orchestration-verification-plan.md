# multi-agent-dev V2.1：并发编排验证与独立审计计划

状态：开发前验证契约，待实现后执行
适用对象：V2.1 并发 controller、worker、Guard、Audit 和主会话边界
contract_rev：v2.1.0-controlled-parallel（由 D07 唯一定义）
前置文档：06-controlled-parallel-orchestration-development.md、07-v2-parallel-orchestration-contracts.md

## 1. 验证原则

1. 每个测试绑定固定 manifest_hash、base_revision 和 result_revision。
2. 模拟 Agent 输出不能替代真实 Codex 运行时探针。
3. 配置中的 model、effort、Profile 和 Hook 不能当作实际运行凭证。
4. 并发测试必须验证竞态、迟到回写、lease 过期和重复事件。
5. 单个 task 成功不能替代全局 run 证据。
6. Guard 的 ALLOW/WARN/BLOCK 与 Audit 的 PASS/HOLD/REJECT/DEGRADED 分开验证。
7. 任何未运行项目必须明确记录为未验证，不得以无报错推断通过。

## 2. 测试环境记录

每次验证至少记录：

- 操作系统、Python 版本、Codex 版本和派发入口。
- V1 工作区 HEAD、V1 未提交差异摘要和 V2 manifest_hash。
- controller 配置、并发上限、状态目录和隔离临时目录。
- Hook trust 状态、Profile discovery 状态和 route provenance 来源。
- 测试命令、环境变量、退出码、stdout/stderr 摘要。
- 运行时可观察的 model、reasoning effort 和字段来源。
- 已脱敏的证据路径、局限和未覆盖事实。

## 3. 静态契约测试

| ID | 场景 | 预期 |
| --- | --- | --- |
| DOC-PAR-01 | 06、07、08、09 文档字段互核 | 名称、状态、模型档位、门禁和阶段一致 |
| DOC-PAR-02 | V1 保留映射 | 不改 V1，新增字段只在 V2 范围 |
| DOC-PAR-03 | D/I/A 交叉路由 | D、I、A 正交；高 D 禁止提前写，高 A 阻止放行 |
| DOC-PAR-04 | model/effort 配置 | requested 值与 runtime provenance 明确分离 |
| DOC-PAR-05 | Hook 降级 | unavailable/unverified 不写成 enforced/pass |
| DOC-PAR-06 | 文档链接和 schema | 所有引用路径存在，示例字段符合当前 contract_rev |

## 4. 纯函数与单元测试

### 4.1 Manifest 和 TaskSpec

- 合法 ScopeManifest 可以规范化并稳定计算 manifest_hash。
- 字段顺序、路径表示、空值和数组顺序变化有明确结果。
- 未知 contract_rev、缺字段、未知路径、D/I/A 非法组合必须拒绝。
- TaskSpec 的 write_set 必须是 allowed_paths 的子集。
- 共享 namespace、shared schema、状态库和 evidence 文件冲突必须识别。
- read-only task 不能声明 write_set 或 external side effect。
- task_id、run_id、lease_id 和 idempotency_key 必须通过安全 ID 校验。

### 4.2 Lease 和 CAS

- 同一 namespace 不能同时存在两个 ACTIVE lease。
- state_revision 不匹配返回 STALE_REVISION。
- 过期 lease 进入 UNKNOWN，未确认旧 writer 终止时不能重新派发。
- 迟到 heartbeat、release 和 handoff 被拒绝。
- 相同 idempotency_key 重放返回原结果，不重复执行。
- 不同 idempotency_key 的重复写入必须进入 Guard 冲突检查。

### 4.3 Handoff 和证据

- changed_paths 超出 write_set 必须 BLOCK。
- diff_hash、artifact_hash 和 result_revision 不匹配必须 HOLD。
- 缺少测试 receipt、evidence_refs 或 next_allowed_actions 必须 INCOMPLETE。
- route provenance 缺失时只能 ROUTE_UNVERIFIED。
- handoff 不得携带完整 prompt、SendKey、Token 或未脱敏个人路径。
- SUCCEEDED task 不能自动生成 RELEASED run。

### 4.4 Guard 和 Audit

- Guard reason code 稳定、可枚举、可复现。
- Guard 不返回 ACCEPTED 或 RELEASED。
- AuditReceipt 必须绑定目标 manifest、result_revision 和 diff_hash。
- 同一 writer 不得为同一版本签发独立 AuditReceipt。
- AuditReceipt 缺 provenance 时 route_result 必须为 ROUTE_UNVERIFIED。
- 版本变化后旧 AuditReceipt 自动失效。

## 5. 并发集成测试

| ID | 场景 | 预期 |
| --- | --- | --- |
| CONC-01 | 两个只读调查共享快照 | 并发完成，状态互不覆盖 |
| CONC-02 | 两个 disjoint write_set | 分离 worktree 并发，fan-in 后可整合 |
| CONC-03 | 同一文件两个 writer | 第二个 lease 被拒绝，Guard 返回 WRITE_CONFLICT |
| CONC-04 | 共享 schema 与普通模块并发 | schema owner 串行，依赖任务等待 |
| CONC-05 | 一个叶子失败，其他叶子成功 | 失败任务 RETRYABLE/HELD，不能伪造全局成功 |
| CONC-06 | fan-in 缺一个 required task | run 保持 EVIDENCE_COLLECTION 或 AUDIT_HOLD |
| CONC-07 | main integrator 只接收 READY_TO_MERGE | 未经 Guard/Audit 的差异不能进入整合 |
| CONC-08 | 同一事件重复投递 | event_id/idempotency_key 去重 |
| CONC-09 | 旧 revision 回写 | CAS 拒绝，当前状态不改变 |
| CONC-10 | 新用户指令改变范围 | 新 manifest revision，旧任务 SUPERSEDED/QUARANTINED |
| CONC-11 | 并发上限达到 | 新任务保持 PLANNED，不创建额外 Agent |
| CONC-12 | 低风险任务取消 | 可取消任务停止，writer 状态清理完整 |

## 6. 故障和恢复测试

- worker 进程在 write lease 中途崩溃。
- controller 在状态提交前崩溃。
- controller 在 event append 后重复重试。
- heartbeat 延迟、网络暂时不可用或进程输出超时。
- audit agent 没有返回 receipt。
- Hook 未加载、Hook 被绕过或 Hook 输出格式错误。
- Profile 文件存在但入口不支持。
- runtime provenance 不可读或实际值不匹配。
- ServerChan 通知失败、重复通知和 pending intent 恢复。
- worktree 删除、路径被移动或结果 artifact 缺失。

每个故障必须记录：

failure_id、触发状态、预期状态、实际状态、恢复动作、是否需要用户决定、是否产生新 manifest、最终证据。

## 7. Guard 触发测试

### 7.1 必须阻断

- 未授权路径写入。
- 同一 namespace 的重叠 lease。
- 旧 writer 未停止就重新派发。
- manifest_hash 或 contract_rev 不匹配。
- 直接外部副作用未经过 policy。
- 发现 ROUTE_MISMATCH 却试图以 ROUTE_UNVERIFIED 继续。
- required evidence 缺失却请求 RELEASED。

### 7.2 可以警告

- 路由 provenance 尚未可见。
- Hook 状态为 UNVERIFIED。
- 重试接近预算上限但已有新证据。
- 可选测试未运行且 manifest 明确其为 optional。
- controller 计划建议需要 Think 进一步澄清。

### 7.3 必须请求用户决定

- 用户新要求与冻结 non-goal 冲突。
- 需要改变公共契约或跨出 allowed_paths。
- 需要提交、推送、部署、安装 Profile 或信任 Hook。
- 需要取消已开始的外部副作用。
- 审计意见和用户硬约束发生冲突。

## 8. 模型与 effort 验证

对每个角色分别验证：

1. requested_model 和 requested_effort 被正确表达。
2. 子会话确实启动。
3. 可读取的 runtime provenance 字段明确说明是请求值还是运行值。
4. 实际值与目标值匹配。
5. Hook receipt、Profile 文件、任务名和 Agent 自述不能替代 provenance。
6. provenance 不可见时结果必须 ROUTE_UNVERIFIED。
7. 实际值不符时结果必须 ROUTE_MISMATCH，不能降级为未验证。

角色覆盖：

- Think：gpt-6-sol/xhigh。
- Execute：I0 low、I1 high、I2 xhigh、I3 max。
- Test：通常 gpt-6-luna/high，复杂 I2 测试才升 xhigh。
- Semantic Guard：A0 high、A1 xhigh、A2 max；route status 使用 D07 的完整枚举。
- Independent Audit：A0 high、A1 xhigh、A2 max。
- Controller 计划建议：gpt-6-luna/high；不直接决定状态或写入。
- Controller 状态机和通知器：无 LLM，使用确定性逻辑。

## 9. 前向工作流

除 V2 原有五个工作流外，增加五个并发/恢复工作流：

1. 精确小改动：只读检查并发，单 writer 低档执行，最终符号审计。
2. 语义有歧义：Think 未返回前，所有依赖执行任务保持 DESIGN_PENDING。
3. 明确复杂故障：事实收集和测试并行，恢复路径和公共状态串行。
4. Hook 故意不可用：使用已验证 Profile 或显式路径；没有 provenance 时保留 ROUTE_UNVERIFIED。
5. 范围跑偏：Guard BLOCK，停止受影响 writer，生成新任务或请求用户决定。
6. 两个独立模块并发修改：独立 worktree，fan-in 后统一测试和整合。
7. 一个共享 schema 加三个消费者：schema owner 串行，消费者等待版本。
8. worker 崩溃后恢复：checkpoint 续跑，禁止旧 writer 迟到回写。
9. 用户中途改变目标：新 manifest，旧任务隔离并记录 superseded。
10. audit agent 不可用：低风险只读可降级，高风险保持 AUDIT_HOLD。

## 10. 运行时探针

只有新鲜 Codex 会话中的真实行为可关闭运行时门禁：

- Hook matcher、输入字段、透明透传、拒绝和纠正。
- V1/V2 Hook 共存和拒绝合并顺序。
- Profile discovery、实际启动和运行 model/effort。
- 显式 model/effort route 和 provenance。
- controller 是否能维持 lease、CAS、恢复和并发上限。
- semantic guard 触发和 independent audit 隔离。
- 五个原有前向工作流与新增五个并发/恢复工作流。

读取配置、单元测试、模拟 payload 和工具返回 task name 不能关闭这些门禁。

## 11. 性能观察

首轮只报告观察结果，不承诺节省比例。至少记录：

- fan-out 到 fan-in 的总耗时。
- worker 等待依赖的时间。
- controller 调度开销。
- retry 次数和无效重试次数。
- Guard/Audit 拒收次数。
- Token、耗时和返工回合数。
- 并发冲突、lease 过期和状态恢复次数。
- V1/V2 对照任务的条件、样本数和环境。

质量、范围和证据指标优先于 Token 或耗时改善。

## 12. 最终放行条件

V2.1 只能在以下全部满足时报告功能完成：

- 纯函数、并发、恢复和证据测试全部通过。
- V1 回归通过且 V1 文件差异不变。
- 所有 required task 已绑定固定 result revision。
- 没有 ACTIVE 冲突 lease、UNKNOWN writer、HELD task 或 stale handoff。
- main integrator 完成整合并通过受影响回归。
- 独立 AuditReceipt 为 PASS，或按文档明确为 DEGRADED 并得到用户接受。
- 真实 Hook、Profile、model/effort provenance 的状态如实记录。
- 未验证项没有被写成通过。
- 运行时和前向工作流证据已追加到实施证据文档。
- 未经用户明确授权，不进行全局安装、信任、提交、推送或部署。
