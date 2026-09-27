# V2.1 测试专员交接

状态：开发实现待测试专员接手；本文件不表示运行时验收完成。

## 测试对象

- 远程工作目录：C:\\Users\\T14S\\.codex\\skills\\multi-agent-dev
- V2 包：skills/multi-agent-dev-v2
- V2.1 入口：skills/multi-agent-dev-v2/scripts/orchestrate.py
- V2 状态库：调用方指定的私有 SQLite 文件；测试期间使用临时目录
- 既有 V1 修改必须保留，不得 reset、clean、覆盖或提交

## 开发侧已完成

代码包括 ScopeManifest/TaskSpec 约束、controller epoch、CAS/event ledger、原子多 namespace lease、依赖调度、retry budget、Handoff/Guard/Audit、worker 有界执行与脱敏、notification intent、外部副作用 outbox claim/complete/recovery、证据索引和 JSON CLI。

## 可重复命令

在仓库根目录执行：

    python -B -m unittest discover -s skills/multi-agent-dev-v2/tests -p "test_*.py" -q
    python -B -m unittest discover -s skills/multi-agent-dev/tests -p "test_*.py" -q
    python -B -m compileall -q skills/multi-agent-dev-v2
    git diff --check

开发侧最后一次 V2 结果为 51/51，V1 基线为 64/64；测试专员应以实际输出为准，并在证据中记录完整命令、解释器和环境编码。

## 必测范围

1. Windows 临时目录下重复 init/plan/dispatch 的幂等与冲突。
2. 并发 namespace lease、controller epoch、过期 lease 和 stop evidence。
3. 依赖 DAG、总并发上限、retry budget、无新证据二次重试阻断。
4. Handoff 顺序、路径范围、Guard fail-closed、独立 AuditReceipt 绑定。
5. outbox claim/complete、认领超时恢复、失败重放和通知 intent 去重。
6. worker timeout、非 shell 执行、输出脱敏和 external side-effect hold。
7. 真实 Codex Hook/Profile/model-effort/五个工作流探针；若未运行必须保持未验证。

## 结果规则

单测、CLI、SQLite 和 worker 探针只能证明本地实现。Hook、Profile discovery、实际 model/effort provenance 和前向工作流必须有目标 Codex 入口的独立运行证据；缺失时状态保持 ROUTE_UNVERIFIED、HOOK_UNVERIFIED 或 HOLD。不得将配置存在、requested route、Agent 自述或模拟输入写成真实通过。

## 交接输出

请追加到 docs/multi-agent-dev-v2/05-implementation-evidence.md：测试命令和结果、解释器版本、manifest hash、V1 diff 摘要、失败复现、运行时限制、独立审计 receipt（如有）及下一步允许动作。不要安装 Profile、修改或信任全局 Hook、提交、推送或部署。


## 当前固定包

V2 package manifest：44 files；SHA-256 774e6beff9064180ec4860c092667d1e806c5110e29232571f3e199fdbb3b4bd。测试专员开始前应按实施证据中的算法独立复算；若代码、测试或 package 文档再变化，必须重新计算并把旧结果标记为 superseded。


最终固定包 hash：bb4e80a14dcec26428814408e96cc5953cdb01e403ab263241a67f5d741377d1。该值 supersedes 前文的 774e6bef...；测试专员应以此值作为起始复算目标。


最终固定包 hash：bf72e20d9759f4a7a99f26bded0562acdec26d8fb37a071b41266757b3af8302。该值 supersedes 前文的 bb4e80a1...。

## V2.1.1 开发修复后交接修订（2026-09-27）

本轮只修改 skills/multi-agent-dev-v2/ 及追加证据，保留 V1 六个既有修改；未安装 Profile、未修改或信任全局 Hook、未安装 PyYAML、未提交/推送/部署。

实际 CLI 命令名为 dispatch-next；dispatch 不属于当前入口。省略 controller_epoch 时，同一 owner 复用持久化 epoch；需要接管时显式传 takeover=true，接管会递增 epoch 并使旧 worker fencing 失效。

修复后可重复命令（仓库根目录）：

    python -B -m unittest discover -s skills/multi-agent-dev-v2/tests -p "test_*.py" -q
    $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; python -B -m unittest discover -s skills/multi-agent-dev/tests -p "test_*.py" -q
    python -B -m compileall -q skills/multi-agent-dev-v2
    git diff --check

本轮 V2 为 60/60，V1 为 64/64，compileall 通过，git diff --check 退出码 0。V2 当前包 45 files，manifest SHA-256 40bc0b0e4653d4a71efd41534d9465e77acf88d2cefc54332a279d40261ffe27；测试专员仍须独立复算。代码门禁继续为 NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED，真实 Hook/Profile/model-effort/前向工作流未验证。

## V2.1.2 最终代码审计前置修订（2026-09-27）

在上一节之后又补强了 lease bundle 的 revision CAS、状态事件覆盖和 Scheduler 对已存 AuditReceipt provenance 的二次校验；因此上一节的 40bc0b0e... 已 superseded。当前 V2 包仍为 45 files，manifest SHA-256 为 37dd08272747b66c286c62cedf01ab65e9e16e5f39454ac260b6194ea2995a49。测试专员必须以当前工作树独立复算。


## V2.1.3 最终开发交接（2026-09-27）

上一节的 hash 已 superseded。当前包：**45 files**；manifest SHA-256：

    184bb6f9e8bffd88e9f7fa70b78a2e0d2e70d9c41ccfc92699138e7493ab14bb

最终本地结果：V2 **61/61 OK**；V1 **64/64 OK**（Windows 下使用 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、代码页 65001）；V2 compileall 通过；`git diff --check` 退出码 0，仅保留 V1 六文件换行提示。

本轮已修复并增加反例覆盖：过期 lease 的 stop evidence、冻结 manifest/task/write_set、handoff 身份和零退出测试、AuditReceipt PASS/provenance、底层 lease fencing、retry 原子性、namespace bundle release/confirm、事件 ledger、DAG 环、init 幂等/epoch reuse/takeover、multi-namespace fencing map、证据 task/run 绑定。CLI 命令名是 `dispatch-next`。

测试专员应独立复算 manifest，并运行：

    cd /d C:\\Users\\T14S\\.codex\\skills\\multi-agent-dev\\skills\\multi-agent-dev-v2
    python -B -m unittest discover -s tests -p "test_*.py" -q
    cd /d C:\\Users\\T14S\\.codex\\skills\\multi-agent-dev
    set "PYTHONUTF8=1" && set "PYTHONIOENCODING=utf-8" && chcp 65001 >NUL && python -B -X utf8 -m unittest discover -s skills\\multi-agent-dev\\tests -p "test_*.py" -q
    python -m compileall -q skills\\multi-agent-dev-v2
    git diff --check

限制保持不变：WorkerAdapter 是受信本地命令 runner，不是沙箱；同 owner epoch reuse 依赖单一受信 controller 进程；进程树终止/资源隔离仍需专门测试或后续增强。没有真实 Codex Hook/Profile、实际 model/effort provenance、外部 Provider、副作用或前向工作流凭证时，必须保持 **NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED**，不得写成 ACCEPTED、READY_TO_MERGE 或独立路由通过。不得安装 Profile、修改或信任全局 Hook、安装 PyYAML、提交、推送或部署。



## V2.1.4 最终 hash supersede（2026-09-27）

上一节的 184bb6f9... 已因底层 execution transition fence 收紧而 superseded。当前包仍为 **45 files**，canonical manifest SHA-256：

    0b9c7815690c040bc9bdbfe95956a88aa44bdb5aba509be5ddf1493fe77fb175

V2 最终回归为 61/61，V1 显式 UTF-8 回归为 64/64；测试专员必须以当前工作树重新复算 hash。所有运行时门禁和“不得安装 Profile/修改全局 Hook/提交推送部署”限制继续有效。

独立只读审计者已复核当前代码和 61/61 V2 测试；其返回的另一 hash 使用了不同清单编码算法，不能替代本交接文档指定的 canonical 算法。测试专员应以本工作树复算出的 `0b9c7815690c040bc9bdbfe95956a88aa44bdb5aba509be5ddf1493fe77fb175` 为目标，并把任何算法差异单独记录。

### V2.1.4 独立复审门禁更新（2026-09-27）

后续独立复审判定 **FAIL / NOT_ACCEPTED**。尽管 V2 61/61、V1 64/64 通过，隔离反例仍证明 Audit PASS 可接受与 TaskSpec 不匹配的模型/强度及未登记 evidence ref；不相交 namespace 下重复 write_set 可并发派发；声明 supersedes 后旧 run 仍可派发，且当前 dispatch 未校验 run state。另有 event `_ledger` 可伪造、retry 幂等重放冲突及 handoff 多事务非幂等等问题。详见 `05-implementation-evidence.md` §4.22。

因此暂不进入接受/合并门禁。后续测试应先验证修复上述 P1 并增加对应反例回归，再复跑全套测试和独立审计。不得把当前 61/61 作为“缺陷已清零”的证据；Hook/Profile/真实 model-effort 运行时门禁继续未验证。原有限制保持：不安装 Profile、不改或信任全局 Hook、不安装 PyYAML、不提交/推送/部署。


## V2.1.5 修复后测试接手（2026-09-27）

V2.1.4 复审指出的 P1 已完成最小代码修复，但本包仍不是验收通过版本。当前 V2 package 为 45 files；按实施证据中的 canonical manifest 算法复算 SHA-256：

    43e601a9b016c681cc3880d1c0e6333c293dd9a0986ce3ce458f4e4da2939b92

开发侧结果：V2 67/67、V1 显式 UTF-8 64/64、compileall 通过、git diff --check 通过。新增反例覆盖审计 requested/observed model-effort 绑定、已登记 evidence 与 acceptance command、跨 namespace 重叠 write_set、INTAKE/SUPERSEDED 派发、event ledger 防伪、retry 幂等重放和 handoff 单事务幂等链。

测试专员请独立复算 hash，并运行：

    python -B -m unittest discover -s skills\\multi-agent-dev-v2\\tests -p "test_*.py" -q
    set "PYTHONUTF8=1" && set "PYTHONIOENCODING=utf-8" && chcp 65001 >NUL && python -B -X utf8 -m unittest discover -s skills\\multi-agent-dev\\tests -p "test_*.py" -q
    python -B -m compileall -q skills\\multi-agent-dev-v2
    git diff --check

本轮独立隔离反例复核显示：错误模型/强度、未登记 evidence、错误验收命令、重叠写集和 superseded run 派发均被阻断。请继续测试状态层 fencing、stop evidence、DAG、outbox、通知、worker timeout、并发恢复和 CLI 幂等；不要把本地 SQLite/子进程探针当成真实 Codex 运行时证明。

限制保持不变：不得安装 Profile、修改或信任全局 Hook、安装 PyYAML、调用真实 Provider 或外部副作用、提交、推送或部署。没有正式 MAD_ROUTE_RECEIPT、Hook/Profile discovery、实际 model/effort provenance 和五个前向工作流证据时，状态必须保持 NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED；不得写成 ACCEPTED、READY_TO_MERGE 或独立路由通过。所有新结果追加到 05-implementation-evidence.md。


### V2.1.5 最终 hash 修订（2026-09-27）

4.23 之后新增 superseded run 的 integrate-check 阻断断言；当前 package 仍 45 files。最新 canonical manifest SHA-256：

    580673c006d75154358982cf8c92bbc4efb7ee99a3da57823c5771d88e1e38e1

该值 supersedes 43e601a9...。V2 67/67、V1 64/64、compileall、git diff --check 均已重新执行并通过。请测试专员以 580673... 复算目标，继续保持 NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED，直到真实运行时门禁和独立正式凭证到齐。


### V2.1.6 精确命令绑定交接修订（2026-09-27）

V2.1.5 的 P1 已修复：验收检查和 handoff packet 测试命令现在要求与已登记 TEST_RECEIPT 的 command_or_ui_step 逐字相等，含子串但不相等的命令会被阻断。新增端到端反例已通过。

当前 package 仍为 45 files。Manifest 规范固定为：路径仅用于 lower-case 排序，清单行保留原始 POSIX 路径；每行写入 original-relative-path、空格、文件 SHA-256、LF，再对 UTF-8 清单求 SHA-256。当前 hash：

    d2c674516fbc3943e8bc04b82aee170697dd4e918eb2c080ee8daec018afb39d

开发侧：V2 68/68、V1 64/64、专项缺陷回归 17/17、compileall、git diff --check 和 Windows CLI 探针均通过。测试专员必须按新规范独立复算 hash，并复跑全量及命令绑定负例。

没有正式 MAD_ROUTE_RECEIPT、真实 Hook/Profile discovery、实际 model/effort provenance 或前向工作流证据时，状态继续为 NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED；不得把本地 SQLite、CLI 或自填 provenance 当作真实运行时证明。


### V2.1.6 复修后测试交接确认（2026-09-27）

精确命令绑定修复后的复跑结果：V2 全量 **68/68 OK**；V1 显式 UTF-8 回归 **64/64 OK**；V2.1 缺陷回归 **17/17 OK**；并行状态 **22/22 OK**；`test_notify_serverchan.py` 与 `test_task_terminal_notify.py` 各 **9/9 OK**。compileall、`git diff --check` 和 Windows 子进程 CLI `init → dispatch-next → status` 均通过。

验收重点：acceptance check 与 `command_or_ui_step` 逐字相等；handoff `test_receipts.command` 与成功 TEST_RECEIPT 的持久化命令逐字相等；含完整命令子串但不相等的 packet 已有端到端负例，必须阻断，不得进入 ACCEPTED 或 READY_TO_MERGE。

当前 package 为 45 files。Manifest 统一规范：排除 `__pycache__`；按 `relative POSIX path.lower()` 排序；清单行保留原始路径文本；每行 `<path> <file-sha256> + LF`；对完整 UTF-8 清单求 SHA-256。当前 hash：

    d2c674516fbc3943e8bc04b82aee170697dd4e918eb2c080ee8daec018afb39d

主会话的只读静态审计输出 `STATIC_EXACT_BINDING_AUDIT_PASS`。独立审计 Agent 因无法访问 Windows 目标目录，正式结论为 **HOLD**，没有 `MAD_ROUTE_RECEIPT`；测试人员不得将本地 SQLite、CLI、模拟 EvidenceIndex 或自填 model/effort 当作真实 Hook/Profile/Provider 凭证。

未关闭门禁：`NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED`。不得安装 Profile、修改或信任全局 Hook、安装 PyYAML、提交、推送或部署。请独立复算上述 hash，并按交接文档重跑全部命令及反例。


### V2.1.7 exit_code 严格类型修复交接（2026-09-27）

本轮修复了 `EvidenceRecord(exit_code=False)` 被 SQLite 转为 0 并绕过审计门的问题。EvidenceRecord、底层 `StateStore.record_evidence()` 和成功 HandoffPacket 现在都要求 `type(exit_code) is int`；TEST_RECEIPT 必须有整数退出码，成功 handoff 必须为整数 0。

新增反例覆盖：`False`、`0.0`、`"0"` 在三层入口均被拒绝；底层 SQLite 不产生错误证据；错误 packet 无法构造，不能到达 ACCEPTED 或 READY_TO_MERGE。

复验：V2 **69/69**；V1 **64/64**；缺陷回归 **18/18**；并行状态 **22/22**；两组通知各 **9/9**；compileall、`git diff --check`、CLI `init → dispatch-next → status` 均通过。独立只读审计输出 `INDEPENDENT_EXIT_CODE_AUDIT_PASS`。

package 45 files，当前 manifest SHA-256：

    8a3468bb94ddab36cbd41efbcbf377f297b08b3f9adc24d95ebebed2cba48a23

仍未验证真实 Hook、Profile、Provider、模型/思考强度、五个前向工作流和正式 `MAD_ROUTE_RECEIPT`。状态保持 `NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED`。测试人员应独立复算 hash 并重跑全套命令。

### V2.1.8 runtime dispatch gate 修订（2026-09-27）

本轮新增运行时派发门禁，要求显式 child start、带 parent scope 的 activity、`thread/settings/updated` 实际配置、child terminal 和 requested/observed 对照；spawn failure、冲突 settings、父线程先终态和 premature close 均 fail-closed。`thread/started` 中的 model/effort、任务名、Agent 自述和 Hook receipt 不作为实际 route provenance。

复验结果：V2 **83/83**；新增 runtime dispatch 定向测试 **14/14**；V1 **64/64**；compileall 和 `git diff --check` 通过。独立只读代码审计结论 **PASS（代码级范围）**。当前 V2 包 48 files，canonical manifest SHA-256：

    1ed0b18282c0c15bd1a07f993b4d9bef8e6f946288175dd89a037866deb64796

真实 Codex Hook/Profile discovery、实际子 Agent model/effort provenance、正式 `MAD_ROUTE_RECEIPT` 和五个前向工作流仍未验证；状态继续为 `NOT_ACCEPTED / ROUTE_UNVERIFIED / HOOK_UNVERIFIED`。不得把本地 fixture、SQLite、CLI 或请求参数当作真实运行时凭证。
