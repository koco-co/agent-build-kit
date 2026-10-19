---
name: build-skill
description: 创建、升级或重构通用或项目级 Agent Skill；涉及 Skill 设计、实现或审查时使用，不用于 Plugin 打包、普通提示词润色或一般编码。
license: MIT
compatibility: 核对平台契约需要访问互联网；内置校验脚本需要 Python 3.9+。
metadata:
  author: koco-co
  version: "3.1.1"
---

# Outcome

把 Skill 需求做成结构清晰、行为可靠、可验证，并能适配目标平台的实现。

## Routing

- 新建、升级或重构 Skill 时进入本流程；通用 Skill 与项目级 Skill 共用同一套设计方法，只在安装位置和平台配置上分流。
- 由 `audit-agent-setup` 调用时，沿用上层审查或修复授权；由 `build-plugin` 统筹时，沿用其范围与恢复条件，不重复确认。
- Plugin 打包、安装、分发、普通文档或提示词润色不属于本 Skill。

## Steps

1. 读 `workflows/§01-research.md`，查明需求、目标项目、现状、依赖和平台契约。
2. 读 `workflows/§02-design.md` 与相关规则，形成最小设计；只确认会改变结构、行为、权限或验收的决策。只有用户要求先评审设计，或仍有未决选择时才等待确认。
3. 读 `workflows/§03-implementation.md`，在已确认范围内实现，复用确定性工具，保持单一规范源。
4. 读 `workflows/§04-validation-delivery.md`，按变更选择静态、内容、文案、独立审查、场景和平台验证，然后报告结果。

## Rules

- `SKILL.md` 只保留目标、路由、步骤和必要红线；规则、模板、示例和校验放到附属文件。
- 每条内容都要有用户需求、仓库事实、平台契约、可复现缺陷或明确安全要求作依据；重复或说不清用途就删除。
- 能用脚本判断的事情交给脚本，不靠大段文字重复约束。
- 用户明确要求创建、升级或重构时，已授权对应 Skill 文件的本地编辑；不自动 commit、push、发布、安装或更新 Plugin，并保留用户未提交的修改。

## References

| 需要了解 | 读取 |
| --- | --- |
| 调研、设计、实现、验证与交付 | `workflows/§01-research.md` 至 `§04-validation-delivery.md` |
| 目录结构、章节职责、脚本与资源放置 | `rules/architecture.md` |
| Frontmatter 字段、调用权限与平台隔离 | `rules/frontmatter.md` |
| 内容、文案、依据与验收标准 | `rules/quality-standard.md` |
| Claude Code、Codex、ZCode、Pi、DSH 的差异 | `rules/platform-compatibility.md` |
| 内容、文案与设计审查 | `checklists/content-review.md`、`checklists/copy-review.md`、`checklists/design-review.md` |
| 独立审查 | `prompts/reviewer.agent.md` |
| 入口、设计提案与交付报告模板 | `templates/skill.template.md`、`templates/design-proposal.template.md`、`templates/delivery-report.template.md` |
