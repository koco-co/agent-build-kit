---
name: rename-codex-sessions
description: 仅在需要依据当前 Codex Desktop 本地项目中的实际对话，为符合范围的 session 生成并批量改名时使用；不用于修改项目名称、对话内容、项目归属、排序、置顶或归档状态，也不用于普通标题建议。
license: MIT
compatibility: 需要 Python 3.9+、可调用 Codex App Server，以及 Codex Desktop 本地项目状态文件。
disable-model-invocation: true
metadata:
  author: koco-co
  version: "1.0.1"
---

# Outcome

只为当前 Codex Desktop 本地项目中已归属的主对话整理简洁标题；先进行只读改名能力预检，再展示唯一的候选表，确认后只调用线程改名接口。

## Routing

- 进入条件：用户要求处理当前 Codex Desktop 本地项目中的对话标题，并保留项目和会话的其他状态。
- 枚举范围：包含已归属本地项目的主对话，包含未归档和已归档线程；排除 projectless（无项目）线程、`exec` 记录和 `subAgent` 子线程。
- 改名范围：只处理脚本预检标记为 `renameable` 的线程；标记为 `no_rollout` 或 `unknown` 的线程保留原名，不进入确认后的改名映射。
- 退出条件：无法读取项目归属、无法调用 App Server、无法读取对话内容，或无法可靠提炼主题时保持原名并停止对应线程；不猜测。

## Steps

1. 读取 `scripts/codex_sessions.py` 的帮助并运行 `list`。脚本只读取本地项目归属、线程元数据和 Rollout 路径，并为每个候选返回 `renameStatus`：`renameable`、`no_rollout` 或 `unknown`。当前 Codex App Server 对已归档线程的 `thread/name/set` 会返回 `no rollout found`，因此已归档线程标记为 `no_rollout`；缺少或找不到 Rollout 时按脚本结果处理。候选日期必须来自返回的 `createdAt`，按 `Asia/Shanghai` 转换为 `MMDD`，不得使用 `updatedAt`。
2. 只对 `renameStatus=renameable` 的线程运行 `content --thread-id <id>`，根据用户消息和相关助手消息提炼实际主题。项目名称只能用于排除主题重复，不得写入新标题；无法判断主题时保留原名，内容不足、主题不明确或类型无法判断时不猜测。`no_rollout` 和 `unknown` 线程不读取内容、不生成映射，保留原名。
3. 为主题和类型均可判断的可改名线程生成标题，格式必须是 `MMDD｜类型｜主题`。类型只使用 `功能`、`设计`、`修复`、`优化`、`发布`、`探索`、`文档`、`研究`；主题要具体、简洁、适合左侧栏，不重复项目名称。

   - `优化批次文字显示` → `0903｜优化｜批次文字显示`
   - `整合快捷键提示页面` → `0902｜功能｜整合快捷键提示页`
   - `提交代码到 GitHub` → `0813｜发布｜提交代码到GitHub`
   - `新功能讨论` → `0901｜设计｜界面对齐检查`

4. 执行前只输出一个两列表格，不加解释、统计、代码围栏或其他文本；表头必须严格为：

   `| 原名称 | 新名称 |`

   表格只包含预检可改名的线程；主题无法判断的线程在两列中保留原名。`no_rollout` 和 `unknown` 线程不放入表格，保留原名并由脚本结果报告跳过原因。没有可改名线程时只输出表头。输出表格后停止，等待用户确认，不得提前调用 `apply`。
5. 只有收到用户对该表的明确确认后，才把实际需要变化的 `threadId` 到新标题映射通过以下命令传给脚本，并带上 `--confirmed`：

   ```bash
   python3 <skill-root>/scripts/codex_sessions.py apply --confirmed <<'JSON'
   {"<thread-id>": "0903｜优化｜批次文字显示"}
   JSON
   ```

   脚本会重新核对线程仍属于本地项目主对话和 `renameStatus`，并在任何写入前校验全部新标题；已变为 `no_rollout` 或 `unknown` 的线程不调用写入接口。结果中的 `changed` 只表示服务端确认成功，`unchanged` 表示无需写入，`skipped` 表示预检不可执行且原名保留，`failed` 表示 `thread/name/set` 实际返回错误。`changed` 可以与 `failed` 同时出现；脚本不会回滚已经成功的线程，存在 `failed` 时以非零状态退出。仅报告脚本返回的修改结果；不复述候选表，不追加无关说明。

## Guardrails

- 只用 `createdAt` 计算日期；不得以 `updatedAt` 替代、排序或修正日期。
- 脚本的 `list`、`content` 和改名能力预检只读；预检不得用 `thread/name/set` 试错。`apply` 的唯一写入方法是 `thread/name/set`。不得调用项目改名、线程归属、`thread/metadata/update`、归档、置顶、删除或内容编辑接口。
- 不直接写入 Codex Desktop 状态文件；不要修改项目名称、对话内容、项目归属、排序、置顶或归档状态。
- 用户未确认候选表、项目状态无法核对、预检状态为 `no_rollout` 或 `unknown`、内容不足或主题不确定时，不执行改名；保留原名。

## References

- 需要执行线程枚举、内容读取或改名时，读取并调用 `scripts/codex_sessions.py`；不要在提示词中复制 JSON-RPC 实现。
