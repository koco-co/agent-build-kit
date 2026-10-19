# 项目级 Skill 示例：`service-release`

本示例强调项目探索和已有能力复用，不代表固定目录模板。

## 场景

目标项目已有：

- `./tools/release` CLI；
- `make verify` 检查入口；
- `.github/workflows/release.yml` 发布流程；
- `docs/release-policy.md` 版本与审批规则。
- `.agents/scripts/release-evidence.py`，由 `service-release` 和既有的 `service-audit` 两个 Skills 共用，用于把 `./tools/release` 的 JSON 输出转换为同一证据结构；脚本只使用 Python 3.9+ 标准库并随项目提交。

用户希望构建一个项目级 Skill，帮助准备发布清单、运行预检并生成交付摘要，但不得自动发布。

## Frontmatter 字段决策矩阵

| 字段或配置 | 结论 | 理由 |
| ---------- | ---- | ---- |
| `name`、`description` | 添加 | 通用必填字段 |
| `disable-model-invocation: true` | 添加到 Claude Code 源 | 发布准备包含命令执行，必须由用户控制时机 |
| `agents/openai.yaml` | 添加 | Codex 禁止模型隐式调用 |
| `compatibility` | `需要 Git、Python 3.9+ 和项目内的 ./tools/release。` | 三者是所有分支都需要的硬性环境条件 |
| `allowed-tools` | 省略 | 是否预授权命令应遵循目标项目权限策略，不在 Skill 中扩大权限 |

## 探索结论

- 版本计算、变更日志生成和制品校验已经由 `./tools/release` 实现；
- 发布准备与发布审计确实共用同一证据转换契约，因此保留 `.agents/scripts/release-evidence.py` 这一项目级单一规范源；
- Skill 不应在自己的 `scripts/` 中复制这些逻辑；
- 每次合并到发布分支后的自动检查属于 CI，不属于 Skill；
- Skill 只负责收集上下文、确认发布范围、编排已有命令、解释结果和生成报告。

## 推荐结构

```text
project-root/
├── .agents/
│   └── scripts/
│       └── release-evidence.py  # 两个 Skills 共用，随项目交付
└── skills/
    └── service-release/
        ├── SKILL.md
        ├── workflows/
        │   ├── §01-prepare.md
        │   ├── §02-verify.md
        │   └── §03-handoff.md
        ├── templates/
        │   └── release-summary.template.md
        └── checklists/
            └── release-readiness.md
```

`skills/service-release/` 表示 Skill 规范源，实际安装位置由各平台安装器决定；`.agents/scripts/` 保持项目根目录位置，并由项目或整体安装包显式交付。

## 边界划分

| 能力           | 位置                     | 理由                       |
| -------------- | ------------------------ | -------------------------- |
| 版本与制品校验 | `./tools/release`        | 已有确定性实现             |
| 证据结构转换   | `.agents/scripts/release-evidence.py` | 两个 Skills 共用相同稳定契约，且脚本随项目交付 |
| 合并后自动检查 | GitHub Actions           | 必须由事件可靠触发         |
| 发布审批规则   | `docs/release-policy.md` | 项目唯一规范源             |
| 命令编排与解释 | Skill 工作流             | 需要上下文判断             |
| 发布摘要结构   | Skill 模板               | 固定交付格式               |
| 最终发布       | 不在 Skill 默认范围      | 具有外部副作用，需单独授权 |

## 关键 Guardrail

“准备发布”不等于“执行发布”。即使所有检查通过，也只能输出交接摘要；执行发布命令必须获得用户针对本次发布的明确授权。

## 验收场景

1. 能读取项目发布规则而不重复询问版本约定；
2. `make verify` 失败时停止，不生成“可发布”结论；
3. 不复制 `./tools/release` 的业务逻辑；
4. 未授权时不会触发发布工作流；
5. 报告能够区分通过、未验证和阻塞项。
6. `python3 .agents/scripts/release-evidence.py <fixture>` 在无第三方依赖的环境中通过，两个 Skills 生成一致的证据结构。
