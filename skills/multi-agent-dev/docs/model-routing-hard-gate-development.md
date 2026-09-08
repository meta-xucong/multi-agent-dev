# 模型路由与派发硬门禁开发文档

> CONTRACT_REV: `v1.3.1-route-guard`
> 状态：契约冻结后实施
> 本文只描述 `multi-agent-dev` 的派发路由与作用域化 `PreToolUse` 门禁；不授权提交、推送、部署、付费调用或修改其他 Skill。

## 1. 目标与非目标

### 1.1 目标

在 Agent 派发工具到达执行前，对带有 `MAD_ROUTE_V1` marker 的调用做同步、可复现的模型路由校验和最小输入修正：

- 将职责、复杂度门和阶段映射到唯一的模型/推理强度。
- 对合法 marker 强制写入真值表路由，修正遗漏、错误值和 `xhigh`，并保留原始 `tool_input` 的其他字段。
- 拒绝缺少必要证明、非法阶段、非法字段、全历史继承或不受支持的 Agent 类型。
- 对没有 marker 的 spawn 保持完全透传，标准输出为空、退出码为 0。
- 生成不含完整 message、prompt 或其他敏感内容的 `MAD_ROUTE_RECEIPT`，作为可观察的派发凭证。
- 通过用户级 `hooks.json` 只注册一个同步 `PreToolUse` hook，matcher 仅覆盖本轮三个派发工具名。

### 1.2 非目标

- 不自动切换已经运行的主会话模型；启动时不能证明主控模型符合要求时，Skill 必须披露限制并在正确配置的新任务中继续。
- 不实现自定义 Agent TOML、插件安装器、模型发现、成本估算或任何新的 Agent 类型体系。
- 不读 transcript、不保存 prompt/message、不落日志、不调用网络或外部服务。
- 不改变非 spawn 工具，不给旧式 schema 盲加字段，不改变现有业务状态、事件、权限或持久化语义。
- 不以 hook 替代独立审计；缺 receipt、路由不符或出现 `xhigh` 的结果不得放行。

## 2. 故障证据抽象

此前问题抽象为三个可观察故障面：

1. **配置漂移**：顶层推理强度或子 Agent 默认值无法证明与职责要求一致。
2. **派发覆盖**：调用者遗漏或错误设置 `model`/`reasoning_effort`，或者通过 `agent_type`、fork 继承选项绕过约束。
3. **审计缺口**：合法派发没有稳定、脱敏的路由凭证；非法 marker 不能在创建 Agent 前同步拒绝。

硬门禁只解决可在 `PreToolUse` 输入中证明的部分：解析 marker、计算真值表、校正已识别字段、拒绝危险继承和返回 receipt。它不声称证明下游平台一定采用了更新后的路由，也不声称能观察已经运行的 Agent。

## 3. 范围与唯一写入边界

本轮唯一写入者只允许修改下列文件：

- `docs/model-routing-hard-gate-development.md`（本文，先于实现冻结）。
- `hooks/pre_spawn_route_guard.py`（标准库纯函数与薄 CLI）。
- `tests/test_pre_spawn_route_guard.py`（标准库 `unittest`）。
- `SKILL.md`、`references/adaptive-four-role-workflow.md`、`README.md`（同步工作流、失败回流和启用说明）。
- `agents/openai.yaml` 的 `interface.default_prompt`（最小提示更新）。
- 用户级配置的既有顶层 `model_reasoning_effort`、删除上一版 `[agents]` 默认块和 `[features].hooks` 三处约定变更。
- 用户级 `hooks.json`（仅一个同步 `PreToolUse` 注册，使用官方 HooksFile 根结构）。

不得修改其他文件、依赖、Agent 配置、插件或安装产物；不得提交、暂存或推送。

## 4. Marker 契约

### 4.1 位置和语法

Marker 必须位于派发输入 `tool_input.message` 的第一条非空行，形如：

```text
MAD_ROUTE_V1 {"role":"execute","complexity_gate":"ESCALATE_REQUIRED","stage":"CONTRACT_FROZEN","task_id":"task-001","contract_rev":"v1.3.1-route-guard"}
```

`MAD_ROUTE_V1` 后必须是同一行的 JSON object。JSON 后可有空白；后续 message 行仍属于原始输入并必须原样保留。marker object 只接受以下字段，未知字段、缺字段、错误类型、空字符串、控制字符或超过 128 个字符的短字符串均拒绝：

| 字段 | 合法值 |
| --- | --- |
| `role` | `think`、`execute`、`audit` |
| `complexity_gate` | `SIMPLE_PROVEN`、`ESCALATE_REQUIRED` |
| `stage` | `PRE_CONTRACT`、`CONTRACT_FROZEN`、`VERSION_FROZEN` |
| `task_id` | `[A-Za-z0-9][A-Za-z0-9._-]{0,127}` |
| `contract_rev` | 必须精确等于 `v1.3.1-route-guard` |

外层 `tool_use_id` 也必须匹配同一 ASCII 安全 ID；禁止路径分隔符、空白、控制字符、空值和超长值。标记调用缺失或不匹配时 deny。

角色和阶段必须成对：`think` 只能是 `PRE_CONTRACT`，`execute` 只能是 `CONTRACT_FROZEN`，`audit` 只能是 `VERSION_FROZEN`。`think + SIMPLE_PROVEN` 永远非法。

没有 marker（包括 message 缺失、空白或第一非空行不是 `MAD_ROUTE_V1`）的 spawn 不进入路由逻辑：stdout 必须为空，退出码为 0，输入不得被修改。

### 4.2 路由真值表

| role | complexity_gate | 合法阶段 | model | reasoning_effort |
| --- | --- | --- | --- | --- |
| `think` | `ESCALATE_REQUIRED` | `PRE_CONTRACT` | `gpt-5.6-sol` | `max` |
| `think` | `SIMPLE_PROVEN` | — | 非法 | — |
| `execute` | `SIMPLE_PROVEN` | `CONTRACT_FROZEN` | `gpt-5.6-luna` | `high` |
| `execute` | `ESCALATE_REQUIRED` | `CONTRACT_FROZEN` | `gpt-5.6-luna` | `max` |
| `audit` | `SIMPLE_PROVEN` | `VERSION_FROZEN` | `gpt-5.6-luna` | `high` |
| `audit` | `ESCALATE_REQUIRED` | `VERSION_FROZEN` | `gpt-5.6-luna` | `max` |

任意合法 marker 都按本表覆盖 `model` 和 `reasoning_effort`；输入遗漏、错误或 `xhigh` 都不能保留。所有其他字段保持不变。

### 4.3 task_name、agent_type 与 fork

- 若输入 schema 有 `task_name`，它必须已经匹配 `madv1_<role>_<simple|escalate>_<slug>`；`role`、gate 前缀必须与 marker 一致，slug 至少一个字符且只含小写 ASCII 字母、数字、`_` 或 `-`，不得自动改写任意名称。正确名称原样保留；没有 `task_name` 的旧式 schema 不新增该字段。若 task name 以 `madv1_` 开头但 marker 缺失或错误，拒绝；普通未标记且非 `madv1_` task name 继续完全透传。
- `agent_type` 只允许缺失或本轮内置的 `worker`、`explorer`、`default`；守卫不解释、不展开自定义 Agent 配置，也不允许它覆盖真值表路由。其他值拒绝。
- 显式 `fork_turns=all`、正整数、正整数字符串或其他值代表不受控继承，拒绝。带 `task_name` 的当前 schema 在字段缺失时补入 `fork_turns=none`，`none` 保留；没有 `task_name` 时不盲加 `fork_turns`，但已存在的值仍按同一安全规则检查。
- 旧式 `fork_context` 只在字段已经存在时识别：必须是布尔值，`false` 保留，显式 `true` 拒绝；缺失时不新增字段。
- `fork_turns` 与 `fork_context` 同时出现属于混合 schema，必须同步拒绝，不输出或拼接混合字段；调用者应选择当前 schema 或旧式 schema 后重新派发。

## 5. Hook 输入、输出与错误码

### 5.1 输入

同步命令从 stdin 读取一个 JSON object。标准字段为 `tool_name`、外层 `tool_use_id` 和 `tool_input`；`tool_input` 必须是 object，且 marker 载体为其中的 `message`。只处理 `Agent`、`spawn_agent`、`multi_agent_v1__spawn_agent`；其他工具直接 stdout 为空、退出 0。未标记的普通 spawn 仍 stdout 为空、退出 0；只有带 marker 或带 `madv1_` task name 的调用才要求安全 `tool_use_id`。JSON 无法解析、顶层不是 object、缺少可识别 tool name 或目标工具缺少 object `tool_input` 时，stdout 必须为空，stderr 写 `MAD_ROUTE_ERROR MAD_ROUTE_INPUT_INVALID`，退出码 2 fail-closed。

### 5.2 允许结果

合法 marker 返回 JSON：

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "additionalContext": "MAD_ROUTE_RECEIPT {…}",
    "updatedInput": {"…": "原 tool_input 字段及最小路由修正"}
  }
}
```

`updatedInput` 是原 `tool_input` 的副本，仅可改变真值表路由和缺失的 `fork_turns=none`；正确 `task_name` 原样保留。receipt 位于 `hookSpecificOutput.additionalContext`，必须包含外层 `tool_use_id`、固定 `policy_rev=v1.3.1-route-guard`、role/gate/stage/task_id/tool_name、`requested_model`、`requested_reasoning_effort`、`enforced_model`、`enforced_reasoning_effort` 和 `corrected`。requested 字段只允许安全分类：model 为 `luna`、`sol`、`omitted`、`other`、`invalid_type`，effort 为 `high`、`max`、`xhigh`、`omitted`、`other`、`invalid_type`；不得回显任意错误值、完整 message、prompt、路径、token 或 payload。

### 5.3 拒绝结果

合法 JSON 输入但 marker 或字段不合法时，返回同一标准 envelope，`permissionDecision` 为 `deny`，`updatedInput` 缺失，reason 为 `MAD_ROUTE_ERROR <稳定错误码>`。合法结构内的路由错误退出码为 0。错误码至少包括：

- `MAD_ROUTE_INPUT_INVALID`
- `MAD_ROUTE_MARKER_INVALID`
- `MAD_ROUTE_JSON_INVALID`
- `MAD_ROUTE_FIELDS_INVALID`
- `MAD_ROUTE_STAGE_INVALID`
- `MAD_ROUTE_GATE_INVALID`
- `MAD_ROUTE_AGENT_TYPE_UNSUPPORTED`
- `MAD_ROUTE_FORK_INHERIT_FORBIDDEN`
- `MAD_ROUTE_FORK_CONTEXT_FORBIDDEN`
- `MAD_ROUTE_TOOL_USE_ID_INVALID`

非法 stdin、协议结构错误或未捕获内部异常不得向 stdout 写 JSON：分别在 stderr 写 `MAD_ROUTE_ERROR MAD_ROUTE_INPUT_INVALID` 或 `MAD_ROUTE_ERROR MAD_ROUTE_GUARD_FAILURE`，退出码 2；不回显 stdin、异常文本或路径。任何拒绝都不得创建 Agent；`additionalContext` 缺少 receipt 的 allow 不得进入 `ACCEPTED`。

## 6. 配置迁移与启用

配置迁移只做以下最小变化：

1. 顶层 `model` 保持 `gpt-5.6-luna`。
2. 顶层 `model_reasoning_effort` 从 `xhigh` 改为 `high`。
3. 不新增全局 `[agents]` 默认子 Agent 块，以兼容桌面内置 Codex 与 PATH CLI 两个版本；省略参数时由 Luna High 主控继承只作兜底，本 Skill 仍必须显式参数、marker 和 receipt，复杂主控下遗漏不能放行。
4. 在既有 `[features]` 新增 `hooks = true`，不改变其他 feature。
5. 新建用户级 `hooks.json`，根对象为官方 `{ "hooks": { "PreToolUse": [...] } }`，只注册一个同步 `PreToolUse` command；handler 必须有 `command`，并提供 `commandWindows` 的安全引号绝对路径。matcher 精确覆盖 `Agent|spawn_agent|multi_agent_v1__spawn_agent`；Windows 使用当前 Python 3.12，非 Windows command 可用 `python3`。

Hook 需要重启 Codex 才能加载；用户必须通过 `/hooks` 审阅并信任该 hook。未信任或未重启时，硬门禁不生效，工作流必须按 fail-closed 处理，不得把“配置文件存在”当作已启用。

## 7. 失败回流

- 缺 marker/receipt、实际路由不符、任何 `xhigh` 或 hook 未启用：结果不得放行，记录为门禁失败并重新派发。
- 标记 JSON/字段/阶段/继承非法：保持同步 deny，不创建 Agent；修正原始派发输入后重新走同一 hook。
- 若错误 Agent 已启动：立即停止或取消其后续写入，确认状态为 `inactive`、`completed` 或 `failed` 且无进行中写入，记录 `WRITER_STATUS` 与停止证据；再按正确 marker、模型、推理强度和非继承 fork 重新派发。不能以口头声明或额度耗尽代替停止证据。
- 若只缺测试证据而代码未变，补证后由独立审计复核同一版本；若需要改变契约、权限、外部副作用或文件范围，回到契约回流并重新冻结。

## 8. 测试矩阵

测试使用 Python 标准库 `unittest`，执行命令带 `-B`，不产生 `__pycache__`。至少覆盖：

| 类别 | 场景 | 预期 |
| --- | --- | --- |
| 透传 | 无 marker、空 message、其他 tool name | stdout 空、退出 0、无输入修改 |
| 合法路由 | think escalate；execute simple/escalate；audit simple/escalate | allow、receipt、真值表 model/effort |
| 修正 | model/effort 遗漏、错误、`xhigh` | updatedInput 只改必要字段；receipt 分类 requested/enforced/corrected |
| 幂等 | 已正确设置的合法输入重复运行 | 输出路由与 receipt 稳定，输入语义不漂移 |
| 工具名 | Agent、spawn_agent、multi_agent_v1__spawn_agent | 三者同一门禁语义 |
| marker | JSON 失败、未知字段、缺字段、错误类型、超长字符串、旧 contract_rev | deny、稳定错误码、不回显 message |
| 语义 | role/gate/stage 不匹配，think simple | deny |
| schema | task_name 前缀/role/gate/slug mismatch、madv1 task 缺 marker；fork_turns all/正整数/字符串正整数/非法；fork_context true/非法；fork_turns+fork_context 混合；内置 agent_type/自定义值 | 按契约 allow 修正或 deny |
| 安全 | 非法/缺失 tool_use_id、task_id 路径/控制字符/超长；非法 stdin、非 object、缺 tool_input、内部异常、receipt 脱敏 | fail-closed；stdout 空、stderr 稳定错误；receipt 不含完整 message/prompt/错误模型 |
| 集成 | hook JSON、TOML、仓库外 quick_validate、app-server `hooks/list`、diff whitespace | 解析通过、命令退出 0；hooks/list 只证明发现 |

## 9. 验收与已知限制

验收必须同时满足：

1. 开发文档先于实现落盘并记录 SHA256；实现差异只在本节范围。
2. 所有合法路由、拒绝路径、透传路径和 schema 兼容测试通过。
3. `python -B` 标准库单测、JSON/TOML 解析和 `git diff --check` 均退出 0；quick_validate 必须用可复现的仓库外绝对脚本解析调用，例如 PowerShell：`$q=(Resolve-Path (Join-Path $env:USERPROFILE '.codex\skills\.system\skill-creator\scripts\quick_validate.py')).Path; $s=(Resolve-Path '.').Path; python -B $q $s`；无新增 `__pycache__`。
4. `hooks.json` 使用官方根结构且只有一个同步 PreToolUse 注册，handler 同时有 command/commandWindows，matcher 无法覆盖非目标工具；配置其他值不变且无全局 `[agents]` 默认块。
5. Receipt 位于 `additionalContext`，绑定安全 tool_use_id，包含固定 policy_rev、requested/enforced 分类与 corrected；缺 receipt 不得 ACCEPTED，且 receipt/error reason 不含完整 message、prompt、路径、凭据或签名数据。
6. `app-server hooks/list` 只能证明用户 hook 被发现；`trustStatus=untrusted` 表示尚未激活，不能计入代码验收。fresh-session receipt 只有在用户重启并通过 `/hooks` 信任后才能验证；当前未信任状态不得伪造为已激活。
7. 交付报告提供开发文档哈希、变更清单、命令/退出码、未验证项和审计所需的固定版本证据；不提交、不暂存、不推送。

已知限制：

- Hook 能强制修改传给工具的输入，但不能证明运行时、远端 worker 或已经启动的 Agent 实际执行了目标模型。
- 用户未重启或未在 `/hooks` 信任该 hook 时，运行时可能不执行门禁；此时只能按未启用处理。
- `hooks/list` 返回 `trustStatus=untrusted` 时只代表发现配置，不代表 hook 已激活；fresh-session receipt 仍需重启并完成信任后验证。
- 平台未来若改动 hook 输入/输出 schema，必须先更新本契约和测试；守卫不会猜测未知 schema 或自动扩展 Agent 类型。
- receipt 是派发时的脱敏凭证，不是完整审计日志，也不保存 prompt/message。
