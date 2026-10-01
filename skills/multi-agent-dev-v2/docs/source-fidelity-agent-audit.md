# Source Fidelity Agent 实现审计记录

## 审计范围

审查 `source_fidelity` 子 Agent 角色、路由 Profile、只读任务约束、来源 receipt 门禁与普通 Audit 的分工，未审查用户项目代码。

## 首次审计发现与修复

首次独立审计发现两项可复现绕过：source task 可请求与 Profile 不匹配的模型/强度，runtime gate 只比较 requested 与 observed，因而错误但相同的路由会误报合规；另有“自动创建 Agent”的文档表述超出原实现。修复如下：

- `source_fidelity` 不再作为 Controller DAG TaskTemplate role：避免来源凭证必须先于 handoff、但 DAG 依赖又等待实现 Task accepted 的循环；
- 来源敏感实现 TaskSpec 冻结 Reference/Target/Mapping hash；主控在写入者冻结结果后派发只读旁路 Source Fidelity 子 Agent，且在 handoff 前附上独立凭证；
- `RuntimeDispatchRequest` 把 runtime role 与专用 profile 集合绑定；Source Fidelity 不能借用普通 Audit profile；
- 新增 `bind-source-dispatch`：控制器将 Source Fidelity 角色、child thread、模型/强度 observed provenance 与 terminal 生命周期绑定到一个持久化证据引用；
- Handoff 现在同时要求该运行时派发证据和同一 child thread 的 SourceFidelityReceipt；只有完整自述 receipt、但没有 dispatch 证据时拒绝；
- 文档明确主会话负责识别用户原型意图并显式标记 source-sensitive；代码可强制已标记任务不漏派，但不能凭 diff 推断未声明的用户意图。

## 已核对

- `route_contract.py` 支持独立 `source_fidelity` 角色，并强制 `VERSION_FROZEN`、`D0`、A1/A2 Profile；
- 两个 Source Fidelity Profile 均为 gpt-6-luna、只读，A1 使用 xhigh，A2 使用 max；
- `parallel_manifest.py` 只接受合法的 source-sensitive 实现 TaskSpec；只读旁路角色的 A1/A2 模型、强度与 sandbox 由 Route Contract、Profile 和 Runtime Dispatch 检查；
- `runtime_dispatch.py` 强制 role/profile 与 requested model/effort/read-only 配置匹配，并核对 observed model/effort；但不观察实际 sandbox，因此只读仅为请求配置，不作为运行时证明；
- `SourceFidelityReceipt` 保留来源 commit、manifest、mapping、target、diff、run/task/revision 绑定；
- 普通 Audit 与 Source Fidelity 仍是两个独立证据门；
- 旧版本 receipt、来源清单、mapping、diff 或目标基线不匹配时继续 fail-closed。

## 最终独立复审与修订

早期实现曾把 Source Fidelity 子 Agent 表达为 Controller DAG 依赖。复审发现这一表达会导致 handoff/调度循环，因此已收敛为“写入者冻结结果 → 主控派发只读旁路子 Agent → 收到 PASS receipt → 正式 handoff → 普通独立 Audit”。Source Fidelity 仍不是普通 Audit；不合格或缺失凭证仍由 Controller handoff/receipt 门禁阻断。

独立只读复审初次返回 `FAIL`，发现完整静态 SourceFidelityReceipt 可以在没有 runtime child 绑定时放行、Source Fidelity 角色可误用普通 Audit Profile，且 sandbox 仅是 requested setting。修复后增加 role/profile 绑定、dispatch evidence、child-thread receipt 绑定与负例。结构完整的孤立伪造 receipt 现会被拒绝；信任边界收窄为：控制器必须从可信 Codex app-server 事件记录派发证据，证据字段本身不提供密码学签名。实际运行时 sandbox 仍未观察，不能声称已验证。

## 验证

```text
python -B -m unittest discover -s tests -p "test_*.py" -q
V2 full suite: 108/108 passed after source-role, dispatch evidence and no-DAG-cycle changes.
compileall: passed.
```

覆盖：Source Fidelity A1/A2 角色路由、错误角色/Profile/model/effort 拒绝、sidecar 不进入 Controller DAG、完整但无 runtime dispatch 绑定的伪造 receipt 阻断、正确 child route 与 receipt 绑定正例、来源凭证缺失/错绑阻断、Profile 元数据。该测试只证明本地确定性合同；本地 synthetic events 不证明 Codex 实际加载 Profile、实际 sandbox 或真实运行时来源。需要可信 runtime provenance 才可提升结论。

## 结论

最终独立复审：**PASS（代码与合同层，限定于可信事件入口）**。独立审计复跑 108/108 测试，并以临时 StateStore 执行 `init → dispatch-next → bind-start → bind-source-dispatch → handoff`；正确绑定进入 `AUDIT_PENDING`。完整 receipt 缺少 dispatch evidence、receipt child ID 不匹配、role/profile 不匹配均被拒绝。

以下仍非验收结论：事件无密码学签名，真实性依赖可信 app-server→controller ingress；实际 sandbox 未观测；Profile discovery、真实模型/effort provenance、Hook receipt 与五个前向工作流仍未验证。Source Fidelity 检查器默认不生成 `producer_thread_id`，Main 必须将其绑定到已验证 dispatch child ID，否则 fail-closed。真实运行时状态继续为 `NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED`。`bind-source-dispatch` 仅实现证据绑定，不等于真实 Codex 派发已通过。
