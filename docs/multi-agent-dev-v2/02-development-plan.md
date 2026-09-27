# multi-agent-dev V2.0：正式开发计划

状态：开发前计划，等待用户验收  
计划版本：V2.0-DRAFT  
输入基线：[需求与架构决策](01-requirements-and-architecture.md)  
迁移基线：[V1 保留与迁移映射](04-v1-preservation-map.md)  
测试基线：[验证与独立审计计划](03-verification-and-audit-plan.md)

## 1. 任务目标

在不覆盖 V1 的条件下，新增可独立安装、使用和审计的 Codex Skill：multi-agent-dev-v2。该 Skill 用固定职责路由为主、Hook 纠错为可选增强，支持 Hook 不可用时按已验证能力降级，并保留 V1 中用户确认过的范围控制、持续纠偏、独立审计、context-lean 条件伴随和 ServerChan 终态通知。

## 2. 范围

### 2.1 本次允许交付

- 新 V2 Skill 的入口指引、职责/分流规则及按需加载的详细参考。
- 新 V2 使用的自定义 Agent profile 配置模板；安装说明区分用户级与项目级目录，不覆盖同名用户配置。
- V2 可选 PreToolUse Hook、示例注册配置、确定性单测，以及 Hook 不可用的路由降级说明。
- V2 需要的终态通知脚本、条件上下文伴随说明和安装/升级说明。已有 V1 脚本只有经过来源与行为核对后才能复制；需记录来源、保持语义的理由和回归测试。
- 用户验收所需的变更清单、测试结果、路由能力状态、独立审计证据及未验证项。

### 2.2 明确不在本次范围

- 修改或清理 V1 当前已存在的文件及未提交差异。
- 无用户要求时修改全局 Codex 配置、信任 Hook、复制 profile 到用户目录或更改当前会话模型。
- 更改 ServerChan 凭据、远端仓库、GitHub、提交/推送、部署、项目业务代码或项目 AGENTS.md。
- 声称 Hook 能覆盖所有派发工具、声称配置文件等于运行时证明，或添加无法在目标工具面观察的机器收据。
- 承诺具体 Token 节省百分比或零偏航。

## 3. 开发写入边界

### 3.1 预期新建范围

- docs/multi-agent-dev-v2/：本开发前文档组。
- skills/multi-agent-dev-v2/SKILL.md：短入口规则、触发边界及支持文件路由。
- skills/multi-agent-dev-v2/agents/openai.yaml：Skill UI 元数据；不得与 Codex 子 Agent TOML 混淆。
- skills/multi-agent-dev-v2/references/：角色与路由表、执行/审计协议、降级与恢复细则。
- skills/multi-agent-dev-v2/profiles/：独立 TOML 模板，每个模板固定一个角色档位。模板不自动等于已安装或已生效配置。
- skills/multi-agent-dev-v2/hooks/：只有 Hook 能力探针支持时才实现可选守卫与注册示例。
- skills/multi-agent-dev-v2/tests/：守卫纯函数、输入/输出、安全和降级行为测试。
- skills/multi-agent-dev-v2/scripts/：仅放经验证且 V2 独立安装时确实需要的通知或配置辅助脚本。

实现开始时必须检查 git status，并把已有修改当作用户基线。本计划执行者拥有新 V2 文件的唯一写入权；若不可避免要改 V1、仓库根说明或用户级配置，须先列出确切目标与原因，更新范围契约并取得用户决定。

### 3.2 允许的外部官方事实来源

- Codex Hooks 官方说明：https://learn.chatgpt.com/docs/hooks
- Codex Subagents 官方说明：https://learn.chatgpt.com/docs/agent-configuration/subagents

开发时重新核对官方页面、当前配置 schema 和本机工具接口；本文的官方资料核对时间为 2026-09-26。动态平台行为以实际安装版本为准，不复制旧版本推测。

## 4. 契约与数据记录

新路由契约使用版本化、短小、脱敏的 MAD_ROUTE_V2 marker；marker 仅承载派发身份、职责、D/I/A 档位、阶段、profile ID、task ID 和 contract revision。不得在 marker、Hook 收据、测试 snapshot 或通知中放入完整任务 prompt、密钥、个人路径或敏感 payload。V2 须建立单一字段表和合法组合表；若当前平台输入 schema 不包含某字段，Hook 不得猜测或盲目新增，须按已验证的 profile/explicit 路由继续或记录不可用。

固定阶段关系：

- 思考派发：PRE_CONTRACT；思考结果只解决已登记歧义。
- 执行派发：CONTRACT_FROZEN；输入含允许修改范围、唯一写入者和验收方法。
- 审计派发：VERSION_FROZEN；输入绑定待审版本与证据，审计员无写权限。

Hook 收据只表示接收到并处理了派发输入。可得的子会话运行元数据另行保存为 provenance，并独立记录来源、字段、Codex 版本和取证步骤；缺少该信息时明确记录 ROUTE_UNVERIFIED。不要把 transcript 格式当稳定 API。

## 5. 实施阶段和 Exit Gate

### Phase 0：文档冻结与运行能力摸底

工作：

1. 用户验收本文件、需求/架构决策、V1 保留与迁移映射、测试/审计计划；四份内容共同冻结实施范围与验收口径。
2. 建立 V1 新鲜基线并检查所有现存改动；只读核对 V1 中要保留的规则和可复用脚本。
3. 按 04-v1-preservation-map.md 建立逐项映射，记录 V1 来源规则/文件、V2 落点、现有测试/运行证据和 V2 回归场景。
4. 在当前 Codex 新鲜会话中分别探测：自定义 profile 可选性、profile 路由实际值、显式 model/effort 路由实际值、Hook 改写、Hook 拒绝、实际 provenance 可见性。
5. 为 provenance 建立来源登记表，记录确实能读取的接口/界面和字段。优先确认是否能取得实际 model 与 reasoning effort；不假定派发工具返回或 transcript 包含这些信息。

Exit Gate：

- 文档互相一致，需求有唯一验收口径。
- 用户已验收 V1 保留映射；映射和 provenance 来源登记表已填，没有可用来源的字段明确标为 UNKNOWN。
- 能力表逐项记录版本、输入、观察结果和局限；未证实能力标为 UNKNOWN。
- 不修改 V1 或用户配置。

### Phase 1：V2 Skill 骨架与固定路由档

工作：

1. 创建独立 V2 package 和短入口。
2. 把 D/I/A 分流、职责、路由真值表、唯一写入者、范围冻结、纠偏与审计放入按需参考文档。
3. 加入角色配置模板，但仅为已验证支持的模型档生成；profile 安装说明不能覆盖已存在同名文件。
4. 从 V1 复用必须的通知与 context-lean 交互时，记录来源路径、行为不变点和独立回归方法。

Exit Gate：

- V2 可被单独识别/安装；技能入口说明准确且不误触普通编码请求。
- 每个角色和模型档位都有职责、边界、升级触发和明确不适用情形。
- 文档、profile 和任何默认值一致；think 使用 gpt-6-sol/xhigh，执行/审计只使用路由矩阵中的 gpt-6-luna 档位。

### Phase 2：Hook 可选守卫与派发路由实现

工作：

1. 只对 Phase 0 已实测支持的派发工具注册同步 PreToolUse。
2. Hook 对可机器判定的职责/阶段/profile/fork/model/effort 错误按架构文档执行最小修正或拒绝。
3. 其他工具和未标记的普通派发按约定透传；不能依赖宽泛的 exec 文本扫描做语义拦截。
4. 如果目标工具面无法支持 Hook，则保留对应提示为未启用，继续实现 Profile/显式参数降级；不把 Hook 缺失处理成整个 Skill 失效。

Exit Gate：

- 纯函数测试覆盖合法、纠正、拒绝、脱敏、幂等和透传。
- 运行时错误参数探针和非法 marker 探针只对确认可用的 Hook 模式判定。
- Hook 不可用时，至少一个经实际 provenance 验证的 Profile 或显式路由路径仍可工作；否则记录 ROUTE_UNVERIFIED 并明确受限行为。

### Phase 3：纠偏、审计、通知与上下文交接

工作：

1. 实现需求原文、基线、符号/变量约束和实际 diff 的证据表模板。
2. 固定“拒收 → 范围内修正/补证 → 固定版本 → 重跑受影响检查 → 独立复审”回流。
3. 保留静默交付模式、用户明确要求监测时的可观察报告，以及任务终态通知。
4. 检查中断、阻断、旧写入者未停止、通知失败和 Hook 不可用路径。

Exit Gate：

- 审计员不能写被审对象或修改验收标准。
- 通知只在终态发送，含真实验证结果，不把机器 marker 回显到主会话。
- 长任务 context-lean 仍是条件伴随；短任务不额外触发压缩/检查点流程。

### Phase 4：集成、独立审计和用户交付

工作：

1. 运行文档验证、所有 V2 定向测试和必要新鲜会话探针。
2. 冻结 V2 文件版本，由未参与 V2 文档/实现写入的只读审计员逐条对照本文档组。
3. 处理审计发现；每次修订重新固定版本，复核受影响项。
4. 报告 V1 基线未被修改、V2 支持能力矩阵、实际测试和已知限制，等待用户验收。

Exit Gate：

- 03-verification-and-audit-plan.md 的必需项通过。
- 无必需项为不符合或证据不足。
- 未经用户后续明确要求，不提交、推送、合并、安装全局配置或更改用户级 Hook/profile。

## 6. 路由与配置安装策略

Skill 路由表是规范来源；自定义 Agent TOML 是可选配置副本。若 Codex 实际选用 TOML 中的模型/强度，而非 spawn 参数，则记录实际生效优先级，更新 profile 和验证用例。

Profile 模板分用户级与项目级示例。默认只提供可审阅文件，不自动写入用户 agents 目录或项目 .codex/agents。用户安装、信任或修改配置由用户明确操作；后续若要自动安装器，必须另行冻结覆盖冲突、备份、回滚和 dry-run 契约。

Hook 示例不得默认为已受信任。启用须由用户在 Codex 支持的界面审阅并信任；升级脚本不得规避该信任步骤。

V1 和 V2 的 marker、task 名空间与 Hook 处理范围必须隔离。V2 Hook 只识别 V2 contract；V1 Hook 对 V2 调用保持透传，V2 Hook 对 V1 调用保持透传。若同一配置层加载多个匹配 Hook，必须检查多 Hook 合并及拒绝优先行为；不得靠修改或删除 V1 注册来掩盖冲突。

## 7. 风险及应对

| 风险 | 影响 | 设计应对 |
| --- | --- | --- |
| 专用派发工具绕过 Hook | 纠错门禁未运行 | 启动期反事实探针；自动降级到实测 Profile/显式路线 |
| 自定义 profile 名不可调用 | 角色配置不能用于当前工具面 | 保留内置 Agent + 显式参数路径；不得假称 TOML 生效 |
| 只看 Hook 收据 | 错误宣称实际模型已采用 | 独立检查子会话 runtime provenance；收据与 provenance 分开 |
| Luna low 处理含糊任务 | 漏需求、局部臆断 | I0 严格准入；未满足条件升至常规档或先由思考 Agent 定界 |
| Hook 过度捕获普通工具 | 破坏其他 Skill/工作流 | 命名空间与输入标记定向；普通工具透传测试 |
| 审计范围膨胀 | Token 和等待增加 | 按风险 A0/A1/A2 选档，测试只覆盖受影响路径和必要回归 |
| 指标样本太少 | 误判质量或节省效果 | 先报告样本及限制，不作统计结论；持续累积代表性任务 |
| V1 修改与 V2 开发冲突 | 覆盖用户未提交改动 | V2 新目录；开始时重查工作树；禁止清理或覆盖 V1 |

## 8. 版本与发布边界

V2 首轮只交付本地可审阅包和验证报告。用户验收前不替换 V1 安装、不改变默认 Skill 选择、不推送或合并。用户验收后如要发布，再按明确授权处理版本号、仓库更新、安装和升级文档。
