# multi-agent-dev V2：V1 保留与迁移映射

状态：开发前迁移清单  
用途：在开始 V2 实现前确认哪些既有规则必须保留、重写或通过回归验证  
关键边界：V1 当前工作区可能包含未提交修改。本文不把工作区内容自动视为可覆盖的干净基线。

## 1. 基线要求

Phase 0 开始时记录 V1 仓库的 HEAD、分支、git status、已跟踪差异和未跟踪文件。当前未提交文件归其所有者，V2 实施者不得回滚、覆盖、移动或清理。

本开发前文档编写时，V1 工作区已观察到以下已跟踪文件存在未提交修改；该状态仅作为本次基线事实，实施开始时必须重新读取，不得假定仍相同：

- skills/multi-agent-dev/README.md
- skills/multi-agent-dev/SKILL.md
- skills/multi-agent-dev/docs/model-routing-hard-gate-development.md
- skills/multi-agent-dev/hooks/pre_spawn_route_guard.py
- skills/multi-agent-dev/references/adaptive-four-role-workflow.md
- skills/multi-agent-dev/tests/test_pre_spawn_route_guard.py

每项复用先检查实际文件与差异，再确认它是用户已接受的行为、实验实现还是未完成改动。若要复制脚本或配置，记录来源路径、源版本/哈希、复制点、修改点及对应回归测试。文件名相同或文档说“已经实现”不能替代检查。

## 2. 保留与迁移矩阵

| V1 能力 | V1 来源 | V2 处理 | 必需回归证据 |
| --- | --- | --- | --- |
| 四职责、主会话统筹、思考按需、唯一写入者 | skills/multi-agent-dev/SKILL.md；references/adaptive-four-role-workflow.md | 保留；D/I/A 只决定是否启用和使用哪档，不增加常驻角色 | 小任务跳过思考；需要设计决策时只读思考；作者与审计员分离 |
| 用户原文、项目文档优先、范围冻结与持续纠偏 | SKILL.md §1-4；adaptive-four-role-workflow.md §3-4 | 保留，并为路由门禁加入独立的配置/运行证据字段 | 用户禁止新增变量的负例能审计拒收；允许文件不等于允许文件内任意行为 |
| 拒收后范围内修正/补证与独立复审 | SKILL.md 第三/四步；adaptive-four-role-workflow.md §4 | 保留，不要求用户对已授权范围内的每次返工重新授权 | 不符合、证据不足均回流；审计员不改代码、不自批 |
| 主回合停滞、关闭失败、状态冲突和旧 writer 交接 | docs/stalled-orchestration-recovery-development.md | 保留安全不变量；把 V1 marker/receipt 条件替换为 V2 当前路由状态，并保持停止确认优先 | 状态未知时不 fork/接管；旧 writer 确认终止后才可交接；无新证据不重试 |
| context-lean 条件伴随、NOT_NEEDED/ARMED/ACTIVE/BLOCKED、压缩和恢复门禁 | docs/context-lean-companion-development.md；skills/context-lean/SKILL.md | 保留条件触发与角色边界；不复制 context-lean 全部机制，不假定平台支持某 Hook/阈值 | 短任务不额外加载；长任务按条件启动；恢复后先核对契约、基线、writer 和版本 |
| ServerChan done/blocked/stopped 通知、凭据、重试和去重 | docs/serverchan-completion-notification.md；scripts/notify_serverchan.py；hooks/task_terminal_notify.py | 保留终态一次通知、通知结果诚实报告和主屏不显示机器 marker；V2 若单独安装须确认脚本依赖齐全 | dry-run 格式测试；done 缺真实 verification 不发送；发送失败进入风险；通知/Hook 不重复发送；无路由 task_id 时可直接通知 |
| V1 route marker 与 PreToolUse 路由守卫 | docs/model-routing-hard-gate-development.md；hooks/pre_spawn_route_guard.py | 不复制成 V2 必需依赖；保留“可纠正错误、非法输入拒绝、最小脱敏收据”的目标，重做 V2 contract 与实际入口探针 | V1 和 V2 marker 相互透传；Hook 活跃时纠正/拒绝探针；Hook 绕过时降级而非假装成功 |
| 用户级 Hook 注册和信任流程 | V1 hooks 配置说明及官方 Codex Hooks 文档 | 不自动覆盖用户配置；V2 示例单独命名并限定 V2 marker。启用由用户审阅、信任 | V1/V2 同时存在时检查匹配 Hook 全部运行及 deny 优先规则；普通其他工具不受影响 |
| 路由硬门禁测试 | tests/test_pre_spawn_route_guard.py | 新建 V2 测试，不把 V1 测试改写后当作 V2 回归 | 语法/透传/纠正/拒绝/脱敏/幂等/运行时探针分别报告 |
| 通知契约、上下文伴随、编排恢复契约测试 | tests/test_serverchan_notification_contract.py；tests/test_task_terminal_notify.py；tests/test_context_companion_contract.py；tests/test_orchestration_recovery_contract.py | V1 测试作为行为参照；V2 需有独立测试或经过明确的共享实现验证 | 每一项注明实际运行命令、退出码和不覆盖的运行时事实 |

## 3. V1 路由规则的明确替换

V1 的二元复杂度门、MAD_ROUTE_V1 marker、固定 model/effort 真值表和“缺 Hook receipt 时不能放行”均不原样沿用。V2 改为：

1. D/I/A 三轴选择职责和路由档位。
2. Hook 状态与 runtime route provenance 分开记录。
3. Hook 只有在当前工具入口通过改写、拒绝及普通工具透传探针后才标为 HOOK_ENFORCED。
4. 不具备 Hook 时，允许经实际运行元数据验证的 profile 或显式参数派发。
5. 没有可核对的实际 model/effort 时标记 ROUTE_UNVERIFIED；若元数据已证明实际值不符，则标记 ROUTE_MISMATCH 并判路由验收不通过。不得虚构证据，也不得把 Hook 收据等同于 provenance。
6. 用户把指定路由设为硬约束时，路由验收未通过不能整体报告合格；若未设为硬约束，可将功能/审计结论与路由不确定性分别报告。

旧 V1 Hook 对 MAD_ROUTE_V2 输入应有透传测试；新 V2 Hook 对 MAD_ROUTE_V1 输入也应有透传测试。若用户级配置会并行加载多个 Hook，应在配置层验证它们的 matcher、输出和拒绝冲突；不能假设新文件替换旧文件。

## 4. 可复用脚本的来源核对

### 4.1 ServerChan

V2 若复制通知脚本，应先记录所用 V1 文件的 HEAD/差异和哈希；在 V2 包内单独运行测试。复制时保持凭据查找顺序、消息脱敏、默认重试、显式 state file、verification 必需条件、task_id 去重/中断补偿语义。不能把真实 SendKey 放进配置模板、测试或通知证据。

若改成依赖单独安装的通知 Skill，必须验证 V2 在该依赖缺失时怎样完成或阻断任务；不得默认其已安装。独立安装场景以无需未声明依赖为验收要求。

### 4.2 context-lean 与编排恢复

V2 只复制触发条件、边界和恢复门禁；实际压缩、检查点及平台专属 Hook 仍以 context-lean 自身能力和目标平台为准。

V2 若需要改变旧编排状态名或路由交接条件，须逐项说明为何变化、保持了哪些停止/唯一 writer 不变量、用哪条负例覆盖。不得因 Hook 不可用而放宽旧 writer 停止确认。

## 5. Phase 0 必须提交的映射产物

实现前在 V2 工作目录完成一张有负责人和证据列的最终表，至少包括：

| 字段 | 必填内容 |
| --- | --- |
| V1 requirement | 保留的用户意图或可观察规则 |
| Source | 具体文件/章节/函数/测试和 V1 固定版本 |
| Current delta | 若来源文件当前有未提交修改，逐项记录且不覆盖 |
| V2 target | V2 文件、规则或脚本路径 |
| Behavior change | 保留、替换或删除的内容及理由 |
| Regression | 对应测试 ID、运行探针或人工 UI 步骤 |
| Evidence | 实际结果、版本、退出码、provenance 或局限 |
| Audit | 符合 / 不符合 / 证据不足及审计责任人 |

完成映射不代表功能已经移植或测试通过；它只是实施授权范围和防遗漏依据。
