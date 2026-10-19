---
name: build-plugin
description: 创建、升级或迁移 Claude Code、Codex、ZCode Plugin 或 Pi Package；涉及打包、平台适配、安装或分发时使用，不用于单独构建 Skill 或普通编码。
license: MIT
compatibility: 需要访问互联网；内置静态校验脚本需要 Python 3.9+。
metadata:
  author: koco-co
  version: "3.1.0"
---

# Outcome

把明确的打包需求转化为可安装、可验证且权限可控的 Claude Code、Codex、ZCode Plugin 或 Pi Package。

## Routing

- 新建、升级或迁移 Plugin 时进入对应分支；多平台需求只维护一份核心内容，分别配置 Manifest。
- Plugin 包含 Skill 时交给 `build-skill`；单独构建 Skill 且没有打包、安装或分发需求时退出并转交。
- 由 `audit-agent-setup` 调用时遵循上层的审查或修复授权，不重复确认。
- 普通代码、文档或未查明契约的其他平台适配不属于本 Skill。
- DeepSeek Harness 直接读取用户或项目的 skills 目录，不通过 Plugin 或 Package 分发；DSH 的 Skill 安装不在本 Skill 内。

## Steps

1. 读取 `workflows/§01-research.md`，确认平台、组件、安装、权限、版本和发布事实。
2. 读取 `workflows/§02-design.md`、`rules/plugin-architecture.md`、`rules/platform-compatibility.md` 与 `rules/security-and-permissions.md`。只确认会改变 Plugin 形态、平台、权限或验收的决策；用户要求先评审设计时，输出方案后等待一次确认。
3. 授权范围明确后读取 `workflows/§03-skill-delegation.md`，把 Skill 子任务交给 `build-skill`，并复核结果。
4. 读取 `workflows/§04-implementation.md`，实现已确认的组件，保持单一规范源和平台隔离。
5. 读取 `workflows/§05-validation-delivery.md`，运行静态校验、安装检查和适用的真实平台场景，报告文件、版本、验证状态、未验证项和后续动作。

## Rules

- 不复制相同工作流，不依赖安装器保留嵌套软链接；共享文件按清单同步并校验。
- 明确要求创建、升级或迁移时，已授权对应分发文件的本地编辑；commit、push、Marketplace、Release、发布和本地 Plugin 更新必须分别授权。

## References

- 调研与设计：`workflows/§01-research.md`、`workflows/§02-design.md`。
- Skill 委派：`workflows/§03-skill-delegation.md`。
- 实现：`workflows/§04-implementation.md`。
- 验证与交付：`workflows/§05-validation-delivery.md`。
- 架构、平台与权限：`rules/plugin-architecture.md`、`rules/platform-compatibility.md`、`rules/security-and-permissions.md`。
- Skill 规范：`rules/skill-architecture.md`、`rules/skill-frontmatter.md`、`rules/skill-quality-standard.md`；由 `build-skill` 维护，本目录为共享镜像。
- 插件设计与语义验收：`checklists/plugin-design-review.md`、`checklists/plugin-semantic-acceptance.md`；共享 Skill 审查：`checklists/skill-design-review.md`、`checklists/skill-content-review.md`、`checklists/skill-copy-review.md`、`prompts/reviewer.agent.md`。
- 设计提案与交付报告：`templates/plugin-design-proposal.template.md`、`templates/plugin-delivery-report.template.md`。
