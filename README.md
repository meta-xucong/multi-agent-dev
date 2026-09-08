# meta-xucong Skills

个人 WorkBuddy / Codex Skills 仓库。每个 Skill 都放在 `skills/<skill-name>/` 下，彼此独立，便于单独安装、审查和迭代。

## 技能目录

| Skill | 用途 | 入口 |
| --- | --- | --- |
| `multi-agent-dev` | 按开发文档组织主控、按需思考、最小执行与独立审计，以证据控制范围和验收；长任务按需伴随 `context-lean` | [`skills/multi-agent-dev/SKILL.md`](skills/multi-agent-dev/SKILL.md) |
| `context-lean` | 优化 WorkBuddy 长任务的上下文膨胀、主动压缩、压缩前状态保存和压缩后恢复 | [`skills/context-lean/SKILL.md`](skills/context-lean/SKILL.md) |

## 仓库约定

- 一个 Skill 一个目录，入口文件固定为 `SKILL.md`
- Skill 的配套说明、参考资料、脚本和示例配置放在自己的目录内
- 不在仓库根目录放某个 Skill 的专属入口，避免新增 Skill 时发生命名冲突
- 公开提交前检查密钥、令牌、本机绝对路径、完整会话日志和项目私密数据
- 规则变更应同步更新对应 Skill 的说明和验证记录
- `multi-agent-dev` 与 `context-lean` 保持独立目录；主 Skill 只负责条件触发和边界衔接，不复制伴随 Skill 的全部规则
- 未经验证的实验功能标明验证范围，不把模拟测试写成真实平台已验证

## 安装原则

优先按 WorkBuddy 或 Codex 当前版本的官方 Skill 发现目录安装单个 Skill。不要把整个仓库误当成一个 Skill；需要使用哪个 Skill，就安装或注册对应的 `skills/<skill-name>/` 目录。

## 许可证与责任边界

本仓库中的 Skill 是工作方法和自动化辅助脚本，不是权限隔离、合规证明或安全承诺。使用者仍需根据目标平台、项目规则和实际环境进行审查、授权与验证。
