# V2.2 Source Fidelity Agent 设计与实施文档

状态：实现完成，等待最后一轮独立复审

## 目标与范围

当用户要求严格移植、兼容、最大化复用，或明确指定 GitHub 仓库、固定 commit/tag、历史版本或本地原型时，增加专职只读 Source Fidelity Agent。它以冻结的原型与映射为基准，找出无依据新增逻辑、变量/方法改名、阈值、fallback、删减和协议漂移。

它不替代普通独立 Audit：Source Fidelity 只审“是否忠于来源及授权映射”，普通 Audit 继续审范围、质量、测试、安全和交付门禁。来源未覆盖或无法证明的能力保持 `BLOCKED`/`INSUFFICIENT_EVIDENCE`，不得自行补造。

## 触发与冻结输入

Main 根据用户明确意图决定是否启用；不得仅从 diff 自动推断。启用时在实现 TaskSpec 设置 `source_fidelity_required=true`，并冻结：来源仓库与 commit/tag、来源 manifest、目标基线和目标 manifest、SourceMappingMatrix 及其 hash、允许新增/删除项、回归测试和任务绑定。来源、目标、基线、映射 hash 必须分别记录。

每条映射归类为 `DIRECT_REUSE`、`THIN_ADAPTER`、`PLATFORM_SHELL` 或明确授权的 `AUTHORIZED_NEW`。无映射改动、来源缺口、来源/契约冲突、未经授权的新逻辑或解析能力不足均不得 PASS。

## 职责和路由

- Main：判断是否来源敏感；冻结 Reference/Target/Mapping；管理版本、dispatch、纠偏与放行。
- Execute：依据冻结映射实施；一次一个写入者。
- Source Fidelity：只读比较冻结参考和冻结目标版本，输出带证据的 `SourceFidelityReceipt`；不得修复、改映射或豁免。
- 普通 Audit：独立复查全局范围、质量、安全、测试和交付。

| 场景 | Profile | 请求模型/强度 |
| --- | --- | --- |
| 常规原型对照 A1 | `madv2_source_fidelity_a1_luna_xhigh` | `gpt-6-luna / xhigh` |
| Provider、计费、安全、公开契约 A2 | `madv2_source_fidelity_a2_luna_max` | `gpt-6-luna / max` |

## 调度：旁路子 Agent，不加入 Controller DAG

固定顺序：

```text
冻结参考/映射/基线
  -> Execute 实现
  -> Execute 冻结输出 revision
  -> Main 派发 Source Fidelity 只读请求旁路子 Agent
  -> 绑定 child 生命周期、role/profile 和 observed model/effort
  -> PASS receipt 与 runtime dispatch 同 child ID 绑定
  -> 正式 handoff / Guard
  -> 普通独立 Audit
```

Source Fidelity 不作为 Controller `TaskTemplate` 或 DAG dependency：实现 handoff 本身等待 Source Fidelity PASS，而 DAG 依赖又可能等待实现任务先 accepted，形成无法调度的循环。Main 在冻结输出后、正式 handoff 前调度旁路 child。控制器不自动识别用户原型意图、不自动创建该 child。

## 放行门禁与纠偏

源敏感 TaskSpec 必须冻结 Reference/Target/Mapping hash。正式 handoff 需要：

1. `SOURCE_FIDELITY_RECEIPT` 状态为 `PASS`，绑定同一 run/task/manifest、来源 commit/hash、mapping revision/hash、target/base hash、result revision 和 diff hash；
2. 一个 source-role runtime dispatch evidence，绑定专用 A1/A2 Profile、同一 task、child start/settings/terminal 事件、observed model/effort 和完成态；
3. Receipt `producer_thread_id` 与 runtime dispatch 中的 child thread ID 一致；receipt、dispatch、测试证据都出现在 handoff evidence refs 中；
4. Guard、AuditReceipt binding 和 merge-readiness 再验证同一版本绑定。

缺证据、错路由、过期版本或任何非 PASS 状态 fail-closed。纠偏只交给原写入者做边界明确的最小修复，修改后冻结新版本并重新执行 Source Fidelity；旧 receipt 不能复用。普通 Audit 仍需独立 PASS。

## 运行时与信任边界

当前 runtime adapter 观察 child lifecycle 和 model/effort settings；`read-only` 是 Profile/派发请求设置，不是已观察到的实际 sandbox 状态。Evidence source 和 producer role 字段不带密码学签名。`bind-source-dispatch` 将传入的 app-server events 规范化、校验并持久化；这依赖控制器从可信 Codex app-server 获取原始事件，不能把任意调用方合成的事件说成可信运行时凭证。不能确保此信任边界时，保持 `ROUTE_UNVERIFIED`/`INSUFFICIENT_EVIDENCE`。

该功能不安装 Profile、不改全局 Hook、不调用 Provider，也不把离线测试称为 Codex 实际运行时验证。
