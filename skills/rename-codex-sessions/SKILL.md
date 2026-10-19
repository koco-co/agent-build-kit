---
name: rename-codex-sessions
description: 仅在需要依据当前 Codex Desktop 本地项目中的实际对话，为符合范围的 session 生成并批量改名时使用；不用于修改项目名称、对话内容、项目归属、排序、置顶或归档状态，也不用于普通标题建议。
license: MIT
compatibility: 需要 Python 3.9+、可调用 Codex App Server，以及 Codex Desktop 本地项目状态文件。
disable-model-invocation: true
metadata:
  author: koco-co
  version: "1.1.0"
---

# Outcome

只为当前 Codex Desktop 本地项目中已归属的主对话整理简洁标题。先做只读预检，再展示唯一候选表；用户确认后，才调用线程改名接口。

## Routing

- 进入条件：用户要求处理当前 Codex Desktop 本地项目中的对话标题，并保留项目和会话的其他状态。
- 枚举范围：已归属本地项目的主对话，包含未归档和已归档线程；排除 projectless 线程、`exec` 记录和 `subAgent` 子线程。
- 改名范围：只处理脚本标记为 `renameable` 的线程；`no_rollout` 和 `unknown` 保留原名。
- 退出条件：无法读取项目归属、无法调用 App Server、无法读取对话内容，或无法可靠提炼主题时，保留原名并停止对应线程，不猜测。

## Steps

1. 读取 `scripts/codex_sessions.py` 的帮助并运行 `list`。脚本只读取本地项目归属、线程元数据和 Rollout 路径，返回 `renameStatus`：`renameable`、`no_rollout` 或 `unknown`。日期只取 `createdAt`，按系统本地时区转为 `MMDD`；需要固定时区时加 `--timezone <IANA 时区>`（例如 `--timezone Asia/Shanghai`），不得用 `updatedAt` 代替。
2. 只对 `renameStatus=renameable` 的线程运行 `content --thread-id <id>`，需要与 `list` 相同的固定日期时加 `--timezone <IANA 时区>`；根据用户消息和相关助手消息提炼实际主题。项目名称只用于排除重复，不写入新标题；主题不确定时保留原名。`no_rollout` 和 `unknown` 不读内容、不生成映射。
3. 为可改名线程生成 `MMDD｜类型｜主题`。类型只用 `功能`、`设计`、`修复`、`优化`、`发布`、`探索`、`文档`、`研究`；主题要具体、简洁、适合左侧栏，不重复项目名称。

   - `优化批次文字显示` → `0903｜优化｜批次文字显示`
   - `整合快捷键提示页面` → `0902｜功能｜整合快捷键提示页`

4. 执行前只输出两列表格，不加解释、统计、代码围栏或其他文本；表头严格为：

   `| 原名称 | 新名称 |`

   表格只包含预检可改名的线程；主题无法判断的线程两列都保留原名。`no_rollout` 和 `unknown` 不放入表格，由脚本结果报告跳过原因。没有可改名线程时只输出表头。输出后停止，等待用户确认。
5. 只有用户明确确认该表后，才把实际需要变化的 `threadId` 到新标题映射传给脚本，并带 `--confirmed`：

   ```bash
   python3 <skill-root>/scripts/codex_sessions.py apply --confirmed <<'JSON'
   {"<thread-id>": "0903｜优化｜批次文字显示"}
   JSON
   ```

   脚本会重新核对项目归属和 `renameStatus`，并在写入前校验全部标题。结果字段：

   - `changed`：服务端确认成功；
   - `unchanged`：无需写入；
   - `skipped`：预检不可执行，保留原名；
   - `failed`：`thread/name/set` 返回错误；`changed` 与 `failed` 可能同时出现，脚本不回滚已成功线程，并以非零状态退出。

   只报告脚本返回的修改结果，不复述候选表，不追加无关说明。

## Rules

- 只用 `createdAt` 计算日期；不得以 `updatedAt` 替代、排序或修正日期。
- `list`、`content` 和改名能力预检只读；`apply` 的唯一写入方法是 `thread/name/set`。不得调用项目改名、线程归属、`thread/metadata/update`、归档、置顶、删除或内容编辑接口。
- 不直接写入 Codex Desktop 状态文件，不要修改项目名称、对话内容、项目归属、排序、置顶或归档状态。
- 用户未确认候选表、项目状态无法核对、预检为 `no_rollout` 或 `unknown`、内容不足或无法判断主题时保留原名，不执行改名。

## References

- 线程枚举、内容读取和改名：读取并调用 `scripts/codex_sessions.py`；不要在提示词中复制 JSON-RPC 实现。
