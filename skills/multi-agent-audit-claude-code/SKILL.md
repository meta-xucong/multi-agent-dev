---
name: multi-agent-audit
description: Multi-agent workflow - implement → audit(Opus 4.8/high) → verify(Sonnet 5/medium) → fix loop with context-lean delegation
version: 2.1.0
---

# Multi-Agent Audit Workflow (Context-Lean)

基于 [lean-codex](https://github.com/heyseven7/lean-codex) 原则的多代理协作审计系统。

## 核心原则

1. **Context-lean delegation**: 子代理只接收完成任务的最小必要上下文
2. **Progressive disclosure**: 主对话保持精简，按需加载详细信息
3. **Evidence-based**: 一旦有足够证据就停止收集
4. **Surgical changes**: 精确修改，不做多余重构

## 模型与思考强度分配

| 角色 | 模型 | Effort | 理由 |
|---|---|---|---|
| **主对话** | Sonnet 5 | (session default) | 平衡能力和成本，足够应对协调和实现 |
| **auditor** | Opus 4.8 | `max` | 需要最高强度推理发现隐蔽问题，差异化视角 |
| **verifier** | Sonnet 5 | `high` | 高标准验证，避免遗漏构建/测试问题 |

## 工作流程

```
用户请求
  ↓
1. 需求分析 (主对话)
   - 识别变更范围
   - 确定影响的文件 (最多 5 个)
  ↓
2. 实现阶段 (主对话)
   - 精确修改目标文件
   - 不做额外重构
  ↓
3. 并行审计 & 验证
   ├─ auditor (Opus 4.8) ──→ 审计报告
   └─ verifier (Opus 5) ──→ 验证报告
  ↓
4. 判定
   ├─ 通过 → 完成 ✓
   └─ 问题 → 修复 (最多 3 轮)
```

## 使用方式

```bash
/multi-agent-audit "实现 USB 安装器的策略检测功能"
```

---

## Execution Prompt

你是 multi-agent 协作系统的主协调者 (Sonnet 5)。

### 任务

{TASK}

### 第 1 步：需求分析 (Context-Lean)

**目标**: 识别变更范围，保持主上下文精简

1. 使用 `Grep` 快速定位相关代码 (不要 `Read` 整个文件)
2. 确定需要修改的文件列表 (≤ 5 个文件)
3. 如果超过 5 个文件，拆分任务或使用 `explorer` 子代理

**输出**: 
```yaml
scope:
  files: [file1.rs, file2.rs]
  changes: [brief description]
```

### 第 2 步：实现 (Surgical Changes)

**原则**: 
- 只修改必要的代码
- 不做"顺手"重构
- 不添加未要求的功能

使用 `Edit` 工具进行精确修改。

### 第 3 步：Context-Lean Delegation

**关键**: 子代理不需要完整上下文，只需要：
- 变更的 diff
- 相关文件路径
- 具体任务指令

**并行启动审计和验证**:

```javascript
// 准备精简的上下文
const changesSummary = `
变更文件:
${files.map(f => `- ${f.path}`).join('\n')}

变更内容 (diff):
\`\`\`diff
${gitDiff}
\`\`\`
`;

// 并行执行
const [auditResult, verifyResult] = await Promise.all([
  // Auditor: Opus 4.8 独立审计
  Agent({
    subagent_type: "auditor",
    model: "opus",
    effort: "max",  // 最高强度推理，发现隐蔽问题
    description: "Independent audit with Opus 4.8",
    prompt: `
你是独立审计员 (Opus 4.8)，提供独立视角。

## 任务
审计以下代码变更，假设有问题并找到它们。

## 上下文 (最小必要)
${changesSummary}

## 审计清单（基于"八荣八耻"）

### 1. 需求对齐检查
- ✓ **查档求证**: API/接口使用是否查阅了文档？
- ✓ **对齐需求**: 功能是否完全覆盖需求？有无误解？
- ✓ **请示规则**: 业务逻辑是否经过确认？有无脑补？

### 2. 代码质量检查
- ✓ **复用存量**: 是否搜索并复用了现有实现？
- ✓ **完备测例**: 边界条件、错误路径是否都有测试覆盖？
- ✓ **恪守规范**: 是否遵循项目架构和命名规范？

### 3. 工程纪律检查
- ✓ **坦诚存疑**: 不确定的地方是否明确标注？
- ✓ **分步迭代**: 变更是否足够小、可独立验证？

### 4. 技术约束检查
- ✓ **边界条件**: null/empty/overflow 是否处理？
- ✓ **资源管理**: 是否有内存/文件/连接泄漏风险？
- ✓ **硬约束**: 是否违反 CLAUDE.md 约束（如 C2: Rust 禁止新增依赖）？

## 输出格式
\`\`\`yaml
audit:
  model: claude-opus-4-8
  passed: true/false
  findings:
    - severity: critical|high|medium|low
      category: boundary|error_handling|resource|constraint
      location: file.rs:42
      issue: "问题描述"
      evidence: "代码证据"
      fix: "修复建议"
\`\`\`

如果无问题: \`findings: []\`
`
  }),

  // Verifier: Sonnet 5 构建验证
  Agent({
    subagent_type: "verifier",
    model: "sonnet",
    effort: "high",  // 高标准验证，避免遗漏问题
    description: "Build & test verification",
    prompt: `
你负责构建和测试验证 (Sonnet 5)。

## 任务
运行构建和测试，回报原始输出。

## 变更文件
${files.map(f => f.path).join('\n')}

## 验证步骤

**检测项目类型并执行**:

- Rust: \`cargo build\`, \`cargo test\`, \`cargo clippy\`
- Node.js: \`npm run build\`, \`npm test\`, \`npm run lint\`
- Python: \`python -m py_compile\`, \`pytest\`, \`flake8\`

## 输出格式
\`\`\`markdown
# Verification Report

Model: claude-sonnet-5 (medium effort)

## Build
Exit: {code}
\`\`\`
{stdout/stderr}
\`\`\`

## Test
Exit: {code}
\`\`\`
{stdout/stderr}
\`\`\`

## Lint
Exit: {code}
\`\`\`
{stdout/stderr}
\`\`\`

## Status
- Build: ✓/✗
- Test: ✓/✗
- Lint: ✓/✗
- Overall: PASS/FAIL
\`\`\`

**原样回报输出，不美化失败**
`
  })
]);
```

### 第 4 步：修复循环 (Evidence-Based)

```javascript
let iteration = 0;
const MAX_ITERATIONS = 3;

while (iteration < MAX_ITERATIONS) {
  iteration++;
  
  const auditPassed = auditResult.passed;
  const verifyPassed = verifyResult.allPassed;
  
  // Evidence-based stopping
  if (auditPassed && verifyPassed) {
    return {
      status: "SUCCESS",
      iteration,
      summary: `通过 (${iteration} 轮)`
    };
  }
  
  // Surgical fixes only
  console.log(`第 ${iteration} 轮修复`);
  
  if (!auditPassed) {
    // 只修复审计发现的问题，不做额外变更
    for (const finding of auditResult.findings) {
      修复(finding);  // 精确修复，不重构
    }
  }
  
  if (!verifyPassed) {
    修复(verifyResult.failures);
  }
  
  // 重新审计 (只针对修改的部分)
  [auditResult, verifyResult] = await reAudit();
}

return {
  status: "MAX_ITERATIONS",
  iteration,
  issues: {
    audit: auditResult.findings,
    verify: verifyResult.failures
  }
};
```

### 第 5 步：精简报告

**Context-Lean 输出**:

```markdown
## 结果

状态: {SUCCESS|FAILED}
迭代: {n} 轮

### 变更
- {file1}: {1-line description}
- {file2}: {1-line description}

### 审计 (Opus 4.8)
{通过|发现 N 个问题}

### 验证 (Opus 5)
{通过|失败}

详细报告: {links}
```

---

## Context-Lean 最佳实践

### DO ✓

- **精确定位**: 用 `Grep` 找到目标，不要 `Read` 整个文件
- **最小上下文**: 子代理只接收 diff 和文件列表
- **停止收集**: 有足够证据就行动，不过度调研
- **原子修改**: 一次只改一个问题
- **简洁通信**: 1-2 句状态更新

### DON'T ✗

- **不要**一次性 `Read` 多个大文件到主上下文
- **不要**在子代理中重复主对话已有的上下文
- **不要**做未要求的重构
- **不要**添加"顺手"功能
- **不要**写冗长的总结

---

## 成功标准

- ✅ Opus 4.8 审计通过
- ✅ 构建成功
- ✅ 测试通过
- ✅ Lint 无警告
- ✅ 主上下文保持精简 (< 50k tokens)

## 失败降级

如果 3 轮后仍有问题:
1. 生成问题报告
2. 标记需要人工介入的部分
3. 保存中间状态

---

## 参考资源

- [lean-codex](https://github.com/heyseven7/lean-codex) - Token-conscious workflow
- [agent-runbook](https://github.com/KnoxOps/agent-runbook) - Contract-based multi-agent framework
- [spawn-agent](https://github.com/khanhbkqt/spawn-agent) - Context-clean delegation pattern
