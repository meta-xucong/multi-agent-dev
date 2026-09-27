# V2.1.8 运行时派发与子线程凭证加固开发文档

## 1. 目标与边界

本改造解决三个运行时证据缺口：子 Agent 的实际 model/effort 不可确认、父线程过早结束导致子线程生命周期不稳定、spawn 失败可能被误当成任务推进。

Hook 不在本章修复范围内。当前 Codex 派发链路未能证明 V2 Hook 可用，因此 Hook 作为 `HOOK_UNAVAILABLE` 或 `HOOK_UNVERIFIED` 的外部运行时状态单独记录。

不改动：V1 六个既有修改、SQLite 状态机语义、真实 Provider、全局 Hook/Profile、Git 历史和外部部署。

## 2. 冻结契约

- 只能接受冻结 TaskSpec 中的 requested model/effort；模型生成的 spawn 参数不是 observed provenance。
- 子线程必须有实际启动证据；仅有任务名或调用返回值不够。
- 必须从子线程 runtime settings 读取 model 和 effort，并与 requested 值逐项比较。
- 子线程必须先产生 terminal turn 事件，父线程才允许关闭。
- 无子线程、缺少设置、路由不匹配、spawn failure、父线程提前关闭，均保持 gate hold。
- 只有 `CHILD_COMPLETED` 且 `EXPLICIT_ROUTE_VERIFIED`/`PROFILE_VERIFIED` 才可作为可接纳运行结果。

## 3. 最小实现

1. `scripts/runtime_dispatch.py`
   - `RuntimeDispatchRequest` 固化父线程、任务、profile 和 requested route。
   - `RuntimeDispatchSession` 解析 `thread/started`、`subAgentActivity`、`thread/settings/updated`、terminal turn 和 spawn failure 事件。
   - `RuntimeDispatchResult` 输出生命周期、observed route、route status、blockers 和 evidence refs。
   - `close_parent()` 阻止子线程终态前的父线程关闭。
   - `require_admissible()` 对缺证据和 mismatch fail-closed。
2. `scripts/orchestrate.py`
   - 增加只读 `runtime-gate` 操作，把运行时事件转换为统一 gate 结果；不直接写账本，不调用 Provider。
3. `references/runtime-dispatch.md`
   - 固化运行时顺序、证据来源和 Hook/route provenance 分离规则。

## 4. 测试与验收

必须覆盖：

- matching child settings + terminal event → `EXPLICIT_ROUTE_VERIFIED`；
- 缺 settings → `ROUTE_UNVERIFIED`；
- observed mismatch → `ROUTE_MISMATCH`；
- 无 child / spawn failure → `SPAWN_FAILED` 或 `CHILD_THREAD_NOT_STARTED`；
- 仅有 child id、没有启动事件 → 阻断；
- 未带 parent scope 的 `subAgentActivity` → 阻断；
- 只有 `thread/started` 携带的 model/effort → 仍为 `ROUTE_UNVERIFIED`；
- 子线程启动后再报告 spawn failure → 持续 `SPAWN_FAILED` 门禁；
- 冲突 settings 更新、父线程先终态 → fail-closed；
- 父线程提前关闭 → `PARENT_CLOSE_BEFORE_CHILD_TERMINAL`；
- terminal 后关闭父线程 → 允许；
- CLI `runtime-gate` 对 mismatch 返回 `GATE_HOLD`。

验证命令：

```text
python -B -m unittest discover -s skills\\multi-agent-dev-v2\\tests -p test_*.py -q
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
chcp 65001 >NUL
python -B -X utf8 -m unittest discover -s skills\\multi-agent-dev\\tests -p test_*.py -q
python -B -m compileall -q skills\\multi-agent-dev-v2
git diff --check
```

本章不把 Hook receipt、Profile 文件、Agent 自述或 requested 参数当作实际 route provenance。真实 Codex 子线程仍须由目标运行时提供 child settings 和 terminal event 后，才能关闭运行时门禁。

## 5. 审计要求

独立审计必须检查新增模块没有：

- 把 requested route 当成 observed route；
- 把父线程或普通事件误认成子线程；
- 在 child 未终态时允许关闭父线程；
- 将 spawn failure 转成成功；
- 引入 Provider、网络、全局配置或持久化副作用；
- 通过新增测试绕过原有 V2 验收门禁。

审计结论只能是 `PASS`、`FAIL` 或 `INSUFFICIENT_EVIDENCE`。即使本章代码审计通过，Hook 和真实 Codex 子线程 provenance 仍按实际运行时结果单独判定。
