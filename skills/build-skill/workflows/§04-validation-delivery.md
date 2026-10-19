# 验证与交付

按变更事实选择静态检查、设计落实、内容、文案、内容回归、独立审查、场景和平台验证；没有依据的检查不执行。已选检查不能互相替代。

## Phase 1：静态检查

优先运行目标仓库已有命令。没有等价能力时，使用本 Skill 的校验器：

```bash
python3 scripts/validate_skill.py /path/to/skill --profile portable --strict
```

按目标平台选择：

```bash
python3 scripts/validate_skill.py /path/to/skill --profile claude --strict
python3 scripts/validate_skill.py /path/to/skill --profile codex --strict
python3 scripts/validate_skill.py /path/to/skill --profile zcode --strict
python3 scripts/validate_skill.py /path/to/skill --profile pi --strict
python3 scripts/validate_skill.py /path/to/skill --profile dsh --strict
python3 scripts/validate_skill.py /path/to/skill --profile dual --strict
```

`dual` 用于同时面向 Claude Code 与 Codex 的 Skill，会额外检查 `agents/openai.yaml` 与 `disable-model-invocation` 的一致性；只跑 claude 和 codex 两个单平台 profile 不能替代。

校验器覆盖结构、Frontmatter、引用、工作流编号、命名、空文件和软链接；清单只处理脚本无法判断的内容与场景。

## Phase 2：设计、内容与文案审查

1. 按 `checklists/design-review.md` 检查设计与实现是否一致：目标是否落地、Frontmatter 是否匹配矩阵、目录是否仍然必要、脚本与 Skill 职责是否正确、是否出现重复规范源、是否越界。
2. 按 `checklists/content-review.md` 检查行为是否正确、完整：路由和步骤是否齐全、可复现失败是否有处理、完成条件是否明确、权限与平台行为是否符合确认结果。
3. 内容通过后，按 `checklists/copy-review.md` 检查自然度、清晰度、简洁度、术语一致性、正反向表达和示例质量；只改表达，不改触发、流程、范围、权限、失败处理或验收。
4. 文案修改后重跑受影响的内容检查和静态检查，确认行为、顺序、确认要求、权限限制和完成证据没有被削弱。

语义歧义在内容阶段解决，不留给文案审查猜测。

## Phase 3：独立 Reviewer

以下变更读取 `prompts/reviewer.agent.md` 并调用独立 Reviewer：

- 新建 Skill；
- 整体重构；
- 改变触发或 Frontmatter；
- 改变权限、上下文或平台行为。

Reviewer 只读审查，分别输出内容与文案结果。主 Agent 修复 Finding 后，再请 Reviewer 复查。微小且不改变语义的修改可以省略；平台无法提供独立 Agent 时标记“未完成独立审查”，不伪造结果。

## Phase 4：真实场景与平台验证

只验证本次目标实际包含的场景：调用策略、输入分支、可复现缺陷、平台差异和交付状态。不为覆盖用户调用、模型调用、参数化、通用、项目级、升级、失败等类别而制造目标 Skill 不具备的行为。

使用临时目录、夹具或隔离分支，避免污染真实项目。平台验证分别记录安装位置、调用配置、权限是否符合设计、专属配置是否隔离、核心工作流是否仍是单一规范源，以及是否真实运行；未运行时写清完成了哪些静态检查。

DSH 至少确认：按安装范围检查 `<dshHome>/skills/<name>/SKILL.md`（用户级）或 `<project>/.dsh/skills/<name>/SKILL.md`（项目级）存在，模型目录出现（或按 `disable-model-invocation` 正确隐藏），`/skill-name` 显式调用可用（将 `skill-name` 换成实际名称），排除场景不触发；`<dshHome>` 为 `$DSH_HOME` 或 `~/.dsh`。Claude Code、Codex、ZCode、Pi 的验证范围按 `rules/platform-compatibility.md` 执行。

## Phase 5：失败修复与复验

实际失败项记录：

```text
失败项：
复现命令或场景：
原因：
修复：
重跑范围：
最终结果：
```

只有修复后重新执行受影响检查并通过，才可标记为已验证。

## Phase 6：交付报告

从实际变更和命令结果汇总，不按计划推断：

- 完成目标与排除项；
- 最终目录树和文件变更；
- Skill 目录外的 CLI、Hooks 或公共能力；
- 平台适配与 Frontmatter 最终状态；
- 内容、文案、回归和独立审查结果；
- 验证命令、场景和结果；
- 外部来源与许可证；
- 风险、未验证项和阻塞项。

统一标记状态：

- **已验证**：有命令输出、测试、文件或真实业务结果支撑；
- **未验证**：实现完成，但当前环境无法真实运行或证据不足；
- **阻塞**：缺少权限、环境、输入或外部条件，无法继续。

“已创建文件”“静态阅读正常”和“应该可以运行”不等于“已验证”。报告使用 `templates/delivery-report.template.md`，让用户能定位变更、复现验证、判断平台差异和遗留风险。

## Phase 7：按调用模式停止

先判断是独立调用，还是由 `build-plugin` 等 Skill 统筹。两种模式都要完成事实汇总、验证状态和报告，不因受控调用省略审查或验证。

**受控调用（上层 Skill 统筹）**

- 不重复询问或执行 commit、push、发布、独立安装和 Plugin 更新；
- 向上层返回修改内容、确认依据、复用依据、验证证据、提交状态、未验证项和恢复条件；
- 尚未创建提交时写“由上层待生成并回填”，不虚构 SHA；
- 出现新的产品、架构、公开接口或范围决策时暂停，交回上层。

**独立调用**

完成当前 Skill 后：

- 不自行构建下一个 Skill，不创建其目录或占位文件；
- 不把提交、推送、发布或安装更新当作默认步骤；
- 只列出真实适用的动作：Git 仓库可列 commit；已知远端与分支时可列 push；已安装到 Claude Code、Codex、ZCode、Pi 或 DSH 时可列对应更新；普通项目不虚构 Plugin、Marketplace 或客户端动作；
- 用下面这句话主动询问一次，并写明每项动作的真实目标、推荐答案，以及可以全部或部分授权：

  ```text
  实现和验证已经完成。是否执行以下交付动作？
  ```

- 用户回答前不执行任何交付动作；只执行明确授权部分，未授权项记录为未执行；
- 提问后停止，等待授权，不自行开始下一项任务。
