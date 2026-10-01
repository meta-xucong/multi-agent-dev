# V2.2 Source Fidelity Agent 独立审计记录

审计对象：V2 Source Fidelity 旁路角色、模型/profile route contract、冻结来源检查、Receipt 与 Handoff/Audit binding。

## 已实施的缺陷修复

独立初审发现：

1. 将 Source Fidelity child 作为 Controller DAG dependency 会与“receipt 必须先于 handoff”形成调度循环；已改为 writer 冻结结果后、正式 handoff 前由 Main 派发只读请求旁路 child。
2. 完整静态 PASS SourceFidelityReceipt 曾能在无 child dispatch evidence 时通过；现在 handoff 要求同一任务/manifest/revision 的 runtime dispatch evidence，receipt 的 `producer_thread_id` 必须等于该 terminal child ID。
3. RuntimeDispatchRequest 未绑定角色，普通 Audit profile 曾可用于 Source Fidelity；现在 Source Fidelity role 只接受专属 A1/A2 profiles 和匹配 model/effort/read-only 请求。
4. 运行时事件只提供模型/强度和 child 生命周期，不提供实际 sandbox provenance；文档和输出明确为“requested read-only, sandbox unobserved”。

## 本轮本地验证

```text
python -B -m unittest discover -s skills/multi-agent-dev-v2/tests -p "test_*.py" -q
108/108 passed

python -B -m compileall -q skills/multi-agent-dev-v2
passed
```

覆盖包括：A1/A2 role/profile 绑定、错误角色和错误路由拒绝、Source Fidelity 不进入 DAG、孤立完整伪造 PASS receipt 缺少 dispatch 时阻断、合法 source-role runtime evidence 与 receipt 的 child-thread 绑定正例、源映射/hash/测试证据 fail-closed。

## 独立复审状态

独立只读复审结论：**PASS（代码与合同层，限定于可信事件入口）**。复审确认 Source Fidelity sidecar 不在 DAG；孤立 PASS receipt、child ID 错绑与 role/profile 不匹配均被拒绝；合法 source-role dispatch + receipt 完整 handoff 实测进入 `AUDIT_PENDING`（Hook 未验证导致 Guard WARN 属预期）。全包测试 `108/108`，compileall 退出码 `0`。

本地测试为合成隔离输入，不证明 Codex 真正发现 Profile、实际加载模型/effort，也不证明实际 sandbox。`producer_role`、`source` 和本地 evidence row 并非密码学身份；event hash 只封存输入内容，不证明事件来自官方 app-server。运行时真实性仍依赖受信 Controller/app-server 取证路径。Source Fidelity 检查器默认不生成 `producer_thread_id`；Main 必须按已验证 dispatch child ID 补绑，否则门禁拒绝。

代码级 PASS 不等于运行时验收或 `ACCEPTED`。真实运行时状态继续为 `NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED`，直至真实 Hook/Profile/model/effort 与五个前向工作流有可核验证据。
