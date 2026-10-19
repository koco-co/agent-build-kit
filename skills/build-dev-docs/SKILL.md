---
name: build-dev-docs
description: 为代码项目建立、提取或更新必要的开发文档，或复核针对已有开发文档的审查报告；需要记录跨模块契约、开发计划或项目状态时使用，不用于小问题、单篇润色、README、AGENTS.md 整体重构或产品代码开发。
license: MIT
disable-model-invocation: true
metadata:
  author: koco-co
  version: "3.1.0"
---

# Outcome

用最少且职责清楚的文档记录项目事实、已确认设计和可验证状态。

## Routing

- 从零建立：依据需求和已确认设计创建当前开发所需文档。
- 已有项目提取：从代码、配置、测试和历史资料提取缺失契约。
- 持续更新：只更新本次变化实际影响的文档。
- 审查报告复核：逐项核查外部意见；仅审查时保持只读，明确要求修订时修改成立的问题。
- 小问题、局部修复、普通润色和产品代码开发不属于本 Skill；README 与 AGENTS.md 整体重构也不在此处理。

## Steps

1. 若任务是复核审查报告，读取 `workflows/§05-review.md` 并按其流程执行；其余分支从下一步开始。
2. 读取 `workflows/§01-research.md`，确定项目事实、文档缺口和真实未决事项。
3. 读取 `rules/documents.md` 与 `workflows/§02-plan.md`，只选择本次需要的文档职责，并沿用现有路径。
4. 读取 `workflows/§03-authoring.md`，按依赖顺序编写或更新所选文档。只有用户要求预览，或存在会改变文档范围、公开契约或项目结构的未决选择时才等待确认。
5. 读取 `workflows/§04-validation.md` 与 `checklists/acceptance.md`，检查所选文档、引用和事实依据，报告结果与未验证项。

## Rules

- 明确要求建立、提取、更新或修订文档时，已授权对应文档的本地编辑；只要求审查时保持只读。
- 不修改产品代码、机器 Schema、构建配置或客户端配置；不自动 commit、push、安装或部署。
- 保留项目已有结构和未提交工作。`AGENT_BRIEF.md` 与 `CHANGELOG.md` 按项目现状或明确需求创建；AGENTS.md 入口只在用户明确要求时创建或更新，项目已有入口惯例只作为发现线索，不构成修改授权。

## References

- 文档职责与取舍：`rules/documents.md`。
- 调研、计划、编写、验证、复核：`workflows/§01-research.md` 至 `workflows/§05-review.md`。
- 交付前验收：`checklists/acceptance.md`。
- 文档骨架：`templates/` 下对应模板，按需读取。
