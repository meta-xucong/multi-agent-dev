# multi-agent-dev V2.1：开发文档独立审计报告

状态：最终独立只读复审完成，文档门禁 PASS_FOR_CODE_START；历史 HOLD/REJECT 段落保留为审计轨迹
审计对象：docs/multi-agent-dev-v2/01–10、INDEX.md。D11 是输出报告，05 是追加式证据日志，不计入本次输入 target hashes。
审计范围：代码实施前的目标、职责、契约、并发、模型/effort、验证和实施可执行性
不包含：V2 代码功能验收、真实 Hook/Profile 运行、实际 model/effort provenance、提交、推送或部署

## 1. 结论摘要

本报告记录文档集的审计输入、检查方法、修正历史和最终放行条件。

当前主会话静态复核结论：初始发现的 P1/P2 文档问题已经完成最小修正；逐文档交叉检查未发现新的 P0/P1/P2。独立审计人已返回正式 MAD_DOC_AUDIT_RECEIPT，但其只读环境无法定位本设备上的文档，因此不能验证修正内容。

在独立 receipt 未返回前：

- 文档实施状态：HOLD_FOR_CODE_START。
- V2 代码：未因本轮文档工作修改。
- V1 文件及既有用户修改：未覆盖、回滚或整理。
- V2 package manifest：仍为 a38d2272226649e9a0c28d860a6f6e38b1cfd63ec568e26a66c2c040e8e30488。
- Hook、Profile、真实 model/effort provenance 和前向工作流：继续未验证。
- 不得开始 Phase 0 代码，不得标记 ACCEPTED。

只有独立 receipt 能读取本设备的固定文档并确认没有未关闭 P0/P1/P2 后，本文件才可更新为 PASS_FOR_CODE_START；该状态只允许开始代码，不代表 V2 功能验收。

## 2. 审计版本和环境快照

审计设备：LAPTOP-HJGDTB1M
device id：ff983560-d3ad-46a7-ae72-881a12496d57
工作根目录：C:\Users\T14S\.codex\skills\multi-agent-dev
目标文档目录：docs/multi-agent-dev-v2
目标 contract_rev：v2.1.0-controlled-parallel
V2 package 文件数：25（排除任意 __pycache__ 文件）
V2 package manifest hash：a38d2272226649e9a0c28d860a6f6e38b1cfd63ec568e26a66c2c040e8e30488

manifest 复算算法：

1. 递归列出 skills/multi-agent-dev-v2 下文件，排除路径组件为 __pycache__ 的文件。
2. 将相对路径规范化为 POSIX 分隔符，并以相对路径的大小写不敏感排序键排序。
3. 每行生成 <relative-path> <sha256(file bytes)>。
4. 用两个字面字符反斜杠和 n 连接各行，并在末尾追加同样的分隔符。
5. 对所得 UTF-8 字节再次计算 SHA-256。

本次文档 hash 使用 SHA-256(file bytes)，行数由远程 PowerShell Get-Content 计数；任何后续文档修改都会使对应 receipt 失效，需重新记录。

## 3. 已执行的静态检查

- D01–D10 和 INDEX 文件存在且可读。
- 文件行数、SHA-256、目标目录和 V2 package hash 已记录。
- 读取 D01–D10 的职责、D/I/A、状态、枚举、模型/effort、Hook/Profile 边界和验证条件。
- 逐项比对 06、07、08、09、10 的字段、状态、reason code、测试 ID、phase 和退出门。
- 检查 INDEX 阅读顺序和所有文档路径。
- 检查 git status：V1 既有六个修改保留；docs/ 与 V2 package 为未跟踪内容；未执行 reset、清理、提交或推送。
- 执行 git diff --check：退出码 0；只有既有 V1 文件的 LF/CRLF 转换提示。
- 独立复算 V2 package 数量和 manifest hash。
- 检查文档没有把模拟测试、配置文件、Agent 自述或任务名当作 runtime provenance。

## 4. 初始 findings 与修正

### FIND-001：D11 报告路径不存在

严重性：P1
位置：INDEX、D09、D10
问题：INDEX 和 Phase 0 需要审计报告，但报告文件尚未创建。
修正：创建本文件，并在最终 receipt 返回后固定报告结论、hash 和审计证据。
状态：本报告创建后关闭路径缺口；最终 receipt 仍是前置条件。

### FIND-002：路由和 Hook 状态枚举大小写不一致

严重性：P1
位置：D07 ScopeManifest；D01、D06、D08、D09 的 runtime 状态
问题：D07 的 route_status/hook_status 使用小写值，其他文档使用大写 canonical 值。
修正：D07 统一为 route_status=VERIFIED/UNVERIFIED/MISMATCH、hook_status=ENFORCED/UNAVAILABLE/UNVERIFIED。
状态：已修，待独立复审确认。

### FIND-003：Run、Task 和 Handoff 状态边界不明确

严重性：P1
位置：D06、D07、D08
问题：HANDOFF_READY、EVIDENCE_COLLECTION、AUDIT_HOLD 和 Task ACCEPTED 的关系可能让实现者误用状态。
修正：D07 改为引用 D06 canonical Run flow 与 Task flow，并明确 HANDOFF_READY 只是 evidence condition；SUCCEEDED 只表示 Handoff 完成，不表示 Task ACCEPTED 或 Run 完成。
状态：已修，待独立复审确认。

### FIND-004：HandoffPacket 的 audit_receipt 字段不一致

严重性：P1
位置：D06 §11、D07 §6
问题：D06 将 audit_receipt 列入 handoff，而 D07 必填字段未列出。
修正：D07 加入 audit_receipt；首次 handoff 允许 null，进入 AUDIT_PENDING 后必须绑定固定版本的 AuditReceipt；D06 同步说明。
状态：已修，待独立复审确认。

### FIND-005：D/I 并发条件措辞冲突

严重性：P1/P2
位置：D06、D10
问题：D06 允许 I0/I1 的 disjoint 叶子并发，D10 原矩阵写成只有 I 高才能拆分并发。
修正：D10 改为 I 越高越需要拆解；I0/I1 只有在 disjoint 且无共享状态时允许并发。
状态：已修，待独立复审确认。

### FIND-006：新增并发工作流数量错误

严重性：P2
位置：D08 §9/§10
问题：清单包含五个新增并发/恢复工作流，正文曾写成四个。
修正：统一为新增五个并发/恢复工作流。
状态：已修，待独立复审确认。

## 5. 当前跨文档结论

待独立 receipt 的最终复核项：

| 主题 | 当前判断 |
| --- | --- |
| 主会话与 Controller | 一个意图/授权权威、一个状态/调度权威，无两个平权主控 |
| worker 与 writer | TaskSpec、write_set、namespace lease、隔离 worktree 和单 integrator |
| Guard 与 Audit | Guard 只能 ALLOW/WARN/BLOCK/NEEDS_USER_DECISION；Audit 独立只读 |
| D/I/A | D 高先冻结；I0/I1 仅无共享状态时可并发；A 高增加 Guard/Audit |
| model/effort | Main Luna/high；Think Sol/xhigh；Execute I0–I3 Luna low/high/xhigh/max；Test Luna/high；Semantic Guard/Audit A0–A2 Luna high/xhigh/max；状态机/通知器无 LLM |
| provenance | requested 与 runtime 分开；缺 runtime 字段为 ROUTE_UNVERIFIED，实际不符为 ROUTE_MISMATCH |
| Hook/Profile | ENFORCED/UNAVAILABLE/UNVERIFIED 与路由状态分开；配置或模拟 payload 不等于运行时通过 |
| 状态 | Run、Task、Handoff 的 canonical flow 和旁路状态已在 D06/D07 对齐 |
| 证据 | manifest、revision、diff/artifact hash、测试 receipt、Guard/Audit receipt 和限制齐全 |
| V1 保护 | 既有 V1 修改保留，V2 只在独立目录实施 |
| 实施顺序 | Phase 0 冻结→schema→状态/lease→Guard/Audit→worker adapter→整合→运行时探针 |

## 6. 独立 receipt 待填格式

以下字段由未参与本文档写入的独立只读审计人填写：

audit_id：
auditor_actor：
target_docs：
target_doc_hashes：
target_contract_rev：v2.1.0-controlled-parallel
v2_package_manifest_hash：
git_status_snapshot：
checks_run：
findings：
cross_document_result：
implementation_readiness：
runtime_provenance_status：
requested_model_effort：
actual_model_effort_provenance：
limitations：
decision：

decision 必须为 PASS_FOR_CODE_START、HOLD_FOR_CODE_START 或 REJECT_FOR_CODE_START。没有实际 model/effort provenance 时写 ROUTE_UNVERIFIED；这不等于运行时通过。

## 7. 代码开始门

独立 receipt 只有在以下条件全部满足时才能写 PASS_FOR_CODE_START：

- D01–D10 和 INDEX 的目标 hash 与审计输入一致；D11/05 的 receipt 追加只作为输出记录，不改变这些输入 hash。
- P0/P1/P2 finding 为零，或有明确的用户接受记录和不影响 Phase 0 的降级项。
- ScopeManifest、TaskSpec、Lease、CAS、Handoff、GuardDecision、AuditReceipt 和 StateEvent 可逐字段映射到 D07。
- D09 每个 phase 都有 owner、目标文件、model/effort、输入、输出和退出门。
- D08 required 测试、恢复测试、十个前向工作流和运行时探针可追踪。
- V1 保护、外部副作用、全局配置和用户授权限制没有歧义。
- 本报告和独立 receipt 追加到 05-implementation-evidence.md。
- ROUTE_UNVERIFIED、HOOK_UNVERIFIED 和未运行工作流仍明确保留，不被写成通过。

## 8. 运行时与功能门禁

即使文档状态为 PASS_FOR_CODE_START，以下仍未自动关闭：

- 真实 Hook matcher、输入、拒绝、更新输入和透传。
- Profile discovery、实际子会话启动和实际 model/effort provenance。
- Controller 的真实 lease、CAS、并发上限、恢复和取消。
- Semantic Guard 与 Independent Audit 的运行时隔离。
- 原 V2 五个前向工作流和本 V2.1 新增五个并发/恢复工作流。
- skill-creator 的 PyYAML validator。
- V2 功能验收和最终 ACCEPTED。

这些项目必须由 08 和 03 规定的真实探针、测试 receipt 和独立审计证据关闭。

## 9. 最终可见 receipt 与主会话静态复核

独立 receipt：MAD-DOC-AUDIT-V2.1-FINAL-20260926-002
独立 receipt 状态：HOLD_FOR_CODE_START / FINAL_INDEPENDENT_REREAD_REQUIRED
独立 receipt 限制：审计 Agent 的只读环境无法定位本设备文档；它搜索了本地工作区、远程设备根目录、C:\cw9ad 和 C:\Users，均返回 zero matches。该 receipt 没有验证修正内容，也没有声明无 P0/P1/P2。
独立审计 requested model/effort provenance：不可见；ROUTE_UNVERIFIED。

主会话静态复核的固定输入（2026-09-26）：

| 文件 | 行数 | SHA-256 |
| --- | ---: | --- |
| 01-requirements-and-architecture.md | 202 | 82a2b0fe19b6c52b889e6d29352017427f44b0ce432ac0939ae5bccfbcddf14c |
| 02-development-plan.md | 169 | 3432952b4f5a118ed6f4b821086e724b364c66fc70c4610efce1ce0a11f8a672 |
| 03-verification-and-audit-plan.md | 149 | 8fdcd23a3f64ae27ed11b356f06858f0aee143fe37ee02ddda6508938fed4a7d |
| 04-v1-preservation-map.md | 79 | 376247c18e9fee6f2df7d374fde21e8c2f9650deb73a9b9c70420efbde8965d7 |
| 05-implementation-evidence.md | 160 | b0e3567e9c10e42094877fea5ab32a5c829bae83b27498030ee31ffb7b5564db |
| 06-controlled-parallel-orchestration-development.md | 265 | 3e0cfad1da48756755a8b5c981be200a9c881b9f5fda5f23b71e68b3590c65e8 |
| 07-v2-parallel-orchestration-contracts.md | 248 | 92e0252f68d0856d49687fe0ce58e37442e264104c2c852935b97b2a02184b1a |
| 08-v2-parallel-orchestration-verification-plan.md | 220 | 42c7ee17014957e4c61b48512ec4b0f7b16e6b405a5b955b1b7663dae40ae4f5 |
| 09-v2-implementation-task-breakdown.md | 215 | c3ae9435bc61ba3c10406bfbaa688893237e29e5cf4b07d42065ce6a9bf75853 |
| 10-v2-document-audit-checklist.md | 204 | ef7a895581145c944678deab16d2d2ad2cc8d40dfe4a19e6a69f9f6b074c55e1 |
| INDEX.md | 32 | cd680755d910f858d7072a520da4df0ce2c5ea3945eb54e875bb3078dd292334 |

主会话检查结论：文件存在、引用路径可读、D07/D08/D09/D10 的已知修正可见；V2 package 25 文件 hash 保持 a38d2272226649e9a0c28d860a6f6e38b1cfd63ec568e26a66c2c040e8e30488；git diff --check 仍为 exit 0（仅既有 V1 LF/CRLF 提示）。主会话检查不是独立审计，不能替代上述 re-read。

当前正式决策：HOLD_FOR_CODE_START。文档内容静态上已达到实施蓝图完整度，但在独立责任人能够读取同一固定版本并签发 PASS_FOR_CODE_START 前，不开始代码 Phase 0。

## 10. R2 独立复审 findings 与本轮修正

独立 receipt：MAD-DOC-AUDIT-V2.1-REREAD-20260926-003
其读取的是固定文档快照，结论为 REJECT_FOR_CODE_START；发现 R01–R13。主会话已按如下方式在远程文档中修正，待第三次独立读取远程最终版本：

| ID | 原问题 | 修正 |
| --- | --- | --- |
| R01 | D07 把 HANDOFF_READY 同时当状态和证据条件 | 移除持久化转换；明示它仅为证据条件，Task 走 WAITING_HANDOFF→AUDIT_PENDING |
| R02 | D06 与 D09 Phase 顺序不同 | D06 改为 D09 的 Phase 0 冻结、1 schema、2 state、3 handoff/Guard/Audit、4 adapter、5 integration、6 runtime |
| R03 | ScopeManifest/task_specs 与 TaskSpec.manifest_hash 自引用 | D07 改为无 hash TaskTemplate 先 hash；随后 Controller 注入运行时 TaskSpec manifest_hash |
| R04 | 并行 Task 共用未定义 revision | D07 增加 run/task/lease 独立 revision；无关 task 不互相拒绝，event_seq 只排序 |
| R05 | CAS 后追加 event 的崩溃窗口 | D07 要求同一持久化事务内更新、event、outbox；失败全回滚、成功后返回 |
| R06 | 初始 handoff 要求尚不存在的 audit_receipt | D07 改为初始 receipt=null；Controller 固定输出后才进入 AUDIT_PENDING，独立审计后附加并接受 |
| R07 | 通用 route/hook enum 与前缀状态不一致 | D07/08 统一 PROFILE_VERIFIED、EXPLICIT_ROUTE_VERIFIED、ROUTE_UNVERIFIED、ROUTE_MISMATCH 与 HOOK_* |
| R08 | 实现作者、Controller、Test、审计 writer 混淆 | D09 改 audit_receipt.py 为 Controller 确定性 schema；Independent Audit 只读签发 receipt |
| R09 | ScopeManifest 缺 hard constraints、sources、read paths、stage、owners、notification | D07 schema 增加这些字段及约束/来源引用 |
| R10 | READY_TO_MERGE 被写成 Task 状态 | D09 改为 Run=READY_TO_MERGE 且 Task=ACCEPTED |
| R11 | CONC-11 使用不存在的 READY Task 状态 | D08 改为 PLANNED |
| R12 | RETRY reason 的 WARN/BLOCK 阈值不一致 | D07 定义第一次 WARN，第二次及以后 BLOCK/NEEDS_USER_DECISION |
| R13 | contract_rev 只在 D07 定义且依赖文档含糊 | D08/D09/D10 显式引用 D07 的唯一定义，未知 revision 拒绝 |

独立复审还指出远程文件的结尾换行差异；主会话保存的是远程原始内容，最终审计 hash 以远程设备实际字节为准，不能用本地快照 hash 冒充。

## 11. 当前门禁

当前不宣称 R2 已独立通过。远程最终版本必须重新计算 D01–D11/INDEX 的文件 hash，并由未参与本轮修正的只读责任人读取该版本，逐项确认 R01–R13 已关闭。若仍有 P0/P1/P2，继续修正和复审；只有正式 receipt=PASS_FOR_CODE_START 才开始 D09 Phase 0。

V2 package manifest 仍为 a38d2272226649e9a0c28d860a6f6e38b1cfd63ec568e26a66c2c040e8e30488；本轮只改 docs，未改 package。

## 12. 最终独立文档审计 receipt（输出记录）

本节的 PASS_FOR_CODE_START supersedes §1、§9–§11 的历史 HOLD/REJECT 状态；那些段落保留用于追溯。

audit_id：MAD-DOC-AUDIT-V2.1-FINAL-SCOPE-20260926-005
auditor_actor：independent-read-only-agent
target_docs：D01–D10、INDEX（D05 为追加式 evidence output，D11 为本报告 output，均不作为自身 target hash）
target_contract_rev：v2.1.0-controlled-parallel
checks：独立只读重读 R2 snapshot；复核 R01–R13、状态、阶段、schema/hash、revision 域、CAS/event 原子性、handoff/audit 顺序、owner 分离、enum、retry、工作流计数和 contract revision 引用。
findings：P0=[]；P1=[]；P2=[]
cross_document_result：CONFORMING
implementation_readiness：CONFORMING
runtime_provenance_status：ROUTE_UNVERIFIED
decision：PASS_FOR_CODE_START

远程权威输入文件的 SHA-256/行数（以设备原始字节为准）：

| 文件 | 行数 | SHA-256 |
| --- | ---: | --- |
| 01-requirements-and-architecture.md | 202 | 82a2b0fe19b6c52b889e6d29352017427f44b0ce432ac0939ae5bccfbcddf14c |
| 02-development-plan.md | 169 | 3432952b4f5a118ed6f4b821086e724b364c66fc70c4610efce1a0a11f8a672 |
| 03-verification-and-audit-plan.md | 149 | 8fdcd23a3f64ae27ed11b356f06858f0aee143fe37ee02ddda6508938fed4a7d |
| 04-v1-preservation-map.md | 79 | 376247c18e9fee6f2df7d374fde21e8c2f9650deb73a9b9c70420efbde8965d7 |
| 06-controlled-parallel-orchestration-development.md | 268 | a7009bbb89153d5c5f4ac3f6ba2c5266371f11ca44b133b45bde445b5110e839 |
| 07-v2-parallel-orchestration-contracts.md | 255 | ab58ac428fc759c094db2279b3cdf2799185010f7a02edf7f961bf3b34cdabaf |
| 08-v2-parallel-orchestration-verification-plan.md | 221 | 7282f28e89545801effb365deebaf0ca6ed667a95615c7af802a13b904e605d8 |
| 09-v2-implementation-task-breakdown.md | 228 | e005c14ee410dc8429ae0a86f695124784d7a99f5135bdba2c95ddd381e37f74 |
| 10-v2-document-audit-checklist.md | 208 | d6307577604737b546863a106e8eb1b74c7628a19ee39301693f3da349c639b8 |
| INDEX.md | 32 | cd680755d910f858d7072a520da4df0ce2c5ea3945eb54e875bb3078dd292334 |

限制：未执行真实 Hook、Profile、model/effort provenance、Controller、workflow 或 package runtime；V2 package hash 仍为 a38d2272226649e9a0c28d860a6f6e38b1cfd63ec568e26a66c2c040e8e30488。

## 13. Superseding final receipt

The previous §12 receipt (audit_id MAD-DOC-AUDIT-V2.1-FINAL-SCOPE-20260926-005) is superseded because INDEX was updated to reflect the final gate. The authoritative final receipt is:

audit_id：MAD-DOC-AUDIT-V2.1-FINAL-20260926-006
auditor_actor：independent-read-only-agent
target_docs：D01–D10、INDEX
excluded_outputs：D05 append-only evidence log；D11 append-only audit report
target_contract_rev：v2.1.0-controlled-parallel
checks：独立只读重读最终 snapshot；R01–R13、schema、state、phase、hash、CAS、handoff、audit、owner、enum、retry、workflow、contract-revision consistency
findings：P0=[]；P1=[]；P2=[]
cross_document_result：CONFORMING
implementation_readiness：CONFORMING
runtime_provenance_status：ROUTE_UNVERIFIED
decision：PASS_FOR_CODE_START

最终 target 输入行数/SHA-256（独立快照的行尾 caveat；远程原始字节以主会话复算为准）：D01 201/b8bcadcdfb5cfb44902b6d746465fffc4cfe963da155d2b8462afcab0aa0df7e；D02 168/d0c907b45b72da27cd0ec7775cd2f68031772c1949ff10610fedc0729285840a；D03 148/39f875e31ed4844d573f3d55264e43ecb5ed9d6a3da1d0f58c9677928829fb13；D04 78/bc1bfbc6e03a669f6596327b8231653ce59cd35dbde407d642a806a3723cfc49；D06 267/4ecad6833bc319387e7521b550a20558899aac1c63b9eeff6ab9f9fc516585ee；D07 254/4c4bd22c9a7213d40a314ea313636f0499ca71d7798e25eaefe80bb622ee6c7b；D08 220/0b5dce4f22f8e0ba5ad790d24a3083a3f79e6b17a4d8af2f110e13ce4f3ff4e3；D09 227/e005c14ee410dc8429ae0a86f695124784d7a99f5135bdba2c95ddd381e37f74；D10 207/dc433a21314b9f612de353f055886aac428b6b2180cbbb03ef6dc2c0b6c251d0；INDEX 31/93d6d712a99a58fb41c04a11ac385e5ffabc0a7c14cb22b283dca2cd7f36335c。
限制：无真实 Hook、Profile、model/effort、Controller 或 workflow execution；package hash 仍 a38d2272226649e9a0c28d860a6f6e38b1cfd63ec568e26a66c2c040e8e30488。

## 12. 后续实现版本的 manifest 规范澄清（2026-09-27）

本报告第 2 节记录的是早期 25 文件设计快照，不是当前 V2.1.6 代码包的验收 hash。为消除“路径文本是否转小写”和分隔符表述歧义，当前实现与测试交接统一采用：

1. 递归列出 package 文件并排除路径组件为 `__pycache__` 的文件。
2. 相对路径统一为 POSIX；仅使用 `relative_path.lower()` 作为排序键，清单行保留原始相对路径文本。
3. 每行写入 `<original-relative-path> <sha256(file-bytes)>` 后追加一个实际 LF 换行；对完整 UTF-8 清单整体计算 SHA-256。
4. 当前 45 文件包的复算值为 `d2c674516fbc3943e8bc04b82aee170697dd4e918eb2c080ee8daec018afb39d`。

该规范 supersede 本报告早期 hash 与旧的分隔符/路径文本表述；测试人员应以 `05-implementation-evidence.md` 与 `12-v2-tester-handoff.md` 的最新段落为准。

## 13. V2.1.7 exit_code 类型门禁修订（2026-09-27）

V2.1.6 之后，EvidenceRecord、StateStore.record_evidence() 与 HandoffPacket 对 `exit_code` 增加严格 `type(...) is int` 校验；成功 handoff 只接受整数 0。`False`、`0.0`、`"0"` 均拒绝。当前 45 文件 package hash 已更新为 `8a3468bb94ddab36cbd41efbcbf377f297b08b3f9adc24d95ebebed2cba48a23`。

该修订不改变 manifest 算法；此前 hash 仅作为历史快照，当前测试目标以 `05-implementation-evidence.md` 与 `12-v2-tester-handoff.md` 最新段落为准。

## 14. V2.1.8 runtime dispatch hardening audit（2026-09-27）

独立只读审计范围：`runtime_dispatch.py`、`orchestrate.py` 的 `runtime-gate`、运行时参考文档及新增定向测试。审计未编辑文件、未提交或推送。

结论：**PASS（代码级范围）**。

- requested model/effort 与 observed model/effort 分离，只有显式 `thread/settings/updated` 才能形成 route provenance；`thread/started` 携带的字段不再绕过设置证据。
- child 绑定要求 `thread/started.parentThreadId` 或带父线程 scope 的 `subAgentActivity`；未带 scope 的普通 activity 不得伪造启动证据。
- child ID 存在时的 spawn failure、冲突 settings、父线程先终态均持续 fail-closed；父线程关闭前必须有 child terminal event。
- `admissible` 同时要求 child lifecycle、terminal、route provenance 和 parent close gate；`runtime-gate` 失败返回 `GATE_HOLD`，不写账本、不调用 Provider。
- 定向测试 **14/14**、V2 全包 **83/83**、`py_compile` 通过；未发现 Provider、网络、全局配置或持久化副作用。

限制：该代码级 PASS 不证明真实 Codex Hook、Profile discovery 或实际子 Agent model/effort provenance；这些仍由真实运行时证据门单独决定。
