# V2 实施基线与能力登记

状态：实现过程记录；其中运行时路由证据尚未完成。  
V2 contract revision：`v2.0.0-route-contract`  
工作区基线 HEAD：`6a2a182c21f9a3b63d7a5ed436c1d1f967bd867c`  
基线分支：`main`  
Codex CLI：`codex-cli 0.157.1`（2026-09-26 读取）

## 1. 授权与写入边界

用户在 2026-09-26 明确要求按已验收的 V2 开发文档实施代码、独立审计并测试。V2 新增写入范围为 `skills/multi-agent-dev-v2/`。此证据记录仅追加在既有 `docs/multi-agent-dev-v2/`。

本轮开始时 V1 存在以下未提交修改；它们属于既有基线，不得覆盖、回滚、移动或整理：

- `skills/multi-agent-dev/README.md`
- `skills/multi-agent-dev/SKILL.md`
- `skills/multi-agent-dev/docs/model-routing-hard-gate-development.md`
- `skills/multi-agent-dev/hooks/pre_spawn_route_guard.py`
- `skills/multi-agent-dev/references/adaptive-four-role-workflow.md`
- `skills/multi-agent-dev/tests/test_pre_spawn_route_guard.py`

此外，`docs/` 在本轮开始时是未跟踪目录，包含上一轮用户验收的 `docs/multi-agent-dev-v2/` 开发前文档；实施仅在该 V2 子目录新增证据记录，不改写冻结的四份设计文档。

## 2. Codex 能力与路由证据注册表

| 能力 | 当前观测 | 状态 | 限制/后续验收 |
| --- | --- | --- | --- |
| Codex 版本 | `codex-cli 0.157.1` | 已观察 | 此信息不能推导 Desktop、其他入口或后续版本行为 |
| 模型/effort 参数可表达 | 当前 Agent 派发接口与协作工具 schema 提供 `gpt-6-sol`、`gpt-6-luna` 及所需 effort 选择；官方 Custom Agent 文档允许在 TOML 中设置 `model`、`model_reasoning_effort`、`sandbox_mode` | 配置能力已确认 | 配置值可表达不等于该次子会话实际采用该值 |
| 自定义 Profile 被当前入口发现 | 未执行真实 profile 派发探针 | `UNKNOWN` | Profile 模板仅是可审阅配置；安装、发现和运行优先级仍须实测 |
| 显式 model/effort 的实际运行值 | 当前可读工具结果不提供独立于请求参数的子会话 runtime provenance；Agent 自述不作证据 | `ROUTE_UNVERIFIED` | 不能把参数回显、任务名、配置文件或 Hook 收据算作实际运行元数据 |
| V1 用户级 Hook 配置 | `%USERPROFILE%\.codex\hooks.json` 存在；只读摘要显示 `PreToolUse` matcher 包含历史 `Agent`/`spawn_agent`/`collaboration.spawn_agent`/`exec` 名称 | `HOOK_UNVERIFIED` | 未从新鲜会话观察信任状态、Hook 输入、更新输入、拒绝或实际路由；本轮不修改、不信任该配置 |
| V2 PreToolUse 路由 Hook | 当前尚无 V2 注册；专用派发路径未通过本轮反事实运行探针 | `HOOK_UNVERIFIED` | 按方案不注册/不宣称可用；继续实现经审阅的 Profile 与显式参数降级规则 |
| V1 对 `collaboration.spawn_agent` 的历史探针 | V1 冻结开发文档记录该路径曾保留错误参数并在非法 marker 下创建 Agent | 历史 `ROUTE_UNAVAILABLE` | 作为负向回归背景；不把它当作 0.157.1 新鲜会话的当前实测 |
| Hook / route provenance 取证来源 | 已找到的工具元数据和普通任务记录不含实际 model + effort 的独立字段 | `UNKNOWN` | Profile/显式派发的端到端路由结论均保持 `ROUTE_UNVERIFIED`，直到可复现字段来源被登记 |
| Hook 官方契约 | 2026-09-26 查阅 Codex Hooks 文档：PreToolUse 支持对适用的本地工具 `deny` 或 `allow + updatedInput`；部分专用路径可绕过；`SubagentStart` 的 `continue:false` 不阻止创建 | 文档事实已核对 | 实际目标入口仍必须运行时探针；不能以官方通用覆盖描述代替入口实测 |
| Custom Agent 文件契约 | 2026-09-26 查阅 Codex Subagents 文档：独立 TOML 必须含 `name`、`description`、`developer_instructions`；可设置 model/effort/sandbox；文件中的 model/effort 可覆盖显式 spawn 值 | 文档事实已核对 | Profile 模板同时显式固定 model 和 effort；验证真实生效仍需 provenance |

官方资料： [Codex Hooks](https://learn.chatgpt.com/docs/hooks)、[Codex Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)。查阅日期：2026-09-26。

## 3. V1 行为迁移证据

固定源码基线为仓库 HEAD `6a2a182c21f9a3b63d7a5ed436c1d1f967bd867c`。`HEAD` blob 用于识别原始版本；当前 SHA-256 用于区分实施开始时实际观察到的文件。带工作区差异的 V1 文件只作为阅读依据，本轮不直接复制其未审差异。

| V1 要求/行为 | V1 来源（HEAD blob） | 起始差异 | V2 落点/回归 |
| --- | --- | --- | --- |
| 四逻辑职责、按需思考、唯一 writer、固定版本审计和拒收回流 | `skills/multi-agent-dev/SKILL.md` (`a4a1fca31a0149c45c5b302ce1f924dcc15bf662`)；`references/adaptive-four-role-workflow.md` (`01621870094b8683f50cc675fc90fdd2d8b3321a`) | 两文件均已修改；当前文件 SHA-256 分别为 `210645A1953248BF1A22EE37D10434D4552B031DAA346187232FB8A016CB4CF6`、`CB6122DB3260A946920C657BAF3A9BD3427813E55F3DC504AE7E62FF8C85CC1E` | `references/role-routing.md`、`references/execution-audit.md`；DOC/ROUTE/AUDIT 前向矩阵 |
| 拒绝/证据不足的范围内返工，作者与审计员分离 | 上述 SKILL/adaptive 文件，特别 adaptive §4 | 存在起始差异，不覆盖 | `references/execution-audit.md`；AUDIT-03/04 |
| 主回合/子 Agent 状态分离、停止后才交接、冲突时阻断 | `docs/stalled-orchestration-recovery-development.md` (`4b5649e72104593ea7e75fda7cf21275c9d0eeb2`)；`tests/test_orchestration_recovery_contract.py` (`c9edc337513e6f31c2b29f3178f50105ac19e35d`) | 起始未修改 | `references/execution-audit.md`；ORCH-01 |
| context-lean 只在长任务/退化时伴随，压缩恢复不改契约/写入权 | `docs/context-lean-companion-development.md` (`5154895dda077fb1341d155d4a7c6f113ba3b697`)；`skills/context-lean/SKILL.md`；`tests/test_context_companion_contract.py` (`a14b904ddd16c4b8defc6263190cb541240b67ab`) | 上述开发文档与测试起始未修改 | `references/long-task-and-notification.md`；CONTEXT-01/02 |
| ServerChan 凭据顺序、重试、verification 门禁、task-id 记录/补偿、消息脱敏 | `docs/serverchan-completion-notification.md` (`aaacc0f7e9ebe1a2c685d09e2d0b7797aa3f8365`)；`scripts/notify_serverchan.py` (`129c8d760694042d9a1bd901d86681298fbaf6bf`)；`hooks/task_terminal_notify.py` (`2590805d4a82783e46ad942485f419288ee084e5`) | 三文件起始未修改；通知器源 SHA-256 `01178F6E58B90823907AAE1232EC6011838D5D4AB44F883733580F2913953095`；Hook 源 SHA-256 `D9E96C7877C9027D9A8F29DCB11039981AF3DB3CE94B482503B8CE63F2581365` | V2 内独立副本；Hook namespace/state root 改为 V2；NOTIFY-01/02 及单测。复制时逐项记录修改理由 |
| V1 MAD_ROUTE marker、二元复杂度、receipt 必需真值表 | `docs/model-routing-hard-gate-development.md` (`e374d9c4e79261fd1156b229e3cbbb6349d7250b`)；`hooks/pre_spawn_route_guard.py`；`tests/test_pre_spawn_route_guard.py` | 开发文档、Hook、测试均有起始差异；当前开发文档 SHA-256 `4C9DF4EB7DFD1DD4C672C36AF1162CAD324D891558565BC324D544954A1E5175` | 不复制 V1 contract/真值表；V2 采用 MAD_ROUTE_V2、D/I/A 与独立 Hook/provenance 状态；PROOF-01/03、HOOK-05 |
| V1 通知行为回归参照 | `tests/test_serverchan_notification_contract.py` (`dbda6cdc56233e18da2efa1e98d8ea4bfee263dc`)；`tests/test_task_terminal_notify.py` (`6f304d896b43d0973fede9006707532c5a89d79b`) | 起始未修改 | V2 新建测试，仅依赖隔离临时状态目录和模拟网络；NOTIFY-01/02 |

源路径、blob 和工作区状态在实现开始时只读核对；上述映射不是复用 V1 当前未提交实现的授权。`skills/multi-agent-dev/README.md`、`SKILL.md`、V1 model-routing 文档、Hook、adaptive reference 和 V1 路由测试均不得修改。

## 4. 实施变更与验证记录

### 4.1 V2 包落地范围

本次新增仅限 `skills/multi-agent-dev-v2/`：

- `SKILL.md`、`agents/openai.yaml`、`README.md`：独立入口、UI 元数据与安装边界。
- `references/role-routing.md`：四种职责、D/I/A 规则、档位矩阵及 V2 dispatch intent schema。
- `references/execution-audit.md`：范围冻结、唯一 writer、纠偏、拒收回流和独立只读审计。
- `references/hook-routing-fallback.md`：Hook 状态与实际路由 provenance 分离；当前不注册未经探针验证的 V2 路由 Hook。
- `references/long-task-and-notification.md`：context-lean 条件伴随、终态推送边界及当前中断补偿限制。
- `profiles/*.toml`：1 Think、4 Execute、3 Audit profile 模板；未安装到用户目录。
- `scripts/route_contract.py`：纯格式/一致性校验器；不接 Codex 工具、不执行 Hook、不证明 runtime route。
- `scripts/notify_serverchan.py`：V2 独立终态推送器，使用同一 SendKey 环境变量/本机密钥文件查找顺序；V2 receipt 存储独立于 V1，并且只记录 task id hash 派生路径、状态与时间。
- `tests/`：路由负例/往返、profile 矩阵、Skill 元数据、本地链接、通知 done 门禁/dry-run/retry/去重/失败脱敏等确定性测试。

无 V1 文件、全局 Codex 配置、Hook 信任状态、用户 profile 目录、网络服务或仓库远端发生写入。V2 含独立终态 notifier、可选生命周期 Hook handler、手工合并示例和隔离状态目录；它们未安装、未信任或未在当前 Codex 入口运行时验证。V2 路由校正 Hook 仍未注册。

### 4.2 验证结果

| Evidence ID | 操作 | 实际结果 | 结论/限制 |
| --- | --- | --- | --- |
| V2-TEST-01 | `python -B -m unittest discover -s skills/multi-agent-dev-v2/tests -p "test_*.py" -v` | 当前 26 tests，全部通过 | 覆盖路由契约/profile、task_id optional/local-only、通知正文/receipt 隐私、PreToolUse 本地登记、Stop pending 重试、Interrupt/SessionEnd fallback、去重和失败行为；模拟 Hook payload 不证明 Codex 实际加载/触发 Hook |
| V2-TEST-02 | `git diff --check` | 退出码 0；仅提示 Git 对 6 个既有 V1 文件的 LF/CRLF 转换提醒 | 这些文件为起始差异，本轮未编辑；提醒不视为内容差异 |
| V2-TEST-02a | `python -B -m unittest discover -s skills/multi-agent-dev/tests -p "test_*.py" -v` | 64 tests，全部通过 | V1 既有未提交基线测试；未改 V1 文件 |
| V2-TEST-03 | `python -B C:\Users\T14S\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills/multi-agent-dev-v2` | 未运行成功：validator 导入 `yaml` 时本机 Python 报 `ModuleNotFoundError: No module named 'yaml'` | 未安装或修改依赖；用 V2 自带标准库结构测试校验 frontmatter/OpenAI YAML 子集及相对链接，但官方 validator 结果仍是未验证 |
| V2-TEST-04 | Codex profile 实际派发及模型/effort runtime provenance | 未运行；当前工具结果未提供独立的实际模型+effort 字段 | `ROUTE_UNVERIFIED`；Profile 模板不算运行证据 |
| V2-TEST-05 | V2 PreToolUse/Stop/Interrupt/SessionEnd 在真实 Codex 入口的事件探针 | 未运行；未修改或信任用户配置 | `HOOK_UNVERIFIED`；单测只验证模拟输入下的处理逻辑，不能标为 `HOOK_ENFORCED` |
| V2-TEST-06 | 安装后加载 V2 的五个 Codex 前向工作流场景 | 未运行；本次没有安装或改用户级配置 | 实际工作流、Hook/profile discovery、不同 Codex 入口仍需验收 |
| V2-AUDIT-01 | 固定 V2 文件版本的独立只读审计 | 前两轮对 hash `528d501c…1915b6e7`、`5ed3befc…6e2d81` 均为 `FAIL for acceptance`；前两轮发现的 task_id 泄漏/必填问题已修复，缺少中断补偿代码现已补入当前包。当前 hash `98ea91bf…061f7215` 等待第三轮复审。协作工具未返回 `MAD_ROUTE_RECEIPT` 或实际模型/effort provenance | 独立审计者是不同责任者；审计子任务实际模型/effort 仍 `ROUTE_UNVERIFIED`。在当前包复审和运行时门禁关闭前，不能报告 `ACCEPTED` |

官方 skill-creator validator 受当前环境缺少 PyYAML 阻断；没有为了验证安装新依赖，也没有将本地标准库结构测试冒称为等价完整 validator。单测由 Python 3.12 运行。

本实施回合最终状态为 `blocked`（实现完成但 V2 验收门禁未关闭）；已通过现有 V1 ServerChan notifier 发送一次终态通知，ServerChan 返回成功。通知凭据及响应中的读回凭据未写入本文档。

### 4.3 冻结包标识

第一轮审计包内 21 个文件（排除 Python `__pycache__` 生成物）的 package manifest hash 为 `528d501cc4dcdc09ea0f8d1bfa0ea07610af80c073ae4be525bc371b1915b6e7`；task_id 修订包内 21 个文件的 hash 为 `5ed3befc1972bd9fbb13ecc2fa6695165bcbedf985fd919d08912704cb6e2d81`。补入可选生命周期 Hook handler、示例与回归测试后，当前 V2 包 25 个文件的 hash 为 `98ea91bf81de75aa36734f6d76f67380aab2216fb12bfa79793ca504061f7215`。Hash 基于相对路径与逐文件 SHA-256 的排序清单再计算 SHA-256；不包含本证据文档。当前 hash 是唯一有效的复审目标，任何后续包内修订都须重算并复审。

第一轮独立审计发现通知迁移/隐私问题：route task id 被放入 ServerChan 正文与明文 receipt，且 CLI 强制要求 task id；两个实现问题已修复。任务 ID 现在可省略，若传入仅用于本地 SHA-256 派生 receipt/pending 路径，不进入通知正文或记录内容。第三轮复审需确认新增可选生命周期 Hook 的状态流程和隔离语义。

第二轮独立复审确认 task_id 修复通过，但中断补偿功能缺失。当前包已实现独立 lifecycle handler 并测试 PreToolUse 登记、Stop pending retry、Interrupt/SessionEnd stopped fallback、receipt 去重及发送失败路径。该代码级缺口已补，但只有经第三轮独立审计和 Codex 运行时探针后才能关闭；profile discovery、Hook 信任/事件实触发、5 个前向工作流和实际 model/effort provenance 仍未验证。

### 4.4 官方 Hook 契约复核及静态修正（2026-09-26）

复核 [Codex Hooks 官方文档](https://learn.chatgpt.com/docs/hooks) 后发现旧 V2 包中的可选 lifecycle Hook 与当前文档有三处静态不符：统一 `exec_command` Hook 事件按 `Bash` 匹配且命令在 `tool_input.command`；`PreToolUse` 不支持 `continue`；`Interrupt`/`SessionEnd` 默认 1 秒且可配置上限 3 秒。已据此修改 `hooks/hooks.json.example`、`hooks/task_terminal_notify.py`、说明文档和回归测试：只按 `Bash` 注册、采用 `command` 输入、PreToolUse 透明返回 `{}`，Interrupt/SessionEnd 超时设为 3 秒，Stop 设 50 秒以覆盖内部有界重试。官方文档明确个别工具路径可能绕过 Hook，且配置存在不等于 Hook 在目标入口已加载。

| 最新验证 | 操作/结果 | 结论/限制 |
| --- | --- | --- |
| V2 单测 | `python -B -m unittest discover -s skills/multi-agent-dev-v2/tests -p "test_*.py" -q`：28 tests，全部通过 | 新增 canonical Bash/tool_input、Hook timeout 配置及 SessionEnd 失败以非零退出码呈报断言；模拟 payload 仍不等于 Codex 实际 Hook 探针 |
| V1 回归 | `python -B -m unittest discover -s skills/multi-agent-dev/tests -p "test_*.py" -q`：64 tests，全部通过 | V1 文件未改；包含测试自身的 notifier mock 输出 |
| 差异检查 | `git diff --check`：exit 0，仅既有 6 个 V1 文件提示 LF/CRLF | 无 whitespace error |
| V2 package manifest | 25 files；`b14aa2daaaa6b9a5090ed4f17c6a64211f0b512d3426555e1e82d47a63ca5892` | 当前独立审计目标；证据文档不计入 package hash |
| 官方 Hook validator/runtime | 未在目标 Codex 会话安装/信任/探测；`skill-creator` validator 仍因缺少 PyYAML 无法运行 | `HOOK_UNVERIFIED`；不标为 `HOOK_ENFORCED` |

本节 supersedes 4.2/4.3 中旧 V2 hash、26 项单测和“等待第三轮”的当时状态；此前记录保留为历史证据。最新独立审计结论将在复审完成后追加。运行时 profile discovery、实际 model/effort provenance、Hook event probes 和五个前向工作流仍未验证，不得以本次静态修正/单测通过关闭这些门禁。


### 4.5 接手复核与当前固定版本（2026-09-27）

本轮接手先执行只读基线检查：

- `git status --short --branch`：仍为 `main...origin/main`；V1 的 6 个既有修改保留，`docs/` 与 `skills/multi-agent-dev-v2/` 仍为本轮未跟踪内容；未执行 reset、清理、提交或推送。
- V2 包固定为 25 个文件；清单排除任意 `__pycache__` 文件。
- manifest 算法：以 `root=skills/multi-agent-dev-v2` 递归取文件，按相对 POSIX 路径排序；每行生成 `<relative-path> <sha256(file-bytes)>`；用两个字面字符 `\n` 连接各行并在末尾追加同样的 `\n`，对所得 UTF-8 字节再次 SHA-256。复算结果：
  `a38d2272226649e9a0c28d860a6f6e38b1cfd63ec568e26a66c2c040e8e30488`。

回归与静态验证：

- `set PYTHONUTF8=1 && set PYTHONIOENCODING=utf-8 && python -B -m unittest discover -s skills\multi-agent-dev-v2\tests -p "test_*.py" -q`：29 tests，全部通过。
- 同一显式 UTF-8 环境下运行 V1：64 tests，全部通过。默认 Windows 代码页下 V1 测试的嵌套子进程输出会被父进程按 UTF-8 错误解码；显式 UTF-8 环境消除该测试环境问题，V1 源文件未改。
- `git diff --check`：退出码 0；仅报告既有 V1 文件的 LF/CRLF 转换提示，无 whitespace error。
- `python -B -m compileall -q skills\\multi-agent-dev-v2`：通过。

代码级只读复核重点：

- `_registration_argv` 只接受 Python 直接调用已解析到的 V2 `notify_serverchan.py`，仅允许 `-3/-B`、一个 `--register-active`、一个安全 `--task-id`；shell 控制字符、包装命令、复合命令、错误脚本、额外参数均拒绝。
- Hook 示例使用 `^Bash$` 和 `tool_input.command`；PreToolUse 返回透明空输出，不使用不支持的 `continue`；Stop/Interrupt/SessionEnd 超时和失败路径与当前实现一致。
- task ID 只用于 SHA-256 派生本地 active/pending/receipt 路径；通知正文和 receipt 内容不写入明文 task ID；发送成功后清理对应 active/pending 状态，重复事件由 receipt 抑制。

独立审计状态：代码读取与关键路径复核未发现新的 P0/P1/P2；但审计 agent 未返回正式 `MAD_ROUTE_RECEIPT`，也未提供实际 model/effort provenance。故代码级结论记录为“未发现新增代码问题”，独立审计正式放行仍为“证据不足”，路由状态为 `ROUTE_UNVERIFIED`，Hook 状态为 `HOOK_UNVERIFIED`。

运行时未关闭门禁：Hook 真实事件探针、Profile discovery、实际 model/effort provenance、五个前向工作流、PyYAML 版 `quick_validate.py` 均未运行；不得标记 `ACCEPTED`。


### 4.6 V2.1 并发编排开发文档与审计状态（2026-09-26）

本轮只写入 docs/multi-agent-dev-v2/，未修改 V2 package、V1 文件、全局 Hook/Profile 配置、Profile 安装状态或仓库历史。新增/更新文档：

- 06-controlled-parallel-orchestration-development.md
- 07-v2-parallel-orchestration-contracts.md
- 08-v2-parallel-orchestration-verification-plan.md
- 09-v2-implementation-task-breakdown.md
- 10-v2-document-audit-checklist.md
- 11-v2-design-document-audit-report.md
- INDEX.md

文档内容覆盖主会话与持久化 Controller 的权威分层、受控 fan-out/fan-in、namespace writer lease、CAS/event ledger、HandoffPacket、Deterministic/Semantic Guard、Independent Audit、D/I/A 并发规则、每个职责的 requested model/effort、runtime provenance、十个前向工作流和 Phase 0–6 实施任务。

主会话静态交叉复核已关闭先前发现的 P1/P2：D07 路由/Hook 枚举大小写、Run/Task/Handoff 状态、audit_receipt 字段、D/I 并发措辞和 D08 工作流计数。主会话未发现新的 P0/P1/P2；这不是独立审计通过。

独立 receipt：MAD-DOC-AUDIT-V2.1-FINAL-20260926-002。其状态为 HOLD_FOR_CODE_START：审计 Agent 的只读环境无法定位本设备上的文档，未执行 post-fix re-read，不能确认 remediation 或无新 P0/P1/P2。requested model/effort provenance 不可见，保持 ROUTE_UNVERIFIED。按审计协议，不把该 receipt 写成 PASS_FOR_CODE_START。

文档实施门禁当前为 HOLD_FOR_CODE_START；代码 Phase 0 未开始。恢复条件是独立责任人能够读取同一固定文档版本，签发正式 PASS_FOR_CODE_START，并把 target hashes、checks、findings、limitations 追加到本证据文档。V2 功能、Hook/Profile、实际 model/effort provenance、五个原有和五个新增前向工作流仍未验证。

### 4.7 最终独立文档审计 receipt（2026-09-26）

audit_id：MAD-DOC-AUDIT-V2.1-FINAL-SCOPE-20260926-005
auditor_actor：independent-read-only-agent
target_docs：D01–D10、INDEX；D05 为本追加式 evidence output，D11 为审计报告 output，不作为自身 target hash
target_contract_rev：v2.1.0-controlled-parallel
checks：独立只读重读 R2 snapshot；复核 R01–R13、状态、阶段、schema/hash、revision 域、CAS/event 原子性、handoff/audit 顺序、owner 分离、enum、retry、工作流计数和 contract revision 引用
findings：P0=[]；P1=[]；P2=[]
cross_document_result：CONFORMING
implementation_readiness：CONFORMING
runtime_provenance_status：ROUTE_UNVERIFIED
decision：PASS_FOR_CODE_START

远程权威 target 文件的行数/SHA-256 已写入 D11 §12。远程设备实际字节为准；本地快照的行尾差异不覆盖远程 hash。V2 package 仍为 25 文件，manifest SHA-256：a38d2272226649e9a0c28d860a6f6e38b1cfd63ec568e26a66c2c040e8e30488。

本 receipt supersedes 本证据文档中此前的文档审计 HOLD/REJECT 历史条目，但不关闭任何代码、Hook/Profile、runtime model/effort、Controller 或前向工作流门禁。

### 4.8 Superseding final document-audit receipt（2026-09-26）

The previous 4.7 receipt is superseded by audit_id MAD-DOC-AUDIT-V2.1-FINAL-20260926-006 because INDEX received its final gate wording after the prior receipt. The independent read-only audit target is D01–D10 and INDEX; D05 and D11 are append-only outputs excluded from their own target hashes.

Result: P0/P1/P2 findings empty; cross_document_result CONFORMING; implementation_readiness CONFORMING; decision PASS_FOR_CODE_START; runtime_provenance_status ROUTE_UNVERIFIED.

The independent audit rechecked R01–R13: HANDOFF_READY evidence-only semantics, D06/D09 phase order, non-circular task-template hash binding, run/task/lease revision domains, atomic CAS/event/outbox, audit ordering, owner separation, full route/hook enums, ScopeManifest fields, Run-only READY_TO_MERGE, PLANNED queue state, retry thresholds and D07 contract revision references.

Final target snapshot hashes and line counts are recorded in D11 §13. Remote byte hashes, not normalized local snapshots, are authoritative. V2 package remains 25 files with manifest a38d2272226649e9a0c28d860a6f6e38b1cfd63ec568e26a66c2c040e8e30488.

This closes the documentation gate only. It does not close V2 code implementation, runtime Hook/Profile, actual model/effort provenance, Controller behavior, validator, or ten forward workflow gates.

### 4.9 最终基线核对

- V2 package：25 files，独立复算 manifest SHA-256 a38d2272226649e9a0c28d860a6f6e38b1cfd63ec568e26a66c2c040e8e30488。
- V2 tests：PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python -B -m unittest discover -s skills/multi-agent-dev-v2/tests -p "test_*.py" -q，29/29 OK。
- V1 regression：同一显式 UTF-8 环境，64/64 OK；测试输出中的 notifier failure/timeout 是负例与重试路径，测试最终退出码 0。
- git diff --check：退出码 0；只有既有 V1 六个文件的 LF/CRLF 转换提醒，无 whitespace error。
- git status --short：既有 V1 六个修改仍保留；docs/ 与 skills/multi-agent-dev-v2/ 为本轮未跟踪内容；没有 reset、清理、commit、push。
- 文档独立审计：MAD-DOC-AUDIT-V2.1-FINAL-20260926-006，D01–D10 + INDEX，PASS_FOR_CODE_START；D05/D11 为追加式输出。
- 仍未验证：真实 Hook/Profile、实际 model/effort provenance、Controller 运行、原五个与新增五个前向工作流、PyYAML validator；V2 功能状态不是 ACCEPTED。

### 4.10 V2.1 代码实现、代码审计与真实探针（2026-09-27）

实现范围（仅修改 `skills/multi-agent-dev-v2/`）：

- `scripts/parallel_manifest.py`：canonical JSON、strict JSON loader、safe ID/path、ScopeManifest/TaskTemplate、非循环 manifest hash、Windows reparse/symlink 检查接口。
- `scripts/task_spec.py`、`scripts/capability_registry.py`、`scripts/route_provenance.py`：冻结 TaskSpec、requested route 与 observed provenance 分离、只读 TOML Profile capability discovery。
- `scripts/state_store.py`：SQLite `WAL`、`synchronous=FULL`、foreign keys、run/task 独立 revision、CAS、idempotency、event/outbox 同事务、controller epoch fencing、规范状态转移。
- `scripts/lease_store.py`、`scripts/task_scheduler.py`：controller-owned 原子多 namespace lease、fencing token、heartbeat/release、过期 UNKNOWN、停止证据确认后才可恢复、依赖 DAG 和并发上限。
- `scripts/handoff_contract.py`、`scripts/guard_contract.py`、`scripts/semantic_guard.py`、`scripts/audit_receipt.py`：worker handoff 不能自带 receipt；Guard fail-closed；route mismatch 阻断；独立 auditor 与 writer 分离及 target hash binding。
- `scripts/orchestrate.py`：`init/plan/dispatch-next/bind-start/checkpoint/handoff/attach-receipt/status/cancel/recover/integrate-check` JSON CLI；输出单行 `{ok,code,entity_revision,data,evidence_refs}`。
- 新增 `tests/test_parallel_v21.py`，覆盖 schema/hash、strict JSON、CAS/idempotency、run/task 状态机、controller epoch、lease fencing/expiry/stop evidence、多 namespace 原子性、依赖调度、handoff/Guard/Audit、Profile capability、隔离 CLI 流程和并发 CAS。
精确清单复算：root=`skills/multi-agent-dev-v2`；递归文件排除所有 `__pycache__`；按相对 POSIX 路径 `.lower()` 排序；每行 `<relative-path> <sha256(file-bytes)>`；以两个字面字符 `\\n` 连接并末尾追加 `\\n`；对所得 UTF-8 字节 SHA-256。

- 文件数：38
- manifest SHA-256：`03c33623d507dfb0a8c27eb05e53c7a81c1d07a05a2bd1515a01420afde27e87`

测试与静态检查：

- V2：`python -m unittest discover -s skills\\multi-agent-dev\\skills\\multi-agent-dev-v2\\tests -p "test_*.py"` → **44/44 OK**。
- V1：`python -m unittest discover -s skills\\multi-agent-dev\\skills\\multi-agent-dev\\tests -p "test_*.py"` → **64/64 OK**；V1 既有 notifier 负例/超时路径仍按测试预期工作。
- `python -m compileall -q skills\\multi-agent-dev-v2\\scripts` → 通过。
- `git diff --check` → 退出码 0；仅既有 V1 文件的 LF/CRLF 提示，无 whitespace error。
只读代码审计结论：

- 复核了 strict schema/duplicate key、canonical hash 自引用、run/task/lease revision、CAS/event/outbox 事务、合法状态转移、controller epoch、lease fencing/expiry/stop evidence、全 namespace 原子租约、handoff→Guard→Audit 顺序、路径边界、动态执行调用和外部副作用边界。
- 审计期间发现并修正：task 插入列数、route mismatch 被错误抛异常、越级状态转移、过期 lease 可无证据重派、controller epoch 未校验、单 namespace 锁定、run transition 缺失、CLI 非对象 JSON 和 handoff 顺序问题；修正后重新跑完整 V2 测试。
- 当前主控只读复核未发现新的 P0/P1/P2。没有独立审计 agent 返回正式 `MAD_ROUTE_RECEIPT`，所以不能把本段写成独立审计 PASS；正式 runtime provenance 仍为 `ROUTE_UNVERIFIED`，Hook 为 `HOOK_UNVERIFIED`。
真实运行探针：

- 已在远端 Windows 真实 Python 进程执行 CLI：manifest `init` 返回 `DISPATCHABLE`、`dispatch-next` 返回 controller epoch 1 并同时发放 `cli-ns-1`/`cli-ns-2` 两个 ACTIVE lease、`bind-start` 返回 `RUNNING`、`status` 返回 run `RUNNING` 和 task `LEASED`；未写入工作区代码。
- 已执行隔离 SQLite 控制器端到端流程和双线程 CAS 竞争；均由真实 Python/SQLite 进程完成。该证据证明本地编排实现，不等同于 Codex Hook/真实 worker/model 运行时证明。
- capability registry 仅只读解析 V2 TOML Profile；没有安装 Profile，没有修改或信任全局 Hook，没有发起实际模型/Provider 请求。
剩余门禁：真实 Codex Hook 事件、Profile discovery 运行时结果、实际 model/effort provenance、原五个与新增五个前向工作流、外部副作用/通知、PyYAML `quick_validate.py` 仍未验证；V2.1 代码状态保持 `NOT_ACCEPTED`/`ROUTE_UNVERIFIED`，不得宣称验收完成。V1 修改仍保留；没有 reset、clean、commit、push 或部署。


### 4.11 V2 package documentation append correction（2026-09-27）

在 4.10 之后仅追加更新 V2 package 的 README.md 与 SKILL.md，说明 V2.1 controller CLI、SQLite/CAS、lease、handoff/Guard/Audit 与 runtime provenance 限制；未改动 V1、全局配置或文档冻结设计。按 4.10 同一算法重新复算：文件数仍为 38，最新 package manifest SHA-256 为 `6d1e289563edc18e25de7139680150cd040a987ee0db59904476a46f10d4d3f0`。此前 4.10 的 `03c33623...` 仅对应 README/SKILL 追加前字节，已被本条 supersede。


### 4.12 最终复跑记录（2026-09-27）

README/SKILL 追加后重新执行：V2 **44/44 OK**；V1 **64/64 OK**；V2 scripts compileall 通过；git diff --check 退出码 0，仅既有 V1 六文件 CRLF 提示。最终 package manifest 仍为 38 文件、SHA-256 `6d1e289563edc18e25de7139680150cd040a987ee0db59904476a46f10d4d3f0`。


### 4.13 最终代码小修正与 manifest supersede（2026-09-27）

代码审计补充发现 plan 写入缺少 request idempotency；已在 state_store.add_tasks 与 orchestrate.plan 增加请求幂等、重复 task/schema 检查，并重新执行 V2 **44/44 OK** 与 V1 **64/64 OK**。最终清单仍为 38 文件；按同一 manifest 算法的最新 SHA-256 为 `5277f989b040b0df5da392bb3544de87d51b8f4b3e318d2ec8a0f21b5569011f`，supersede 4.11 的 `6d1e2895...`。compileall 与 git diff --check 仍通过。该修正不改变 V1 文件、全局 Hook/Profile 配置或 runtime 门禁。


### 4.14 V2.1 开发完成、最终复跑与测试交接（2026-09-27）

在 4.13 之后继续只修改 V2 package 与追加式文档，未修改 V1、全局 Hook/Profile 配置或仓库历史。补齐内容：

- scripts/evidence_index.py：带 kind/source、manifest、revision、artifact hash、命令、限制和脱敏状态的证据索引；拒绝 secret-like 内容并绑定当前 run manifest。
- state_store.py：evidence source 字段迁移；外部副作用 outbox 的 claim、complete、FAILED 重放、claim 超时恢复和 pending 查询；side-effect class 校验。
- orchestrate.py：retry budget 改为严格按 max_retries，无新证据重试保持 GATE_HOLD，并在状态预检通过后才记录 attempt。
- lease_store.py / state_store.py：RETRYABLE 任务可重新派发；旧 controller epoch、过期 lease 和多类中断状态的迟到回写被拒绝或转 UNKNOWN。
- handoff_contract.py / worker_adapter.py：changed path 规范化、成功 Handoff 的测试 receipt 字段校验、key/value、JSON key/value 和 Bearer 输出脱敏。
- V2 references 新增 parallel-orchestration.md、guard-and-audit.md、model-effort-routing.md；新增测试专员交接 docs/multi-agent-dev-v2/12-v2-tester-handoff.md。

最终测试和静态检查：

| 检查 | 结果 |
| --- | --- |
| V2 全套 | python -B -m unittest discover -s skills\\multi-agent-dev-v2\\tests -p "test_*.py" -q：51/51 OK |
| V1 回归 | 显式 PYTHONUTF8=1、PYTHONIOENCODING=utf-8：64/64 OK；默认代码页会使 V1 的嵌套子进程解码负例失真，不能作为代码失败 |
| 编译 | python -B -m compileall -q skills\\multi-agent-dev-v2：通过 |
| 差异 | git diff --check：退出码 0；只有既有 V1 六文件的 LF/CRLF 提示 |
| V2 文件清单 | 44 个文件，排除所有 __pycache__ |

最终 manifest 算法保持不变：root=skills/multi-agent-dev-v2；递归取文件并排除 __pycache__；按相对 POSIX 路径 .lower() 排序；每行 <relative-path> <sha256(file-bytes)>，以字面 \\n 连接并在末尾追加 \\n；对所得 UTF-8 字节 SHA-256。最终 hash：

bfa007a07f330e43e3b72ad235777126b0de53e18792a4d76070f6510d6caa3f

真实本地探针：

- 独立 Python 进程调用 JSON CLI：init 返回 DISPATCHABLE，manifest hash 8c711c326290bd8f6ba385ceb680270fb43e743bd32cd813d3767e7cc861471c；dispatch-next 发放 controller epoch 1 和 namespace lease；bind-start 返回 RUNNING；status 读回同一 run/task revision。
- 独立 WorkerAdapter 进程用 shell=False 执行 Python 子进程，返回 exit code 0，api_key=secret 被脱敏为 api_key=<redacted>，无超时。
- V2 单测另行覆盖 outbox claim/complete/recovery、evidence index、retry budget、新证据门禁、controller epoch、RETRYABLE lease、Handoff/Audit 绑定和失败关闭路径。

最终主会话代码审计未发现新的 P0/P1/P2；本轮没有独立审计 agent 返回正式 MAD_ROUTE_RECEIPT 或实际 model/effort provenance，因此结论是“代码自审通过、独立审计证据不足”，不能写成独立审计 PASS。仍未关闭：真实 Codex Hook 事件、Profile discovery、实际 model/effort provenance、原五个与新增五个前向工作流、外部通知 provider、PyYAML quick_validate.py。V2 状态保持 NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED，交由测试专员按 12-v2-tester-handoff.md 接手。


### 4.15 Package hash supersede after reference links（2026-09-27）

在 4.14 后仅更新 V2 SKILL.md，补充三个操作参考文档的链接；重新复跑 V2 **51/51 OK**、V1 **64/64 OK**（显式 UTF-8 环境）、compileall 通过，git diff --check 仍退出码 0。V2 文件数仍为 44；按同一排除 __pycache__、相对 POSIX 路径 .lower() 排序、逐文件 SHA-256 清单和 UTF-8 清单 SHA-256 算法，最终 package manifest hash 为：

774e6beff9064180ec4860c092667d1e806c5110e29232571f3e199fdbb3b4bd

该 hash supersedes 4.14 的 bfa007a0...。没有改动 V1、全局配置、Profile 安装状态、提交或推送；运行时 Hook/Profile/model/effort/前向工作流门禁仍未关闭。


### 4.16 Notification idempotency hardening and final package hash（2026-09-27）

补充通知 intent 的默认幂等键绑定 run/task/status/message，并对同一 key 的不同 payload 拒绝；新增冲突负例。最终复跑：V2 **51/51 OK**；V1 **64/64 OK**（显式 UTF-8 环境）；V2 compileall 通过；git diff --check 退出码 0，仅既有 V1 六文件行尾提示。V2 package 仍为 44 files，按同一 manifest 算法的最终 SHA-256 为：

bb4e80a14dcec26428814408e96cc5953cdb01e403ab263241a67f5d741377d1

该 hash supersedes 4.15 的 774e6bef...。V2 代码自审未发现新的 P0/P1/P2；独立审计 receipt、真实 Hook/Profile/model/effort 和前向工作流仍未提供，状态继续保持 NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED。


### 4.17 Final stale-epoch regression and superseding hash（2026-09-27）

新增旧 controller epoch 在新 controller 接管后拒绝 lease 校验的回归断言；最终 V2 **51/51 OK**、V1 **64/64 OK**（显式 UTF-8 环境）、compileall 通过、git diff --check 退出码 0。V2 package 44 files；最终 manifest SHA-256：

bf72e20d9759f4a7a99f26bded0562acdec26d8fb37a071b41266757b3af8302

该 hash supersedes 4.16 的 bb4e80a1...。当前代码级自审结论仍未发现 P0/P1/P2；没有独立审计 MAD_ROUTE_RECEIPT 或真实 model/effort provenance，不能宣称独立审计通过或 V2 ACCEPTED。


### 4.18 V2.1 测试专员预审与隔离探针（2026-09-27）

本轮按 `12-v2-tester-handoff.md` 对固定 V2.1 包做只读预审和隔离探针；除本证据文档追加外，没有修改 V2/V1 代码、用户全局 Hook/Profile、Git 历史或远端。临时 SQLite 数据位于操作系统临时目录。

冻结版本核验：

- 独立复算 package manifest：44 files，SHA-256 `bf72e20d9759f4a7a99f26bded0562acdec26d8fb37a071b41266757b3af8302`，与交接值一致。算法按相对 POSIX 路径 `.lower()` 排序、排除 `__pycache__`、逐文件 SHA-256、清单末尾 LF 后计算 UTF-8 SHA-256。
- V1 六个既有修改文件仍在：`skills/multi-agent-dev/README.md`、`SKILL.md`、`docs/model-routing-hard-gate-development.md`、`hooks/pre_spawn_route_guard.py`、`references/adaptive-four-role-workflow.md`、`tests/test_pre_spawn_route_guard.py`；未覆盖或整理这些文件。
- Python：3.12.10；Windows 11 10.0.26200。未安装依赖、Profile 或 PyYAML；未改全局 Hook；未提交、推送或部署。

实际执行：

| 检查 | 结果 |
| --- | --- |
| V2 全套 `python -B -m unittest discover -s skills\\multi-agent-dev-v2\\tests -p "test_*.py" -q` | 51/51 OK |
| V1 回归（`PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`）`python -B -m unittest discover -s skills\\multi-agent-dev\\tests -p "test_*.py" -q` | 64/64 OK |
| V2.1 专项 `python -B -m unittest discover -s skills\\multi-agent-dev-v2\\tests -p "test_parallel_v21.py" -v` | 22/22 OK；包含双线程 SQLite CAS、lease、retry、handoff、Guard/Audit 和 CLI 隔离流程 |
| `python -B -m compileall -q skills\\multi-agent-dev-v2` | 通过 |
| `git diff --check` | 退出码 0；仅既有 V1 文件 LF/CRLF 提示 |
| 独立 JSON CLI 子进程探针 | `init`、`dispatch-next`、`bind-start`、`status`、`recover` 均成功；retry 可从 FAILED 到 RETRYABLE，预算耗尽返回 GATE_HOLD |

探针也发现交接命令名需更正：CLI 接受 `dispatch-next`，不接受 `dispatch`（argparse exit 2）。此外，相同 idempotency key 重放成功的 `init` 时，首次返回 DISPATCHABLE/revision 3，重放返回 revision mismatch；不是稳定的幂等响应。

确认的放行级缺陷（探针/代码位置）：

1. **P1 — 过期 lease 可绕过 stop evidence。** `scripts/lease_store.py:25-34` 的 `acquire_many()` 遇到过期 ACTIVE lease 后仅把 lease 改为 EXPIRED，随后直接发出新 namespace lease；没有把旧 task 改为 UNKNOWN 或等待 stop confirmation。隔离复现：旧 task 仍为 LEASED、`stop_evidence=None` 时，新 task 已在同一 namespace 获得 ACTIVE lease。安全停止只能由 `expire()`→UNKNOWN→`confirm_stop()` 路径保证，但该快捷分支绕过了它。
2. **P1 — `plan` 可把冻结清单外的 TaskSpec 排入执行。** `scripts/orchestrate.py:28` 和 `scripts/state_store.py:120-135` 未校验新增任务在 run manifest 中，也未核对其 `manifest_hash`。隔离复现：传入 `task_id=rogue`、不同 manifest hash 和越界 write_set，`plan` 返回成功，随后 `dispatch-next` 实际派发 `rogue` 与 `task-a`。这是直接的范围冻结绕过。
3. **P1 — handoff 未绑定外层任务、冻结 TaskSpec、lease/revision 与测试结果。** `scripts/handoff_contract.py:25-30` 只对照 packet 自报的 write_set，测试回执只要求有 command/exit_code 字段；`scripts/semantic_guard.py:9-19` 不校验 exit_code；`scripts/orchestrate.py:42-52` 未将 packet 的 task/run/lease/revision 对照当前持久化任务和租约。隔离复现：外层 task-a 的有效 lease 携带 `task_id=task-b` 的 packet，且测试 `exit_code=1`，handoff 仍成功并把 task-a 推进至 AUDIT_PENDING。
4. **P1 — AuditReceipt 的 PASS 可伴随失败检查和未验证路由。** `scripts/audit_receipt.py:15-25` 未约束 PASS 时 `scope_result`、`behavior_result`、`evidence_result` 的通过值，也允许 `route_result=ROUTE_UNVERIFIED`；`scripts/orchestrate.py:55-64` 仅按 `decision == PASS` 转为 ACCEPTED。隔离调用 `validate_receipt()` 接受了 `decision=PASS`、三个检查均为 `FAIL`、route 未验证的收据。与交接要求的未验证运行时必须保持 NOT_ACCEPTED 冲突。
5. **P1/P2 — 状态层没有强制 lease write 必须带 epoch 和 fencing token。** `scripts/state_store.py:161-167` 只有调用方提供时才校验这些字段；某些入口（包括 retry）允许省略。直接调用状态层只提供有效 `lease_id`、省略 epoch/token，仍成功将任务写为 RUNNING；应在底层持久化边界强制，而不只依赖入口约定。
6. **P2 — retry 的 attempt 与状态迁移非原子。** `scripts/orchestrate.py:74-75` 先提交 `record_attempt()`，再提交状态迁移。隔离复现：UNKNOWN 任务持有已过期 lease 时，retry 因 `LeaseError: lease inactive or expired` 失败，但 attempts 已从 0 增至 1，消耗重试额度而任务仍 UNKNOWN。
7. **P2 — 多 namespace lease 只释放/确认一个 lease。** `scripts/lease_store.py:63-85` 的 release/confirm_stop 只处理传入 lease；confirm_stop 可将整个 UNKNOWN task 重置为 PLANNED 并清空主 lease_id，但同 task 其他 namespace lease 仍可能 ACTIVE，造成残留锁/恢复不一致。
8. **P2 — 状态 ledger 漏记租约释放与 stop-confirm 状态变更。** `scripts/lease_store.py:63-85` 直接 UPDATE task 状态，缺少对应 event，无法完整重建恢复前后的状态。
9. **P2 — WorkerAdapter 不构成强隔离/有界资源边界。** `scripts/worker_adapter.py:38-44` 通过 `communicate()` 先把完整 stdout/stderr 放入内存后才截断；超时只 kill 直接子进程，没有验证进程树收尾、cwd/argv/本地 write-set 与冻结 TaskSpec/lease 绑定。当前不应用于不可信命令或作为写入沙箱证明。
10. 另需补测/修订：TaskSpec 依赖只验证存在而未检测 DAG 环；`dispatch-next` 未传 controller_epoch 时每次都会 acquire 新 epoch，可能使既有 worker 的 epoch 失效；`12-v2-tester-handoff.md` 中的 `dispatch` 应改为真实 CLI 命令 `dispatch-next`。

独立审阅：另一个只读审计 agent 独立核对了 lease、handoff、AuditReceipt、plan、fencing、retry、ledger、WorkerAdapter 和 DAG/epoch 风险，结论同样为**不建议进入真实并行写入或审计放行测试**。它没有修改文件或配置，也没有提供正式 `MAD_ROUTE_RECEIPT`；因此这是独立代码审阅发现，不是正式路由凭证/审计收据。

测试阶段判定：基础测试和受控 CLI 路径虽然全绿，但上述 P1 缺陷已由隔离探针确认，当前包**不可作为可用版本放行，也不建议按原 handoff 开始真实并行写入、基于 AuditReceipt 的验收或前向工作流测试**。允许的下一步仅是受限隔离复现和修复验证（临时 SQLite、无真实 Hook/Profile/Provider/外部副作用）；修复后必须重算 manifest、重跑 V2/V1/专项探针和独立审计。`NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED` 继续有效。真实 Hook/Profile、实际 model/effort provenance、原五个及新增五个前向工作流仍未运行。

终态 ServerChan 通知：调用 bundled notifier 成功，`ok=true`、`attempts=1`；通知只报告审计完成与未放行结论，不代表版本通过。


### 4.19 V2.1.3 缺陷修复、回归和本地真实探针（2026-09-27）

本节 supersede 4.18 中针对旧包的缺陷结论。仅修改 `skills/multi-agent-dev-v2/` 及本证据/交接文档；保留 V1 六个既有修改，不 reset、clean、覆盖、提交、推送或部署。

修复清单：

- `lease_store.py`：过期 namespace lease 先整体标记 EXPIRED、任务转 UNKNOWN 并阻断重新申请；release/confirm-stop 按完整 namespace bundle 原子处理，强制 fencing token、stop evidence 和 revision bundle；运行中任务释放后清理 owner/lease 并转 UNKNOWN；每个状态变化写入 event。
- `state_store.py`：底层 task/run 写入强制 epoch、owner、fencing token、lease 状态/期限和 manifest hash；多 namespace 写入要求完整 token map；retry 的 attempt、状态、预算和 event 同一事务；禁用非原子 `record_attempt`；event payload 自动带 `_ledger` 与 `_fence`；evidence 绑定 task/run/manifest；直接存储 AuditReceipt 复用完整 PASS、provenance 和 AUDIT_PENDING 校验。
- `orchestrate.py` / `handoff_contract.py`：handoff 逐项核对 task/run/manifest/attempt/lease/revision；changed_paths 只按冻结 TaskSpec write_set；成功 handoff 要求零退出测试回执；多 namespace 的 fencing bundle 可随 packet/请求贯穿；retry 传递并校验 bundle。
- `audit_receipt.py` / `task_scheduler.py`：PASS 要求三个维度、route、hook、runtime source、observed model/effort、evidence refs 全部明确通过且无 correction；READY_TO_MERGE 再次检查同一门禁。
- `parallel_manifest.py`：拒绝 DAG 环和越界 read/write scope。CLI 继续使用 `dispatch-next`；同 owner 默认复用 epoch，显式 takeover 递增并使旧 worker 失效；该复用语义限定为单一受信 controller 进程假设。
- `worker_adapter.py`：安全声明固定为 trusted local command runner，不把它当成不可信代码沙箱或 write-set enforcement；进程树终止和资源隔离仍是明确限制。

精确 manifest 复算算法：root=`skills/multi-agent-dev-v2`；递归取文件并排除所有 `__pycache__`；相对 POSIX 路径按 `.lower()` 排序；每行写入 `<relative-path> <sha256(file-bytes)>\n`；对整个 UTF-8 清单 SHA-256。结果：**45 files，SHA-256 `184bb6f9e8bffd88e9f7fa70b78a2e0d2e70d9c41ccfc92699138e7493ab14bb`**。

测试与探针：

- V2：`cd /d C:\\Users\\T14S\\.codex\\skills\\multi-agent-dev\\skills\\multi-agent-dev-v2 && python -B -m unittest discover -s tests -p "test_*.py" -q` → **61/61 OK**。
- V1：`set "PYTHONUTF8=1" && set "PYTHONIOENCODING=utf-8" && chcp 65001 >NUL && python -B -X utf8 -m unittest discover -s skills\\multi-agent-dev\\tests -p "test_*.py" -q` → **64/64 OK**。通知负例和超时输出属于测试路径，最终退出码为 0。
- 编译：`python -m compileall -q skills\\multi-agent-dev-v2` → 通过。
- 差异：`git diff --check` → 退出码 0；仅既有 V1 六文件的 LF/CRLF 提示，无 whitespace error。
- 独立 Python/SQLite CLI 探针：真实 Windows 子进程调用 `init`、`dispatch-next`、`status` 均返回码 0；状态依次为 DISPATCHABLE、RUNNING，task-a 获得 ACTIVE lease。WorkerAdapter 真实子进程返回 exit code 0、timeout=false，并将 `api_key=secret` 脱敏为 `api_key=<redacted>`。这证明本地隔离实现，不等同 Codex Hook/Profile/真实 Provider 或实际模型凭证。

独立只读审计待写入最终 receipt；截至本节，尚未收到正式 `MAD_ROUTE_RECEIPT`，也没有实际 model/effort provenance。运行时门禁继续为 **NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED**。



### 4.20 独立只读代码审计结果（最终快照）

本节仅在独立审计者返回后填写正式 receipt；若无正式 `MAD_ROUTE_RECEIPT` 或真实运行时凭证，审计结论只能表示代码契约复核，不能表示路由/Hook/模型运行时通过。


### 4.21 最终 fence 收紧后的 superseding hash（2026-09-27）

在 4.19 后又把底层 `transition_task` 对 RUNNING/CHECKPOINTED/WAITING_HANDOFF/AUDIT_PENDING/ACCEPTED 的 lease fence 要求设为强制；V2 仍 **61/61 OK**，其余 V1、compileall、diff 检查结果不变。按 4.19 明确的 canonical manifest 算法重新复算：**45 files，SHA-256 `0b9c7815690c040bc9bdbfe95956a88aa44bdb5aba509be5ddf1493fe77fb175`**。本 hash supersedes 4.19 的 `184bb6...`；此前 hash 不再作为测试目标。


独立审计者最终只读复核回传：当前代码路径通过 lease/handoff/retry bundle/CAS/event ledger/direct AuditReceipt 等检查，`python -B -m unittest discover -s tests -p "test_*.py" -q` 为 **61/61 OK**；未改文件、配置、依赖。残余为 P2/限制：同 owner epoch reuse 依赖单一受信 controller 进程；WorkerAdapter 仍不是进程树沙箱或资源隔离；没有真实 route/model-effort/Hook/Profile 运行凭证。审计者同时报告了一个使用不同“path+/0/+bytes”清单算法得到的 hash（`5c12ff62...`）；该值不作为本项目 manifest 目标。项目冻结算法已由证据文档定义并由主会话复算为 `0b9c7815690c040bc9bdbfe95956a88aa44bdb5aba509be5ddf1493fe77fb175`。因此独立结论是**代码契约 HOLD/可交测试专员复核，运行时仍 NOT_ACCEPTED**，不是独立路由或真实模型通过。


### 4.22 V2.1.4 独立复核：发现仍不可放行的门禁缺口（2026-09-27）

主会话对开发返回的 V2.1.4 在当前工作树独立复算 manifest：45 files，SHA-256 与 4.21 完全一致（`0b9c7815690c040bc9bdbfe95956a88aa44bdb5aba509be5ddf1493fe77fb175`）。当前复跑结果：V2 **61/61 OK**、V1 **64/64 OK**、缺陷回归 **10/10 OK**、compileall 通过、`git diff --check` 退出码 0；CLI/SQLite 隔离探针成功。上述绿灯没有覆盖以下反例，不构成验收。

独立只读审计结论：**FAIL / NOT_ACCEPTED**。审计者未修改文件，并独立复核测试套件；真实 Codex Hook/Profile/实际模型与思考强度 provenance 仍不可用，没有正式 `MAD_ROUTE_RECEIPT`。本会话另行执行隔离反例，确认：

1. **P1 — Audit PASS 没有把运行时路由和证据引用绑定到冻结 TaskSpec/EvidenceIndex。** `audit_receipt.py` 只要求 observed model/effort 和 evidence refs 非空；`orchestrate.py` 与 Scheduler 没有对照 TaskSpec requested route，也没有解析 evidence refs 并验证已登记证据。`compare_requested_observed()` 未接入生产放行路径。隔离端到端探针使用与 TaskSpec 不同的 observed model/effort、自报 `codex-runtime`、不存在的 evidence ref，以及不匹配 acceptance check 的零退出命令，仍让 task 进入 `ACCEPTED`、run 进入 `READY_TO_MERGE`。因此当前 PASS 不能证明路由/测试/证据属实。
2. **P1 — 并发 TaskSpec 可声明相同 write_set 并同时派发。** 两个无依赖任务写同一个 `src/a.py`、使用 `ns-a`/`ns-b` 不同 namespace；ScopeManifest 接受该清单，Scheduler 同时返回两项 ready 并取得两份 lease。与 D06 的不重叠写集/单 writer 约束冲突，可能造成并行写覆盖。
3. **P1 — supersedes 和 Run 状态未阻止旧/非可派发 run 继续启动任务。** 隔离探针创建 revision 2 且声明 `supersedes=run-1` 的新 manifest 后，旧 run 仍可被 `dispatch-next` 派发；旧 run 状态仍是 `INTAKE`。Scheduler/dispatch 未校验 Run 是否处于 `DISPATCHABLE`，manifest supersedes 关系也未对旧 run 执行 fencing/quarantine。
4. **P1/P2 — event `_ledger` 保留调用者伪造值。** `state_store._event_payload()` 对 `manifest_hash`、`controller_epoch`、`entity_revision` 使用 `setdefault`；隔离探针注入 `_ledger` 后，事件 payload 中伪造字段原样落库，与事件 canonical 列/状态不一致，削弱审计账本可信度。
5. **P2 — retry 的 CLI 前置检查绕过事务内幂等回放。** 对同一失败 task 使用相同 idempotency key 和相同 retry 请求重放，CLI 先根据更新后的 attempt count 推导出新的 `attempt_id`，底层随后抛 `IdempotencyConflict`，没有返回首次结果。若 attempt budget 已耗尽，还会在到达幂等回放前返回预算错误。
6. **P2 — handoff 流程是多次独立事务且无幂等键。** 中途进程崩溃可能留下部分状态；重放原 packet 可能被 revision 检查拒绝。handoff 中的 test command/exit code 仍是调用者自报，不等于执行记录或 EvidenceIndex 中可复核的真实测试凭证。

WorkerAdapter 仍为可信本地命令 runner，而非不可信代码沙箱；超时终止进程树和资源隔离也未证实。该限制已披露，但不能据此宣称 write_set 在操作系统层得到强制执行。

本节 supersedes 4.21 中“未发现新的 P0/P1/可交测试专员复核”的结论。V2.1.4 当前**不应进入接受/合并门禁，也不应把 61 项测试通过解释为缺陷已清零**。下一轮至少需为上述 P1 增加生产路径校验和反例回归测试；修复后重新运行全套测试并独立复审。运行时门禁继续保持 **NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED**。本轮仅审计与更新本证据文档；没有改 V2/V1 代码、Profile、全局 Hook、依赖或 Git 历史，也没有提交、推送或部署。


### 4.23 V2.1.5 P1 缺陷修复、独立反例复核与最终交接（2026-09-27）

本节 supersede 4.22 的 FAIL 结论所针对的代码快照。仅修改 V2 包代码/测试并追加本证据与交接文档；保留 V1 六个既有修改，未安装 Profile、未修改或信任全局 Hook、未安装 PyYAML、未提交、推送或部署。

修复与回归：

- state_store.py：PASS receipt 在状态层绑定冻结 TaskSpec 的 requested model/effort；要求已登记、同 run/task/manifest 的 EvidenceIndex 记录；要求 route evidence 的 observed model/effort 与冻结请求一致；要求 acceptance check 与成功 TEST_RECEIPT、handoff command 与持久化测试命令一致。ACCEPTED 与 READY_TO_MERGE 都经过该绑定检查。
- task_scheduler.py：ready/dispatch 只允许 DISPATCHABLE 或 RUNNING；跨 namespace 的 write_set 按大小写不敏感的相等/父子路径冲突检测，冲突候选不同时派发。
- state_store.py / parallel_manifest.py：supersedes 校验旧 run 存在、无活跃 lease/task 后在同一事务中把旧 run 和计划任务置为 SUPERSEDED 并写事件；INTAKE、SUPERSEDED 等非可派发 run 被阻断。
- state_store.py：event _ledger 的 manifest hash、controller epoch、entity revision 由状态层重建并拒绝调用者不一致值；retry 增加事务外幂等回放；handoff 使用带 fencing 的单事务 state chain 和稳定幂等结果。
- tests/test_v21_defect_regressions.py 新增并通过：跨 namespace 重叠 write_set、INTAKE/SUPERSEDED 派发、model/effort/evidence/acceptance command 反例、ledger 伪造、retry 重放、handoff 重放。

最终 package 复算算法：root=skills/multi-agent-dev-v2；递归文件排除 __pycache__；相对 POSIX 路径按 .lower() 排序；每行 <relative-path> <sha256(file-bytes)>\\n；对 UTF-8 清单整体 SHA-256。当前 45 files，manifest SHA-256：

    43e601a9b016c681cc3880d1c0e6333c293dd9a0986ce3ce458f4e4da2939b92

验证结果：V2 python -B -m unittest discover -s skills\\multi-agent-dev-v2\\tests -p "test_*.py" -q → 67/67 OK；V1 显式 UTF-8 python -B -X utf8 -m unittest discover -s skills\\multi-agent-dev\\tests -p "test_*.py" -q → 64/64 OK；V2 scripts/tests compileall 通过；git diff --check 退出码 0，仅既有 V1 LF/CRLF 提示。

隔离真实探针：Windows Python 子进程调用 orchestrate.py init、dispatch-next、status 均返回码 0；WorkerAdapter 本地子进程 exit code 0、timeout=false，api_key=secret 脱敏为 <redacted>。这只证明本地隔离实现，不是 Codex Hook/Profile、Provider 或模型运行时凭证。

独立只读复核重新执行了审计凭证路由/证据/验收命令反例、重叠 write_set、superseded run 派发反例，均输出 BLOCKED；代码审计结论为 P1 反例已修复 / 代码级 HOLD。没有正式 MAD_ROUTE_RECEIPT，没有 Hook/Profile discovery、实际 model/effort provenance 或五个前向工作流证据，因此状态继续为 NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED，不得标记 ACCEPTED、READY_TO_MERGE 或独立路由通过。


### 4.24 Final test assertion superseding hash（2026-09-27）

4.23 之后只在 V2 回归中补充了 superseded run 的 integrate-check 阻断断言；V1 六个既有文件未改动。最终 V2 仍 67/67 OK，V1 显式 UTF-8 仍 64/64 OK，compileall 通过，git diff --check 退出码 0。

按同一 canonical 算法复算：**45 files，SHA-256 580673c006d75154358982cf8c92bbc4efb7ee99a3da57823c5771d88e1e38e1**。该 hash supersedes 4.23 的 43e601a9...；测试专员必须以此 hash 重新复算。独立反例复核结论不变：P1 路径均 BLOCKED；没有 MAD_ROUTE_RECEIPT、Hook/Profile/实际 model-effort provenance 或前向工作流证据，状态仍为 **NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED**。


### 4.25 V2.1.5 测试专员复跑与新增反例（2026-09-27）

按本轮交接执行；没有改动 V2/V1 代码、Hook/Profile、依赖或 Git 历史。V1 六个既有修改仍为原来的六个文件。测试前 `git status --short` 显示该六文件、`docs/` 与 `skills/multi-agent-dev-v2/` 为既存状态。

**Manifest 复算差异：**当前包为 45 files。若“按小写排序”解释为仅以 `relative_path.lower()` 作为排序键、每行保留原始相对 POSIX 路径，则得到 SHA-256 `555808d3eb54ec5c4c62047bb59f141266f1e946f569e298854ce4f87c8db58d`，与交接声明的 `580673c006d75154358982cf8c92bbc4efb7ee99a3da57823c5771d88e1e38e1` 不同。声明值恰好对应另一种算法：除排序外还把每行路径文本本身转换成小写。交接目前未明确路径文本是否也要小写；测试目标 hash 因而有歧义，须固定算法后再声称 hash 匹配。两个计算都排除了 `__pycache__`，并对最终 LF 清单计算 SHA-256。

**命令与结果：**

- `python -B -m unittest discover -s skills\\multi-agent-dev-v2\\tests -p "test_*.py" -q` → **67/67 OK**。
- 设置 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8` 后运行 `python -B -X utf8 -m unittest discover -s skills\\multi-agent-dev\\tests -p "test_*.py" -q` → **64/64 OK**。通知缺少 verification、通知超时等 stderr/stdout 是负向/超时用例输出，最终退出码 0。
- `python -B -m unittest discover -s skills\\multi-agent-dev-v2\\tests -p "test_v21_defect_regressions.py" -v` → **16/16 OK**。
- `test_parallel_v21.py` → **22/22 OK**；`test_notify_serverchan.py` → **9/9 OK**；`test_task_terminal_notify.py` → **9/9 OK**。
- `python -B -m compileall -q skills\\multi-agent-dev-v2` → 退出码 0。
- `git diff --check` → 退出码 0；仅原有 V1 六文件的 LF/CRLF 提示。
- 独立 Windows Python 子进程 CLI 探针：临时 SQLite 上 `init`、`dispatch-next`、`status` 均退出码 0；Run=`RUNNING`，task-a=`LEASED`。
- 额外写集边界探针：不同 namespace 下 `src` 与 `src/a.py` 的父子路径冲突只派发 task-a；错误 effort（requested high / observed xhigh）被 TaskSpec 绑定校验拒绝。

**未覆盖边界 / 阻断项：**

1. **P1 — handoff 测试命令采用子串匹配，仍可用不相同的命令通过审计并 READY_TO_MERGE。** 在隔离端到端流程中，EvidenceIndex 登记的成功命令是 `python -m unittest discover -s tests -p test_*.py`，TaskSpec acceptance check 为 `unit`，handoff packet 却只声明 `command="unit"`。当前 `validate_audit_receipt_binding()` 的验收检查和 handoff command 检查使用 `check in command` / `command in indexed_command`，所以该不相同的命令通过，AuditReceipt 被存为 PASS，task 到达 ACCEPTED，integrate-check 最终进入 **READY_TO_MERGE**。本探针使用临时 SQLite 和人工构造的记录，仅复现本地门禁行为，不是真实测试或 Codex provenance。应使用规范化的测试 ID/精确命令绑定，并新增“含子串但不相等必须拒绝”的端到端回归。
2. 现有 `test_audit_receipt_binds_route_evidence_and_acceptance_command` 的 wrong-command 分支只登记了 `source=unittest` 的测试证据，没有有效 route evidence；`validate_audit_receipt_binding()` 会先因缺少匹配 route evidence 抛错。因此该断言没有单独证明 wrong command 被拒绝。需要按上面的隔离复现补齐有效 route evidence，只改变 handoff command，并断言明确的命令绑定错误。
3. 合成 EvidenceIndex 字段（如 `source="codex-runtime"`、`hook_status="HOOK_ENFORCED"`）不等于实际 runtime provenance。本轮按用户限制没有调用真实 Hook/Profile/Provider，也没有正式 `MAD_ROUTE_RECEIPT`、实际 model/effort provenance 或五个前向工作流证据。CLI/SQLite/子进程成功不能关闭这些门禁。

本轮全套单测均通过，但第 1 项是可达 `READY_TO_MERGE` 的反例，且 hash 算法描述有歧义。因此 V2.1.5 **测试未通过接受门禁**；建议先修精确命令/证据绑定并补测试，明确 manifest 算法，随后对新冻结快照重跑全部验证。状态继续为 **NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED**。按“不要产生外部副作用”限制，本轮未发送 ServerChan 或其他外部通知。


### 4.26 V2.1.6 精确测试命令绑定与 manifest 算法统一（2026-09-27）

本节 supersede 4.25 中的 P1 结论。仅修改 V2 状态校验和缺陷回归测试，并追加证据与交接文档；V1 六个既有修改未动，未安装 Profile、未修改全局 Hook、未安装 PyYAML、未提交或推送。

修复：

- state_store.py 的 acceptance check 改为成功 TEST_RECEIPT 的 command_or_ui_step 与冻结 acceptance_checks 逐字相等。
- handoff packet 的 test_receipts.command 必须是非空字符串、exit_code 必须是整数 0，并与已登记成功 TEST_RECEIPT 的 command_or_ui_step 逐字相等；不再使用子串匹配。
- 新增完整端到端负例：EvidenceIndex 中的完整命令、route evidence、model/effort、manifest、lease 和 handoff 均有效，packet 只写完整命令的子串 unit；attach-receipt 被明确阻断，task 保持 AUDIT_PENDING，run 不进入 READY_TO_MERGE。

最终 manifest 规范统一为：路径只用于排序键，即按 relative POSIX path.lower() 排序；清单行保留原始 relative POSIX path 文本，不对路径文本再做大小写转换。每行格式为 original-relative-path + 空格 + file SHA-256 + LF；对完整 UTF-8 清单计算 SHA-256。当前 45 files，按该规范复算：

    d2c674516fbc3943e8bc04b82aee170697dd4e918eb2c080ee8daec018afb39d

旧 hash 580673... 对应“排序并将清单行路径文本一并小写”的另一算法，不再作为当前规范目标。

验证：V2 全套测试 **68/68 OK**；V1 显式 UTF-8 **64/64 OK**；专项 handoff/缺陷回归 **17/17 OK**；compileall 通过；git diff --check 退出码 0；Windows CLI init → dispatch-next → status 子进程探针通过。独立审计待复核。运行时门禁继续为 **NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED**。


### 4.27 V2.1.6 复修后专项复跑与代码级审计记录（2026-09-27）

复修后重新执行：

- V2 全量：`python -B -m unittest discover -s skills\\multi-agent-dev-v2\\tests -p "test_*.py" -q` → **68/68 OK**。
- V1 回归：显式 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、`python -B -X utf8` → **64/64 OK**；既有六个 V1 文件保持未改动。
- 缺陷回归 `test_v21_defect_regressions.py` → **17/17 OK**；并行状态 `test_parallel_v21.py` → **22/22 OK**；`test_notify_serverchan.py` 与 `test_task_terminal_notify.py` 各 **9/9 OK**。
- `python -B -m compileall -q skills\\multi-agent-dev-v2` 与 `git diff --check` 均通过；后者只报告既有 V1 文件 LF/CRLF 提示。
- 独立 Windows Python 子进程 CLI 探针：临时 SQLite 上 `init → dispatch-next → status` 均 rc=0，Run=`RUNNING`、task-a=`LEASED`。

命令绑定代码级审计：在只读独立进程中检查 `validate_audit_receipt_binding()`，确认 acceptance check 与 `command_or_ui_step` 使用逐字相等，handoff `test_receipts.command` 与持久化测试命令使用逐字相等；未发现原子字符串 `in` 子串匹配。审计输出：`STATIC_EXACT_BINDING_AUDIT_PASS`。同一进程确认本证据记录的当前 hash 算法说明包含 `.lower()` 排序键、保留原始路径文本和 LF。

当前 V2 包仍为 **45 files**；canonical manifest 规范为：排除 `__pycache__`，按 `relative POSIX path.lower()` 排序，清单行保留原始相对路径，行格式为 `<path> <file-sha256> + LF`，对完整 UTF-8 清单求 SHA-256。复算 hash：

    d2c674516fbc3943e8bc04b82aee170697dd4e918eb2c080ee8daec018afb39d

独立审计边界：现有独立审计 Agent 的 Linux 沙箱无法挂载本机 `C:\\Users\\T14S\\.codex\\skills\\multi-agent-dev`，因此其正式结论为 **HOLD**，没有 `MAD_ROUTE_RECEIPT`，不能将其写成 PASS。主会话完成的只读静态审计仅证明代码级精确命令绑定，不证明 Codex Hook/Profile、Provider、真实 model/effort provenance 或五个前向工作流。

状态继续为 **NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED**；不得标记 ACCEPTED、READY_TO_MERGE 或独立路由通过。未安装 Profile、未修改或信任全局 Hook、未安装 PyYAML、未提交、推送或部署。


### 4.28 V2.1.7 exit_code 类型校验修复与复验（2026-09-27）

测试专员发现 `EvidenceRecord(exit_code=False)` 会被 SQLite 归一为整数 0，随后绕过 handoff/审计门并进入 READY_TO_MERGE。本轮只修改 V2 包和回归测试，V1 六个既有修改未动。

修复：

- `scripts/evidence_index.py`：EvidenceRecord 对所有非空 `exit_code` 要求 `type(exit_code) is int`；TEST_RECEIPT 必须提供整数退出码。
- `scripts/state_store.py`：底层 `record_evidence()` 在事务前执行同样的严格类型校验，拒绝调用者绕过 EvidenceRecord 直接写入 `False`、浮点数或字符串。
- `scripts/handoff_contract.py`：成功 handoff 的 test receipt 要求命令为字符串、`type(exit_code) is int` 且值为 0。
- `tests/test_v21_defect_regressions.py`：新增 `False`、`0.0`、`"0"` 在 EvidenceRecord、底层 SQLite 写入和 HandoffPacket 三个入口的拒绝测试；数据库中不产生错误证据。

复验结果：V2 全量 **69/69 OK**；V1 显式 UTF-8 **64/64 OK**；缺陷回归 **18/18 OK**；并行状态 **22/22 OK**；两组通知测试各 **9/9 OK**；compileall、`git diff --check`、Windows CLI `init → dispatch-next → status` 均通过。

独立只读进程静态与行为审计输出 `INDEPENDENT_EXIT_CODE_AUDIT_PASS`：确认三层代码存在严格 `type(...) is int` 校验，并逐一验证 `False`、`0.0`、`"0"` 均被拒绝。此前的错误路径无法再写入 EvidenceIndex，也无法构造成功 HandoffPacket。

当前 package 仍为 45 files；manifest 算法不变：排除 `__pycache__`，按 `relative POSIX path.lower()` 排序，清单行保留原始路径，使用实际 LF，对完整 UTF-8 清单求 SHA-256。最新 hash：

    8a3468bb94ddab36cbd41efbcbf377f297b08b3f9adc24d95ebebed2cba48a23

本轮没有真实 Hook、Profile、Provider、模型/思考强度凭证或正式 `MAD_ROUTE_RECEIPT`；独立运行时门禁继续保持 **NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED**。未安装 Profile、未修改全局 Hook、未安装 PyYAML、未提交、推送或部署。

### 4.29 V2.1.7 运行时验证阶段复核（2026-09-27）

在用户授权进入下一阶段后，对 V2.1.7 冻结包执行只读复核；未修改全局 Hook、未安装 Profile、未调用真实 Provider、未提交/推送/部署。

本轮复验：

- V2 全量：`python -B -m unittest discover -s skills\\multi-agent-dev-v2\\tests -p "test_*.py" -q` → **69/69 OK**。
- V1 UTF-8 回归：显式 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、`python -B -X utf8` → **64/64 OK**。
- V2.1.7 缺陷回归 → **18/18 OK**；并行状态 → **22/22 OK**；通知测试各 **9/9 OK**。
- `compileall` → 通过；`git diff --check` → 退出码 0，仅有既存 V1 文件换行提示。
- Windows 临时 SQLite 子进程 CLI `init → dispatch-next → status` → 均返回 0。
- 当前 V2 包仍为 **45 files**；按统一清单算法独立复算 SHA-256：

      8a3468bb94ddab36cbd41efbcbf377f297b08b3f9adc24d95ebebed2cba48a23

运行时探针结果：

1. 只读检查 `C:\\Users\\T14S\\.codex\\hooks.json` 显示当前全局 `PreToolUse` 仍指向 V1 的 `skills/multi-agent-dev/.../pre_spawn_route_guard.py`；没有证据表明 V2 route contract 已接入实际派发 Hook。
   对该已安装 V1 脚本做的直接 stdin 合成调用可返回 `MAD_ROUTE_RECEIPT`，但这只是脚本适配器的离线行为，不是 Codex 实际 Hook 事件，也不能证明 V2 路由已接入。
2. V2 profiles 仍只存在于技能包 `skills/multi-agent-dev-v2/profiles/`；全局 `C:\\Users\\T14S\\.codex\\profiles/` 未发现 `madv2_*` profile，不能据此声称 Profile discovery 或实际加载成功。
3. 通过真实子智能体派发接口执行只读 route probe，工具结果只返回子任务名 `/root/madv2_runtime_route_probe`，没有 `MAD_ROUTE_RECEIPT`、实际模型、思考强度或 Hook 收据。该子任务随后停止；不使用其自述作为凭证。
4. 本轮独立只读窄审计确认 `exit_code` 类型门禁和精确命令绑定均通过，但没有形成正式 `MAD_ROUTE_RECEIPT`，也没有完成五个前向工作流或真实 Provider 验证。

因此，本轮关闭的是 V2.1.7 代码缺陷与本地回归门禁；真实运行时门禁仍保持：

    NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED

### 4.30 隔离 Codex 运行时认证门禁（2026-09-27）

用户明确授权在临时隔离目录启动独立 Codex 运行时；授权边界仍为不修改全局 Hook/Profile、不调用真实 Provider、不提交或推送。

- 使用独立 `CODEX_HOME=C:\\Users\\T14S\\AppData\\Local\\Temp\\madv2-runtime-1676i_y0`，Codex CLI `0.157.1`。未复制、读取或修改全局认证文件。
- `codex exec --json --ephemeral --ignore-user-config --skip-git-repo-check --sandbox read-only -` 实际启动但返回 `401 Unauthorized`，表明隔离 `CODEX_HOME` 尚未认证；这不是 V2 Hook/Profile/model 路由通过或失败的运行时证据。
- 随后在隔离 `CODEX_HOME` 内启动 `codex login --device-auth`。官方设备登录流程正在等待用户在本机浏览器完成一次性授权；验证码不写入本证据文档。
- 全局配置运行的一次无工具探针虽成功返回固定文本，但未提供可验证的实际模型/思考强度，也没有加载 V2 route Hook/Profile，因此不计作路由验收证据。
- 临时目录中已生成隔离运行状态数据库和 skills 缓存；技能仓库既有用户改动保持不变，未发现本轮对全局 Hook/Profile 的编辑。没有调用真实 Provider、没有提交或推送。

当前等待用户完成隔离设备登录。登录完成后才可继续验证临时 V2 Hook/Profile 注册、派发收据及实际 model/effort provenance；在此之前状态保持：

      NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED

### 4.31 隔离运行时登录后复核与真实派发探针（2026-09-27）

用户完成临时 `CODEX_HOME` 的官方设备登录后，继续使用 Codex app-server `0.158.0-alpha.2.1` 做真实运行时探针；仍未修改全局配置、未调用真实 Provider、未提交或推送。

- `codex login status` 在临时目录返回 `Logged in using ChatGPT`。
- app-server `initialize`、`thread/start`、`turn/start` 均成功。线程返回实际 `model=gpt-6-sol`；随后 `thread/settings/updated` 明确返回本轮 `effort=xhigh`。这证明该隔离 app-server 能返回主线程的运行时设置，但仍不是子 Agent 路由收据。
- app-server 确实生成了 `collaboration.spawn_agent` function call。正向提示下曾看到 function-call 参数为 `model=gpt-6-luna`、`reasoning_effort=high`，与 execute/I1 目标一致；由于临时线程随后被关闭，未形成子线程 provenance，不能把模型自发选择当作 Hook 强制证据。
- 反向探针明确要求同一 execute/I1 标记使用错误的 `model=gpt-6-sol`、`reasoning_effort=max`。原始 app-server `rawResponseItem/completed` 中 function-call 参数仍为 `model=gpt-6-sol`、`reasoning_effort=max`、`fork_turns=all`，没有被改写或拒绝；调用最终因 `collab spawn failed: no thread with id` 结束。
- 临时 Hook 脚本按收到事件写入 `hook_events.jsonl`；整个 app-server/CLI 探针后该文件不存在，且配置没有报错。这说明当前 app-server 派发路径没有触发该临时 PreToolUse Hook（或该路径不支持该 Hook 配置），不能宣称 `HOOK_ENFORCED`。该反向结果也证明“请求参数正确”不能替代运行时门禁。
- 之前的 `codex exec` CLI 探针同样只返回普通 Agent 文本，未触发临时 Hook；CLI 能接受未知 profile 名称而继续运行，不能以 `--profile` 参数本身证明 Profile discovery 或实际加载。

本轮新增结论：隔离认证已解决，主线程 model/effort provenance 可由 app-server 的线程设置读取；但目标子 Agent 派发仍无 Hook receipt，错误路由可以进入 function-call，且子线程启动本身还存在 `no thread with id` 的运行时故障。因此 V2.1.7 仍不得验收，状态继续为：

      NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED

要进入验收，至少需要目标 Codex 桌面派发路径提供：对允许路由的原始 `MAD_ROUTE_RECEIPT`、对错误模型/effort 的拒绝或改写、成功子线程的实际 model/effort provenance，以及不依赖已关闭父线程的稳定 spawn/handoff 证据。

### 4.32 V2.1.8 运行时派发门禁加固与复验（2026-09-27）

针对 4.31 暴露的“子 Agent 配置不可证明、父线程生命周期不稳定、spawn 失败可能被误接纳”问题，新增 transport-neutral runtime dispatch gate。该改造不修改全局 Hook/Profile、Provider、V1 六个既有修改或 Git 历史。

实现与文档：

- `skills/multi-agent-dev-v2/scripts/runtime_dispatch.py`：只接受父线程范围内的 child start、显式 `thread/settings/updated`、child terminal 事件；requested model/effort 与 observed provenance 分离。
- `skills/multi-agent-dev-v2/scripts/orchestrate.py`：增加只读 `runtime-gate`，不写账本、不调用 Provider，失败统一返回 `GATE_HOLD`。
- `skills/multi-agent-dev-v2/references/runtime-dispatch.md` 与 `docs/multi-agent-dev-v2/13-runtime-dispatch-hardening.md`：固化生命周期、证据来源和独立审计规则。
- `tests/test_runtime_dispatch.py`：补充 spawn failure 持续阻断、无 parent scope activity、thread/started 配置不充当 settings 证据、冲突 settings、父线程先终态等负例。

复验结果：

- V2 全量：`python -B -m unittest discover -s skills\\multi-agent-dev-v2\\tests -p test_*.py -q` → **83/83 OK**。
- V1 UTF-8 回归：`python -B -X utf8 -m unittest discover -s skills\\multi-agent-dev\\tests -p test_*.py -q` → **64/64 OK**。
- `compileall` → 通过；`git diff --check` → 退出码 0，仅有既存 V1 文件换行提示。
- 新增运行时定向测试 → **14/14 OK**。

首次独立只读审计发现并推动修复了 3 个 P1/高风险缺口：child ID 存在时的 spawn failure 未持久阻断、thread/started 中的 model/effort 被误当 route 证据、未校验 parent scope 的 `subAgentActivity` 可误绑 child。修复后新增冲突 settings 与 parent-terminal 负例，并重新执行全量测试。独立只读复核结论为 **PASS（代码级范围）**：确认上述六项门禁已落实，定向 **14/14**、全包 **83/83**、`py_compile` 均通过；未编辑代码、未提交。该 PASS 不等于真实 Codex Hook/Profile/子线程运行时通过，未形成正式 `MAD_ROUTE_RECEIPT` 前不得宣称真实运行时验收通过。

当前 V2 包排除所有 `__pycache__` 后为 **48 files**。Manifest 规则保持不变：相对 POSIX 路径按 `.lower()` 排序、清单保留原始路径、每行使用实际 LF，最后对完整 UTF-8 清单求 SHA-256。最新 hash：

    1ed0b18282c0c15bd1a07f993b4d9bef8e6f946288175dd89a037866deb64796

代码级运行时门禁现已对上述证据缺口 fail-closed；但真实 Codex 子线程的 Hook receipt、Profile discovery、实际 model/effort provenance、五个前向工作流和 Provider 仍未验证。因此状态继续保持：

      NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED

### 4.33 V2.2 Source Fidelity sidecar route/evidence binding (2026-10-01)

本轮只改动 multi-agent-dev-v2，不涉及业务项目代码。针对原型忠实度 Agent 增加了专用 role/profile 绑定、child dispatch evidence 与 SourceFidelityReceipt 同 child ID 绑定；Source Fidelity 保持 Controller DAG 之外的只读请求 sidecar，以避免 handoff/dependency 死锁。

- `RuntimeDispatchRequest` 增加 role 与 Profile class 强绑定；`source_fidelity` 不能借用普通 Audit Profile。
- 新增 `bind-source-dispatch` 操作：对 Source Fidelity child lifecycle、app-server settings 中 observed model/effort、terminal 事件和原始输入 event hash 生成并持久化 route evidence。
- Source-sensitive handoff 必须包含一个 Source Fidelity runtime dispatch evidence 与 PASS receipt；receipt 的 `producer_thread_id` 必须与 dispatch child ID 相同。孤立的完整静态 PASS receipt 无 dispatch evidence 时拒绝。
- runtime adapter 没有观察 sandbox 字段；`read-only` 仅表示请求/Profile 配置，不是实际运行时 sandbox 证明。runtime events/evidence 目前没有密码学签名，完整性依赖可信 Controller 从 Codex app-server 取得原始事件；不得表述成 tamper-proof。
- Source Fidelity sidecar 不是 TaskTemplate/DAG node；Main 负责显式判断来源敏感、冻结输出后在正式 handoff 前派发；Controller 不自动推断意图或自动创建 child。

### 4.34 V2.2 Source Fidelity 最终独立审计与发布前复验（2026-10-01）

独立只读复审结论：**PASS（代码与合同层，限定于可信 app-server→controller 事件入口）**。审计员未修改文件，复跑 V2 `108/108`，`compileall` 退出码 `0`，并用临时 StateStore 实测完整流程 `init → dispatch-next → bind-start → bind-source-dispatch → handoff`；合法证据进入 `AUDIT_PENDING`，无 Hook provenance 导致 Guard WARN 属于预期。孤立完整 PASS receipt、错误 child ID 和不匹配 role/profile 均被阻断。

发布前复验：V2 `108/108`、V1 回归 `64/64`、`compileall` 通过、`git diff --check` 退出码 `0`，意图文件 secret-pattern scan clean。本机活动安装目录与发布包均为 55 files，manifest SHA-256 相同：

    393544871c9ea264346d1b152176e9086eedef978263cc1c9c8a74eb552168f2

Skill Creator `quick_validate.py` 未能运行：环境缺少 PyYAML（`ModuleNotFoundError: No module named 'yaml'`）；未安装依赖。包内 metadata 测试、全量测试与编译均通过。

明确剩余限制：runtime evidence 无密码学签名、依赖可信事件入口；实际 sandbox 未观测；真实 Hook、Profile discovery、实际模型/effort provenance 与五个前向工作流未验证。因此只通过代码与合同层审计，不构成运行时验收；状态保持：

    NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED
