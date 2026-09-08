# context-lean

WorkBuddy 上下文压缩规则优化 Skill，面向长任务、多轮开发、大文件探索和批量处理场景。

## 能力范围

- 延缓无必要的上下文膨胀，减少自动压缩次数
- 在任务边界主动使用 `/compact`，降低被动压缩代价
- 通过 `PreCompact` 保存 `PROGRESS.md` 快照
- 通过 `SessionStart(source=compact)` 注入短状态摘要
- 控制工具输出、文件读取和交接内容的 Token 消耗
- 区分 `/clear`、`/compact`、新会话和子代理的适用场景

## 安装

将 `skills/context-lean` 目录复制到 WorkBuddy 可发现的个人 Skill 目录，并保留其中的 `SKILL.md`。也可以直接将本仓库作为源码仓库使用，再按平台规则注册或加载该 Skill。

## Hook 配置

`hooks/` 目录提供两个可选脚本：

- `before-compact.py`：在压缩前原子复制 `PROGRESS.md` 到 `.workbuddy/state/PROGRESS.precompact.md`
- `after-compact.py`：在压缩后读取 `PROGRESS.md` 的短摘要并通过 `SessionStart` 输出额外上下文

`hooks/settings-hooks.example.json` 是配置示例。示例使用 `python3`，Windows 用户也可以替换为本机 Python 解释器的绝对路径，例如 WorkBuddy 隔离运行时中的 `python.exe`。

启用前应确认：

1. 项目中存在真实的 `PROGRESS.md` 或 `.workbuddy/PROGRESS.md`
2. 先在项目级配置中验证，再考虑合并到用户级设置
3. 不要把密钥、完整会话日志或项目私密信息提交到公开仓库
4. Hook 只负责保存和恢复短状态，不保证压缩无损，也不替代测试和版本控制

## 验证状态

Hook 已通过模拟 `PreCompact` 和 `SessionStart(source=compact)` 输入的语法与行为测试。真实 WorkBuddy `/compact` 生命周期仍应在目标环境中单独验证。

完整规则见同目录下的 [SKILL.md](SKILL.md)。
