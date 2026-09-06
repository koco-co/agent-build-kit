# Agent Build Kit 开发指南

## 项目概览

- 本仓库为 Claude Code、Codex 与 ZCode 分发 `agent-build-kit` Plugin，并为 Pi 分发 Package；也支持从 `skills/` 单独安装不依赖其他 Skill 的能力。
- `skills/` 是 Skill 行为的权威来源；Claude Code 专用配置写在 `SKILL.md` Frontmatter，Codex 专用配置写在 `agents/openai.yaml`。
- `AGENTS.md` 是仓库开发说明的唯一正文；`CLAUDE.md` 是只包含 `@AGENTS.md` 的普通文件，供 Claude Code 导入同一正文。

## 仓库结构

- `skills/<name>/SKILL.md`：Skill 的入口与主流程；详细内容按需放入同目录的 `workflows/`、`rules/`、`templates/`、`examples/` 和 `checklists/`。
- `skills/build-skill/scripts/validate_skill.py`：检查单个 Skill 的结构和多平台配置。
- `skills/build-plugin/scripts/validate_plugin.py`：检查 Plugin Manifest、组件、共享文件镜像、符号链接安全和版本号。
- `scripts/install_skill.py`：将单个 Skill 安装到 Claude Code、Codex、ZCode 或 Pi。
- `scripts/sync_distributions.py`：合并执行发布前门禁，并在显式发布模式下提交、推送和同步四个平台分发。
- `.plugin-shared-files.json`、`skills/build-plugin/scripts/sync_shared_files.py`：记录跨 Skill 共享文件的规范源，并同步普通文件副本，避免客户端缓存遗漏嵌套软链接。
- `.claude-plugin/`、`.codex-plugin/` 与 `.zcode-plugin/`：三个平台的 Plugin Manifest；`.claude-plugin/marketplace.json` 同时是 Claude Code 与 ZCode 的 Marketplace 配置，`.agents/plugins/marketplace.json` 是 Codex Marketplace 配置；`package.json` 声明 Pi Package 及其 Skills。
- `evals/skills/`、`scripts/validate_skill_evals.py`：保存九个 Skill 的触发、排除和关键行为用例，并在 CI 中做确定性结构校验，不调用付费模型。
- `tests/`：校验器、安装器和仓库约定的回归测试。
- `README.md`：面向使用者说明能力、安装方法和验证命令，不重复 Skill 的详细流程。
- `LICENSE`：Agent Build Kit 的 MIT License 正文。

## 常用命令

- `python3 -m unittest discover -s tests -p 'test_*.py' -v`：运行全部回归测试。
- `python3 skills/build-plugin/scripts/validate_plugin.py . --platform all --strict`：检查全平台分发包（三份 Plugin Manifest、Pi Package 及版本一致性）。
- `python3 skills/build-skill/scripts/validate_skill.py skills/build-agents-md --profile dual --plugin-root . --strict`：检查单个 Skill；修改其他 Skill 时替换目标路径。
- `python3 skills/build-agents-md/scripts/validate_agents_md.py . --strict`：检查项目指令和 `CLAUDE.md` 导入文件。
- `python3 skills/build-readme/scripts/validate_readme.py README.md --project-root . --strict`：检查 README 结构和本地引用。
- `python3 skills/build-plugin/scripts/sync_shared_files.py --root .`：只读检查跨 Skill 镜像是否与规范源一致；需要刷新时显式添加 `--write`。
- `python3 scripts/validate_skill_evals.py .`：静态检查每个正式 Skill 是否具有触发、排除和关键行为用例。
- `git diff --check`：检查空白和补丁格式问题。
- `python3 scripts/sync_distributions.py`：一次运行完整本地发布前门禁，不修改远程仓库或客户端。
- `python3 scripts/sync_distributions.py --publish --stage --message "..."`：显式提交、推送并同步四个平台分发。

## 关键约定

- 最高优先级：禁止防御性编程和防御性提示词。所有行为都必须有用户需求、仓库事实、平台契约、可复现缺陷或明确安全要求作为依据；不得仅凭假设增加代码、分支、兜底、兼容、校验、权限确认、提示词或流程。输入校验、数据安全、权限边界和错误处理同样需要说明具体依据。
- 主 `SKILL.md` 只保留目标、适用与退出条件、执行顺序和必要限制。引用的本地文件必须存在，工作流文件使用 `§NN-name.md` 命名；删除没有依据或与附属规范重复的内容，详见 `skills/build-skill/rules/quality-standard.md`。
- 用户明确要求创建、更新或修复且范围可由仓库事实确定时，可直接执行对应本地编辑；仅在选择会改变结构、公开行为、权限或验收时提问。commit、push、安装、发布和本地 Plugin 更新仍分别授权。
- 调用策略写在平台配置中；目标 Skill 允许模型调用时，按 `skills/build-skill/rules/quality-standard.md` 写清触发条件和排除条件。
- 跨 Skill 运行依赖在 `.plugin-shared-files.json` 中声明，仓库保存普通文件副本。修改规范源后执行同步；副本缺失、使用软链接或内容与规范源不一致时，严格校验必须失败。
- 项目级 `CLAUDE.md` 不使用符号链接，必须是只包含 `@AGENTS.md` 的普通文件；其他确需使用的符号链接必须是仓库内相对链接，不得假设 Plugin 客户端缓存会保留嵌套软链接。
- Claude Code 安装副本保留 Claude Code 支持的 Frontmatter，并移除 `agents/`；Codex 安装副本移除 Claude Code 专用 Frontmatter，并保留 `agents/openai.yaml`；ZCode 与 Pi 忽略未识别的 Frontmatter 键，安装副本保留完整 Frontmatter 并移除 `agents/`。
- 当前只直接维护 Claude Code、Codex、ZCode 与 Pi；不再维护 DSH 专用包、镜像、安装分支或验证流程。
- 破坏性兼容变更递增 Plugin major 版本，新增向后兼容能力递增 minor 版本，修复递增 patch 版本；五个正式版本号（`.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`、`.codex-plugin/plugin.json`、`.zcode-plugin/plugin.json` 与 `package.json`）必须一致。Skill 的 `metadata.version` 独立维护。
- 静态校验、安装成功和测试用例能被识别，都不能代替在真实 Claude Code/Codex/ZCode/Pi 客户端中验证行为。

## 验证流程

| 修改内容                     | 至少运行                                                                                                                     |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| 新建或修改 Skill             | 先补行为测试，再运行目标 Skill 检查和相关单元测试                                                                            |
| Manifest、平台适配或共享文件 | 镜像检查、全平台分发包检查、安装器测试和完整回归                                                                             |
| `AGENTS.md` / `CLAUDE.md`    | `validate_agents_md.py --strict`，并检查 Git 中的普通文件与导入内容                                                          |
| README                       | `validate_readme.py`，并核对公开命令与当前仓库一致                                                                           |
| 正式版本                     | 核对 `.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`、`.codex-plugin/plugin.json`、`.zcode-plugin/plugin.json` 和 `package.json` |
| 四端同步脚本                 | 先运行本地门禁；发布模式再核对提交、推送和 Claude Code、Codex、ZCode、Pi 的安装版本与关键 Skill 文件                           |

- 行为变化还要在适用的真实客户端中验证；当前环境无法完成时，明确标为“未验证”。
- 交付前运行相关测试、完整回归、全平台分发包检查和 `git diff --check`，分别报告结果。

## 提交与发布

- Skill 与 Plugin 的详细交付流程分别维护在 `skills/build-skill/workflows/§06-delivery.md` 和 `skills/build-plugin/workflows/§07-delivery.md`，本文件不复制具体发布命令。
- 实现和验证结束后，主动询问用户是否执行当前任务需要的 commit、push、Claude Code Plugin 更新、Codex Plugin 更新、ZCode Plugin 更新和 Pi Package 更新；允许只授权部分操作。
- 普通开发流程不得自动 commit、push 或更新本地 Plugin；用户明确执行 `scripts/sync_distributions.py --publish` 时，视为一次性授权该脚本按既定顺序完成这些动作。
