# Agent Build Kit

用于澄清想法、构建与审查 Agent Skill 和 Plugin，以及维护项目开发文档的多平台工具集。

[![Claude Code](https://img.shields.io/badge/Claude_Code-Plugin-D97757?logo=anthropic&logoColor=white)](https://code.claude.com/docs/en/plugins)
[![Codex](https://img.shields.io/badge/Codex-Plugin-000000?logo=openai&logoColor=white)](https://developers.openai.com/plugins/)
[![ZCode](https://img.shields.io/badge/ZCode-Plugin-7B5CFF)](https://z.ai)
[![Pi](https://img.shields.io/badge/Pi-Package-7C3AED)](https://pi.dev)
[![Tests](https://github.com/koco-co/agent-build-kit/actions/workflows/validate-skills.yml/badge.svg)](https://github.com/koco-co/agent-build-kit/actions/workflows/validate-skills.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 功能

Agent Build Kit 直接适配 Claude Code、Codex、ZCode 和 Pi。`skills/` 是各项能力的规范源；完整仓库可作为 Plugin 或 Package 安装，不依赖其他 Skill 的能力也可以单独安装。

| Skill | 用途 |
| --- | --- |
| [`clarify-idea`](skills/clarify-idea/) | 通过事实核查和逐轮决策，将模糊想法整理为明确的目标、范围与方案 |
| [`rename-codex-sessions`](skills/rename-codex-sessions/) | 按创建日期和实际内容整理 Codex 本地项目主对话标题，确认后只修改 session 名称 |
| [`audit-agent-setup`](skills/audit-agent-setup/) | 检查 Agent Skill、Plugin、README 和项目指令，确认后修复并复检 |
| [`build-skill`](skills/build-skill/) | 构建或审查符合多平台约定的 Agent Skill |
| [`build-plugin`](skills/build-plugin/) | 构建、升级或迁移 Claude Code、Codex、ZCode 与 Pi 分发包 |
| [`build-readme`](skills/build-readme/) | 基于仓库事实创建或更新 GitHub README |
| [`build-agents-md`](skills/build-agents-md/) | 初始化或重构跨平台 `AGENTS.md` 与 `CLAUDE.md` |
| [`build-dev-docs`](skills/build-dev-docs/) | 为大型代码项目建立、提取、更新开发文档或复核外部审查报告 |
| [`handoff`](skills/handoff/) | 整理跨会话交接信息并生成下一会话提示词 |

`audit-agent-setup` 依赖其他 Skill，只随完整分发包提供。其余 Skill 可以独立安装。

## 安装

### Claude Code

```bash
claude plugin marketplace add koco-co/agent-build-kit@main
claude plugin marketplace list
claude plugin install agent-build-kit@agent-build-kit --scope user
```

完整安装后，可以使用 `/agent-build-kit:clarify-idea` 等命令调用 Skill。

### Codex

```bash
codex plugin marketplace add koco-co/agent-build-kit --ref main
codex plugin marketplace list
codex plugin add agent-build-kit@agent-build-kit
```

完整安装后，可以使用 `$agent-build-kit:clarify-idea` 等命令调用 Skill。

### ZCode

在 ZCode 的 **Settings → Plugin Management → Discover** 中添加 GitHub 仓库 `koco-co/agent-build-kit`，然后安装 Plugin。ZCode 使用 `.claude-plugin/marketplace.json` 发现 Plugin，并优先读取 `.zcode-plugin/plugin.json`。

### Pi

```bash
pi install git:github.com/koco-co/agent-build-kit
pi list
```

完整安装后，可以使用 `/skill:clarify-idea` 等命令调用 Skill。

### 四端同步与发布

一次只做本地验证，不修改远程仓库或本地客户端：

```bash
python3 scripts/sync_distributions.py
```

明确需要发布时，使用一个命令完成验证、提交、推送，以及 Claude Code、Codex、ZCode、Pi 四端更新：

```bash
python3 scripts/sync_distributions.py \
  --publish \
  --stage \
  --message "feat: update agent build kit"
```

`--stage` 会暂存当前全部改动；不指定时，脚本只接受已经整理好的暂存区，并拒绝未暂存或未跟踪文件。脚本不会强制推送、拉取合并或直接编辑客户端缓存。ZCode 更新通过其内置 app-server 完成；Codex 更新后，如果已经打开的会话仍引用旧缓存路径，请重启 Codex 或新开会话。

### 单独安装 Skill

以下命令只校验并准备平台专用副本，不写入目标目录：

```bash
python3 scripts/install_skill.py build-skill \
  --platform codex \
  --scope user \
  --dry-run
```

移除 `--dry-run` 后执行安装。`--platform` 支持 `claude`、`codex`、`zcode` 和 `pi`；`--scope` 支持 `user` 和 `project`。将 `build-skill` 替换为以下名称可安装其他独立 Skill：

- `clarify-idea`
- `rename-codex-sessions`
- `build-plugin`
- `build-readme`
- `build-agents-md`
- `build-dev-docs`
- `handoff`

目标目录已存在时默认拒绝覆盖；明确需要覆盖时添加 `--force`。

## 3.0.0 迁移

3.0.0 是破坏性版本，不提供旧名称的运行时别名。升级完整分发包或独立 Skill 后，请同步更新调用命令、脚本和本地引用。

| 2.x 名称 | 3.0.0 名称 |
| --- | --- |
| `build-goals` | `agent-build-kit` |
| `shape-idea` | `clarify-idea` |
| `health-check` | `audit-agent-setup` |
| `build-docs` | `build-dev-docs` |

3.0.0 将仓库地址和完整分发包标识从 `koco-co/build-goals` 改为 `koco-co/agent-build-kit`；发布前需先在 GitHub 完成仓库重命名。本地旧版本不会自动改名；请卸载旧分发包并按上方命令安装 3.0.0。

## 仓库结构

```text
agent-build-kit/
├── .agents/plugins/marketplace.json
├── .claude-plugin/
├── .codex-plugin/
├── .zcode-plugin/
├── scripts/install_skill.py
├── scripts/sync_distributions.py
├── skills/
├── tests/
├── AGENTS.md
├── CLAUDE.md
├── LICENSE
└── package.json
```

跨 Skill 共享文件由 `.plugin-shared-files.json` 声明。修改规范源后，使用同步脚本检查或刷新普通文件副本：

```bash
python3 skills/build-plugin/scripts/sync_shared_files.py --root .
python3 skills/build-plugin/scripts/sync_shared_files.py --root . --write
```

## 验证

四端同步脚本会合并执行以下发布前门禁：共享文件镜像、全平台 Plugin、Skill 评测资产、完整回归测试和 Git 空白检查。

验证完整的四平台分发包：

```bash
python3 skills/build-plugin/scripts/validate_plugin.py \
  . \
  --platform all \
  --strict
```

验证单个 Skill：

```bash
python3 skills/build-skill/scripts/validate_skill.py \
  skills/clarify-idea \
  --profile dual \
  --plugin-root . \
  --strict
```

静态校验九个 Skill 的触发、排除和关键行为评测资产（不调用模型）：

```bash
python3 scripts/validate_skill_evals.py .
```

运行全部回归测试：

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

静态校验和安装成功不能代替真实客户端行为验证。发布前仍需分别在 Claude Code、Codex、ZCode 和 Pi 中验证发现、调用与更新流程。

## 开发约定

- 项目开发说明以 [`AGENTS.md`](AGENTS.md) 为准。
- `CLAUDE.md` 是只包含 `@AGENTS.md` 的普通文件。
- 工作流文件使用 `§NN-name.md`；模板文件使用 `<name>.template.<ext>`。
- 普通验证不会提交、推送、发布或更新本地 Plugin；只有明确使用 `sync_distributions.py --publish` 时，才会按脚本顺序执行这些动作。

## 许可证

本项目使用 [MIT License](LICENSE)。
