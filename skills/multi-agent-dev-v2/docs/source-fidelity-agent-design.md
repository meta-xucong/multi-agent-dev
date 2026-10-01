# V2 Source Fidelity Agent：正式设计文档

## 目标

当任务要求严格移植、兼容、复刻或以 GitHub/历史版本/本地原型为行为依据时，增加一个独立的只读子 Agent，持续比较“冻结原型—目标基线—当前改动”，阻止自行发明逻辑、变量、阈值、回退和协议。

它不是普通 Audit 的别名，也不是执行 Agent 的自检。普通 Audit 检查需求、代码、测试和安全边界；Source Fidelity Agent 只回答：当前实现是否仍忠于冻结参考原型，以及偏差是否有明确授权。

## 触发规则

出现以下任一情况，Main 必须将相关实现 TaskSpec 标记为 source-sensitive；执行 Agent 冻结目标版本后，Main 必须派发 `source_fidelity` 只读旁路子 Agent，在正式 handoff 前完成比对：

- 用户指定 GitHub 仓库、commit、tag、历史版本或本地原型；
- 用户要求“严格移植”“最大化复用”“保持原逻辑/变量/参数”；
- 兼容性、Provider 协议、计费规则、公开契约或安全规则以来源实现为事实依据。

没有参考原型的新功能不创建该 Agent，避免无意义消耗。是否存在参考原型是用户意图判断，不能仅从 diff 推断；Main 必须在冻结范围时显式记录并设置 `source_fidelity_required=true`。控制器不能自动判断意图或自动创建子 Agent。

## 固定职责

Source Fidelity Agent 必须：

1. 读取冻结的 `ReferenceSpec`、SourceMappingMatrix、目标基线和当前版本；
2. 验证来源 commit、来源清单、目标清单、基线清单、mapping hash 和 diff hash；
3. 检查直接复用的符号、片段、结构、运算符、标识符和字面量；
4. 检查薄适配是否只发生在明确的平台边界；
5. 找出未经授权的新增变量、方法、阈值、分支、fallback、重命名、删减和协议改变；
6. 返回绑定同一 run/task/manifest/result revision/diff 的 `SourceFidelityReceipt`。

它禁止：

- 修改代码、测试、文档、mapping 或验收标准；
- 执行来源仓库的 Hook、安装器、构建脚本、Provider 或网络调用；
- 用“看起来合理”替代缺失的来源证据；
- 把 BLOCK、WARN 或 INSUFFICIENT_EVIDENCE 改写成 PASS。

## 调度与模型

| 场景 | Profile | 模型/强度 |
| --- | --- | --- |
| 普通来源对照 | `madv2_source_fidelity_a1_luna_xhigh` | gpt-6-luna / xhigh |
| Provider、计费、安全、公开契约迁移 | `madv2_source_fidelity_a2_luna_max` | gpt-6-luna / max |

Source Fidelity 旁路子 Agent 必须以 `VERSION_FROZEN`、`D0`、`I1`、A1 或 A2、请求的 `read-only` sandbox、无写集合、无外部副作用运行。A1 固定 `gpt-6-luna/xhigh`，A2 固定 `gpt-6-luna/max`。Route contract 与 runtime dispatch gate 将 role、profile、requested model/effort 绑定；runtime event 观察模型/强度和生命周期，但当前不观察实际 sandbox。该只读子 Agent 不作为 Controller DAG TaskTemplate：若它依赖实现任务完成，而实现 handoff 又必须等待它的 PASS，会形成无法调度的循环。来源敏感标记仍冻结在实现 TaskSpec；Handoff Gate 对缺少 SourceFidelityReceipt、同一 child runtime dispatch 或线程 ID 不匹配 fail-closed。事件由可信控制器从 Codex app-server 导入是当前信任边界，证据不带密码学签名。Hook 不可用时仍可执行静态来源审查，但 Hook 状态保持独立；实际 runtime provenance 未观察到时继续为 `ROUTE_UNVERIFIED`。

## 纠偏闭环

```text
冻结来源与映射
  -> Source Fidelity 只读对照
  -> PASS：进入普通 Audit
  -> BLOCK/INSUFFICIENT_EVIDENCE：停止受影响路径
  -> Main 记录证据并给 Execute 有界修复
  -> 生成新版本、重新做 Source Fidelity
  -> 新版本通过后才允许普通 Audit/集成
```

任何新版本都会使旧 receipt 失效。Source Fidelity PASS 不能替代普通 Audit；普通 Audit PASS 也不能替代 Source Fidelity PASS。

## 实现入口

- 路由合同：`scripts/route_contract.py` 的 `source_fidelity` 角色；
- 任务合同：`scripts/parallel_manifest.py` 冻结实现 TaskSpec 的 source-sensitive 输入；只读旁路角色由 route/runtime-dispatch contract 约束；
- 来源检查器：`scripts/source_fidelity.py`；
- 证据绑定：`scripts/state_store.py`、`scripts/semantic_guard.py`、`scripts/task_scheduler.py`；
- 独立 Profile：`profiles/madv2_source_fidelity_a1_luna_xhigh.toml`、`profiles/madv2_source_fidelity_a2_luna_max.toml`。

## 验收标准

- 来源敏感实现缺少已绑定 PASS receipt 时，Handoff/Guard/AuditReceipt/merge gate 拒绝放行；
- Main 未标记来源敏感的意图识别不由静态代码推断，必须由主会话依照用户请求检查；
- 非来源任务不会额外创建该角色；
- 请求只读/无副作用/来源字段缺失、runtime dispatch 缺失或 receipt-child 绑定不匹配时 fail-closed；不能将请求 sandbox 写成已观测事实；
- 未授权新增逻辑、来源漂移、hash 不一致和旧 receipt 均被阻断；
- Source Fidelity PASS 后仍必须通过独立普通 Audit；
- 测试覆盖 route、profile、任务角色、来源漂移、证据绑定和修复重审。
