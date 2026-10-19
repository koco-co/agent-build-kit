# Skill 子任务委派

## 1. 盘点 Plugin 中的 Skills

对每个 Skill 标记：

```text
可直接复用
需要升级
需要新建
不应纳入 Plugin
```

可直接复用的 Skill 仍需通过当前规范校验。

## 2. 统一规范

Plugin 中的每个 Skill 必须满足 `build-skill` 的结构、命名、Frontmatter、渐进式读取、静态校验、内容审查和文案审查要求。需要在本 Plugin 内直接核对时，读取 `rules/skill-architecture.md`、`rules/skill-frontmatter.md`、`rules/skill-quality-standard.md` 和 `templates/skill.template.md`；这些文件只提供规范镜像，不替代 `build-skill` 的委派流程。

执行：

```bash
python3 scripts/validate_skill.py <skill-dir> --profile <profile> --strict
```

再使用：

- `checklists/skill-design-review.md`；
- `checklists/skill-content-review.md`；
- `checklists/skill-copy-review.md`。

需要文案改写参考时读取 `examples/skill-copy-review.example.md`。新建、整体重构或改变触发、Frontmatter、权限与平台行为时，使用 `prompts/reviewer.agent.md` 调起独立 Reviewer；Reviewer 只报告问题，主 Agent 修复后复查。

## 3. 委派方式

需要新建或升级 Skill 时：

- 平台支持由当前流程统筹的子任务委派：明确调用 `build-skill` 并传递已确认范围、负责统筹的 Skill、由谁负责创建提交，以及恢复条件；`build-skill` 按其他 Skill 统筹调用时的要求返回结果，不重复询问 commit、push、安装或 Plugin 更新；
- 平台不支持嵌套调用：输出可直接交给 `build-skill` 的交接内容，由用户继续调用；
- 不在本工作流中复制 `build-skill` 的完整实现。

交接内容包含目标、非目标、输入、输出、平台、目录位置、复用能力、验收标准和该 Skill 与 Plugin 关联的配置或接口位置。

## 4. 返回 Plugin 流程

Skill 完成后重新检查：

- 名称与目录；
- Manifest 发现路径；
- 调用权限与触发文案；
- Frontmatter 字段决策矩阵与硬性环境要求；
- 平台适配文件；
- 引用、共享镜像和必要链接；
- 与其他组件的接口；
- 实际验证状态。

完成条件：Plugin 内全部 Skills 均有明确来源，并完成内容审查、文案审查、适用的独立审查和场景验收。
