# 通用 Skill 示例：`api-contract-review`

本示例展示设计粒度，不代表必须复制这些目录或内容。

## 场景

用户希望构建一个可在不同项目中复用的 Skill，用于审查 OpenAPI 契约中的兼容性、命名、错误模型和分页规范，并输出 Markdown 报告。

## 已确认契约

- 类型：通用 Skill；
- 输入：一个或多个 OpenAPI YAML/JSON 文件；
- 输出：结构化 Markdown 报告和机器可读 JSON 结果；
- 副作用：默认只读，不自动修改契约；
- 调用权限：仅限用户调用，由平台配置控制，不在 Skill 正文重复说明；
- 验收：Schema 解析、规则检查、样例契约与语义审阅。

## Frontmatter 字段决策矩阵

| 字段或配置 | 结论 | 理由 |
| ---------- | ---- | ---- |
| `name`、`description` | 添加 | 通用必填字段 |
| `disable-model-invocation: true` | 添加到 Claude Code 源 | 审查时机由用户控制 |
| `agents/openai.yaml` | 添加 | Codex 禁止模型隐式调用并提供展示信息 |
| `compatibility` | 省略 | 没有通用 Skill 自身无法处理的硬性环境要求 |
| `argument-hint` | 添加到 Claude Code 源 | 用户需要传入一个或多个契约路径 |
| `metadata` | 省略 | 没有注册表或安装器需要读取这些信息 |

## 推荐结构

```text
api-contract-review/
├── SKILL.md
├── workflows/
│   ├── §01-inventory.md
│   ├── §02-review.md
│   └── §03-delivery.md
├── rules/
│   └── contract-rules.md
├── scripts/
│   └── validate_contract.py
├── templates/
│   ├── review.template.md
│   └── findings.template.json
├── examples/
│   └── review.example.md
└── checklists/
    └── semantic-review.md
```

章节按内容需要保留：本示例因有独立分支和红线，使用 `Outcome / Routing / Steps / Rules / References`；没有独立分支时删除 `Routing`，没有红线时删除 `Rules`，没有附属文件时删除 `References`，都属合法形态。

## 设计理由

- OpenAPI 解析、引用解析和确定性规则交给 `validate_contract.py`；
- 报告字段由模板固定；
- 结果措辞和问题粒度参考完整示例；
- API 语义、风险优先级和改进建议由语义清单约束；
- 工作流只编排输入清点、机械检查、语义审阅和交付；
- 不创建 `prompts/`，因为该场景不需要 Subagent；
- 不创建 `references/`，因为所有内容已经有明确专用目录。

## 按需读取

| 条件         | 读取或执行                                                   |
| ------------ | ------------------------------------------------------------ |
| 收到契约文件 | `workflows/§01-inventory.md`                                 |
| 开始审查     | `rules/contract-rules.md`、`scripts/validate_contract.py`    |
| 生成报告     | `templates/review.template.md`、`examples/review.example.md` |
| 完成交付前   | `checklists/semantic-review.md`                              |

## 验收场景

1. 有效契约无错误退出；
2. `$ref` 失效时返回非零退出码和准确路径；
3. 删除已有响应字段被判定为破坏性变化；
4. 只要求审查时不修改输入文件；
5. 普通 API 问答不会误触发该 Skill；
6. Markdown 与 JSON 报告中的问题编号一致。
