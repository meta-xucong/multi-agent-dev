# Multi-Agent Audit — Claude Code Edition

适用于 **Claude Code** 的多代理审计工作流，基于 context-lean 原则。

## ⚠️ 平台差异

本版本为 **Claude Code** 设计，使用 **Claude 模型家族**（Opus/Sonnet/Haiku）。

**不兼容** Codex 平台。Codex 版本请访问主仓库的 `main` 分支。

## 核心特性

### 1. 多模型协作
- **主对话** (Sonnet 5): 协调、实现
- **独立审计** (Opus 4.8): 提供差异化视角
- **构建验证** (Opus 5 via Haiku): 运行测试

### 2. Context-Lean 设计
- 子代理只接收最小必要上下文 (diff + 文件列表)
- Progressive disclosure
- Evidence-based stopping
- Surgical changes

### 3. 八荣八耻工程纪律

集成 [八荣八耻](https://github.com/oyj123321/claude-code-eight-principles) 代码规范：

- ✓ 查档求证 (验证 API 使用)
- ✓ 对齐需求 (功能完整性)
- ✓ 请示规则 (业务逻辑确认)
- ✓ 复用存量 (避免重复代码)
- ✓ 完备测例 (边界覆盖)
- ✓ 恪守规范 (架构一致性)
- ✓ 坦诚存疑 (不确定性标注)
- ✓ 分步迭代 (小步变更)

## 工作流程

```
用户请求
  ↓
1. 需求分析 (Sonnet 5)
   - 识别变更范围 (≤5 文件)
  ↓
2. 实现 (Sonnet 5)
   - 精确修改，不做额外重构
  ↓
3. 并行审计 & 验证
   ├─ auditor (Opus 4.8) → 八荣八耻检查
   └─ verifier (Opus 5) → 构建/测试
  ↓
4. 判定
   ├─ 通过 → 完成 ✓
   └─ 问题 → 修复 (最多 3 轮)
```

## 安装

```bash
# 复制到 Claude Code skills 目录
cp -r claude-code-version ~/.claude/skills/multi-agent-audit

# 重启 Claude Code 使 skill 生效
```

## 使用

```bash
/multi-agent-audit "实现 USB 路径验证功能"
```

## 测试结果

✅ 已验证场景：
- 文件备份工具实现（5 个测试用例）
- Opus 4.8 发现重复覆盖问题
- 1 轮迭代修复通过

Token 消耗：~16k (子代理) + ~8k (主对话)

## 参考资源

- [lean-codex](https://github.com/heyseven7/lean-codex) - Context-lean workflow
- [八荣八耻](https://github.com/oyj123321/claude-code-eight-principles) - Engineering discipline
- [agent-runbook](https://github.com/KnoxOps/agent-runbook) - Multi-agent framework

## 许可证

MIT

---

**最后更新**: 2026-09-22  
**适配平台**: Claude Code 2.x + Claude 5 系列  
**模型要求**: Opus 4.8/5 + Sonnet 5 + Haiku 4.5
