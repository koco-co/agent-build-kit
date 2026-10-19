---
name: build-agents-md
description: 初始化或重构项目的 AGENTS.md，并提供只包含 @AGENTS.md 的普通 CLAUDE.md 兼容 Claude Code；让读取 AGENTS.md 的客户端（包括 Codex 与 DeepSeek Harness）共用同一份项目指令。项目指令缺失、失效或与事实不符时使用，不用于普通文档、CI 或测试建设。
license: MIT
compatibility: 需要 Python 3.9+ 运行内置校验脚本。
metadata:
  author: koco-co
  version: "4.1.0"
---

# Outcome

为项目建立简洁、具体、可执行且可验证的 Agent 开发指南，并让多个客户端读取同一份正文。

## Routing

- 根目录缺少 `AGENTS.md` 时初始化；已有时先审查，再按需要整体重构。
- Monorepo 只有子目录确有不同约定时才创建嵌套指南。
- 用户明确要求初始化、重构或修复，且范围可由仓库事实确定时直接实施；仅审查或预览时保持只读。
- 普通文档、通用 Agent 规范、测试框架和 CI 建设不属于本 Skill；由 `audit-agent-setup` 调用时遵循上层授权范围。

## Steps

1. 读取 `workflows/§01-research.md` 与 `rules/content-admission.md`，只用仓库事实确定内容和文件范围。
2. 读取 `workflows/§02-preview.md`，形成完整正文和文件操作。只有用户要求预览，或存在会改变文件范围、规则语义或删除内容的未决选择时才等待确认。
3. 读取 `workflows/§03-authoring.md`、`rules/platform-and-scope.md` 与 `templates/agents-md.template.md`，写入 `AGENTS.md` 和只包含一行 `@AGENTS.md` 的普通 `CLAUDE.md`。
4. 读取 `workflows/§04-validation-delivery.md` 与 `checklists/semantic-acceptance.md`，运行校验和适用项目命令，报告变更、证据、未验证项和恢复条件。

## Rules

- `AGENTS.md` 只保留项目特有、会改变执行结果的约定；保留用户未提交的修改。
- 不创建额外文档、CI 或测试体系；提交、推送、安装和 Plugin 更新均需单独授权。

## References

- 项目事实、内容取舍、预览、写入、验证和交付：按 Steps 读取对应工作流。
- 平台与目录范围：`rules/platform-and-scope.md`。
- 内容准入：`rules/content-admission.md`。
- 正文骨架：`templates/agents-md.template.md`；需要展示完整替换方案时使用 `templates/replacement-preview.template.md`。
