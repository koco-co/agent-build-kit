# Plugin 验证与交付

## 静态检查

```bash
python3 scripts/validate_plugin.py <plugin-root> --platform <all|dual|claude|codex|zcode|pi> --strict
```

脚本已覆盖 Manifest、多平台身份与版本一致性、Skill 质量与 Frontmatter、共享镜像（存在、非软链接、与规范源一致且不越界）、必要链接、空文件、失效引用及 Claude Marketplace。`all` 仅适用于同时提供 Claude Code、Codex、ZCode 与 Pi 四端入口的完整分发包；部分平台使用 `dual`（Claude Code + Codex）或 claude/codex/zcode/pi 单个平台名。清单只处理脚本无法判断的内容与场景。

## 平台检查

Claude Code：

```bash
claude plugin validate <plugin-root> --strict
claude --plugin-dir <plugin-root>
```

进入后验证命名空间调用、目标 Skill 的调用权限和 `/reload-plugins`。

Codex：验证 `.codex-plugin/plugin.json`；确认 Marketplace 能解析并列出 Plugin；在支持 Plugin 的客户端完成安装；按每个 Skill 的设计验证调用权限；检查 `agents/openai.yaml`。

ZCode：验证 `.zcode-plugin/plugin.json`；在 **Settings → Plugin Management** 安装，确认 Skills 出现在列表中；用自然语言请求验证触发。

Pi：

```bash
pi install <package-path-or-source>
pi list
```

启动交互会话确认 Skills 被发现，用 `/skill:<name>` 验证用户调用，并按设计验证模型调用策略。本地路径、Git 和 npm 安装只验证目标实际采用的方式。

## 场景验收

先执行 `checklists/plugin-design-review.md` 与 `checklists/plugin-semantic-acceptance.md`。至少覆盖：

1. 新建 Plugin；
2. 升级已有 Plugin；
3. 仓库迁移；
4. 多平台共用组件；
5. Skill 委派；
6. 共享镜像缺失、内容不一致、被软链接替代，以及失效或越界的必要链接；
7. 安装、更新和失败回滚；
8. 每个 Skill 的实际调用行为与平台配置一致。

其余场景遵循 `rules/skill-quality-standard.md` 的决策与确认原则。

结果分别记录：已验证；静态检查通过但未真实运行；未验证；无法完成的内容和原因；失败后已修复并复验。

完成条件：所有静态检查通过，关键路径有实际结果，未运行的平台没有被描述为已通过。Plugin 包含新建、整体重构或改变触发、Frontmatter、权限与平台行为的 Skill 时，还必须完成 `build-skill` 规定的内容审查、文案审查、内容回归和独立 Reviewer 复查。

## 交付

使用 `templates/plugin-delivery-report.template.md`。报告要让用户能回答：

- 最终交付了什么，哪些没有做；
- 分发包在 Claude Code、Codex、ZCode 与 Pi 中如何发现、安装和调用；
- 哪些文件是规范源，哪些是平台适配或共享镜像，规范源在哪里，保留了哪些必要链接；
- Plugin 中的 Skills 是否通过 `build-skill` 规范；
- 实际运行了哪些命令；
- 哪些结论来自真实客户端，哪些只是静态检查；
- 当前版本是否已提交、推送、发布或仅在本地；
- 存在哪些未验证项或阻塞项。

### 受控调用

由 `audit-agent-setup` 等上层 Skill 统筹时，不重复询问 commit、push、Marketplace、Release、发布、部署或本地 Plugin 更新，也不自行执行。向统筹 Skill 返回：修改内容与确认依据；静态校验、安装、真实客户端与 Skill 子任务的验证证据；提交、版本、Marketplace 与 Release 状态；未验证项；恢复条件。尚未创建提交时写“由上层待生成并回填”。发现新的产品、架构、公开接口、权限或范围决策时暂停，交回统筹 Skill。

### 独立调用

实现和验证完成后，只列出真实适用的动作，并主动询问一次：

```text
实现和验证已经完成。是否执行以下交付动作？
```

候选动作：commit 当前任务变更；push 到明确远端与分支；发布或更新明确存在的 Marketplace；更新并核验 Claude Code Plugin；更新并核验 Codex Plugin；更新并核验 ZCode Plugin（仅本地安装 ZCode 时）；更新并核验 Pi Package（仅目标含 Pi 且本地安装 Pi 时）；创建 Release（仅仓库确实使用且前置条件满足时）。

每项写明真实目标、当前或拟发布版本，并给推荐答案；可以全部或部分授权。目标只支持一个平台时，不列另一平台更新；不存在远端、Marketplace、安装或 Release 流程时，不虚构动作。

用户回答前不执行任何交付动作。收到回答后只执行明确授权部分，按依赖顺序完成并逐项核验；未授权项记录在交付报告中。提问后停止，不自动开始另一个 Plugin、发布 Marketplace、创建 Release 或适配其他 Coding Agent。
