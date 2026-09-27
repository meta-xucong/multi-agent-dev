# multi-agent-dev V2 开发前文档

本文档组定义 V2.0 与 V2.1 受控并发编排的需求、设计、契约、实施边界和验收方式。当前状态为开发前文档冻结候选稿，不代表 V2 已实现或通过 Codex 运行时验证。

## 阅读顺序

1. [需求与架构决策](01-requirements-and-architecture.md)：目标、职责、D/I/A、路由档位、Hook 边界和降级原则。
2. [V1 保留与迁移映射](04-v1-preservation-map.md)：V1 文件、行为和回归证据保护。
3. [正式开发计划](02-development-plan.md)：V2 原有实现范围、阶段顺序和 Exit Gate。
4. [受控并行编排开发设计](06-controlled-parallel-orchestration-development.md)：主会话、Controller、worker、Guard、Audit 和并发模型。
5. [并行编排数据契约](07-v2-parallel-orchestration-contracts.md)：ScopeManifest、TaskSpec、Lease、Handoff、Guard、Audit 和 StateEvent。
6. [并行编排验证计划](08-v2-parallel-orchestration-verification-plan.md)：静态、单元、并发、恢复、运行时和前向工作流验证。
7. [实施任务分解](09-v2-implementation-task-breakdown.md)：目标文件、Phase 0–6、owner、模型/effort 和退出门。
8. [开发文档审计清单](10-v2-document-audit-checklist.md)：独立只读审计范围、矩阵、结果和 receipt 格式。
9. [开发文档审计报告](11-v2-design-document-audit-report.md)：固定文档版本的审计结果、修正记录和当前独立复审门禁。
10. [原 V2 验证与独立审计计划](03-verification-and-audit-plan.md)：Hook、Profile、运行时路由和原五个工作流门禁。
11. [实施证据](05-implementation-evidence.md)：历史和当前证据；不得把配置、模拟测试或自述写成真实运行时证明。

## 冻结原则

- V2.1 作为 V2 包内的受控并发扩展开发；V1 与工作区已有 V1 修改均保留。
- 主会话掌握用户意图、授权、范围冻结、最终整合和报告；Controller 掌握状态、依赖、lease、CAS、重试和恢复；不得存在两个平权主控。
- worker 只能在冻结 TaskSpec、write_set 和 namespace lease 内运行；共享资源使用单 writer。
- Deterministic Guard 做硬边界检查；Semantic Guard 事件触发并只读；Independent Audit 只审冻结版本，不能代替用户授权。
- requested model/effort 是路由目标，不是实际运行凭证；没有 runtime provenance 时必须标注 ROUTE_UNVERIFIED。
- Hook/Profile 不可用时按文档降级并保留证据；不可把 Hook 命中、配置存在、Agent 自述或模拟测试写成运行时通过。
- 代码开始前须完成文档独立审计并得到 PASS_FOR_CODE_START；这只表示可开始代码，不表示 V2 功能已验收。
- 未经用户明确授权，不安装 Profile、不改动或信任全局 Hook、不提交、不推送、不部署。

## 当前门禁

文档审计报告 D11 已创建并追加最终独立 receipt=PASS_FOR_CODE_START；这只关闭代码开始的文档门禁。V2 代码、Hook/Profile 真实运行、实际 model/effort provenance、前向工作流和最终 ACCEPTED 状态仍保持未关闭。

## 实现后交接

- V2 package references/parallel-orchestration.md：Controller、worker、lease、handoff 和 fan-in 操作说明。
- V2 package references/guard-and-audit.md：Guard/Audit 边界、绑定和拒绝规则。
- V2 package references/model-effort-routing.md：D/I/A 到 requested model/effort 与 provenance 的映射。
- [测试专员交接](12-v2-tester-handoff.md)：可重复命令、必测范围、结果规则和未关闭运行时门禁。
