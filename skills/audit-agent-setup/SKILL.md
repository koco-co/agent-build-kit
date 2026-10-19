---
name: audit-agent-setup
description: 检查项目的 Skill、Plugin 与 Pi Package、README、AGENTS.md/CLAUDE.md；用户要求项目规范健康检查时使用，不用于代码质量、安全、依赖、测试、CI 或性能审计。
license: MIT
metadata:
  author: koco-co
  version: "3.1.1"
---

# Outcome

先只读检查并一次性报告真实问题；用户已授权修复时，再按报告范围修复、验证并复检。

## Routing

- 单独调用时检查四个规范领域：Agent Skill、Plugin 与 Pi Package、README、AGENTS.md/CLAUDE.md。
- 只要求检查时保持只读，报告后询问是否修复；明确要求检查并修复时，报告后直接处理成立问题，但 README/AGENTS.md 的新增、整体替换、公开内容或范围变化、删除仍先展示正文并取得内容确认。
- 本 Skill 只随完整 `agent-build-kit` 分发包提供。代码质量、安全、依赖、测试覆盖率、CI 和性能审计不在范围内。

## Steps

1. 读取 `rules/domain-contract.md` 与 `workflows/§01-inspection.md`，记录工作区现状，确定适用领域。
2. 只读调用适用领域 Skill。Plugin 与 Pi Package 内的 Skill 由该领域统一检查；每项问题只保留问题、证据、修复方案、影响文件和验证方式。
3. 使用 `templates/audit-agent-setup-report.template.md` 输出一次性报告。无问题时结束；只要求检查时，有问题才请求一次修复确认；已明确要求修复时直接继续；README/AGENTS.md 的新增、整体替换、公开内容或范围变化、删除仍先展示预览并确认。
4. 获得授权后读取 `workflows/§02-remediation.md`，按领域修复、验证，并重新运行同一范围的健康检查。
5. 读取 `checklists/semantic-acceptance.md`，交付已修复项、复检结果、未验证项和剩余问题。

## Rules

- 检查阶段只读；只报告有证据的问题，不创建持久化报告，不扩张审计范围。
- 不自动 commit、push、发布、部署或更新本地 Plugin。

## References

- 四领域边界与返回字段：`rules/domain-contract.md`。
- 只读检查与修复流程：`workflows/§01-inspection.md`、`workflows/§02-remediation.md`。
- 报告格式：`templates/audit-agent-setup-report.template.md`。
- 交付前自检：`checklists/semantic-acceptance.md`。
