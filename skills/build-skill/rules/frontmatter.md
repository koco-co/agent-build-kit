# Frontmatter 设计规则

Frontmatter 只放目标平台会读取的元数据和调用策略。每个字段都要有真实用途；平台默认行为已经满足需求时，不重复声明默认值。

## 1. 字段决策矩阵

先根据已确认行为找字段，不要求把整张表填满。没有对应特征的字段直接省略。

| Skill 特征 | 字段 | 判断规则 |
| --- | --- | --- |
| 所有 Skill | `name` | 必填，使用 kebab-case，并与目录名一致 |
| 所有 Skill | `description` | 必填，写清能力、触发条件、排除条件和相邻边界 |
| 有分发或第三方内容要求 | `license` | 有明确要求时添加 |
| 有硬性环境要求 | `compatibility` | 只写目标产品、运行时、系统软件或网络等必要条件 |
| 仓库或安装器会读取 | `metadata` | 有真实消费方时添加 |
| 需要临时预授权工具 | `allowed-tools` | 通用 Agent Skills 字段；Claude Code 用它做临时预授权，Codex 副本保留，完成权限评估后添加 |
| 需要临时禁用工具 | `disallowed-tools` | 仅 Claude Code；Skill 活跃期间必须禁用时添加 |
| 只允许用户调用 | `disable-model-invocation: true` | Claude Code、Pi、DSH 支持；副作用或执行时机必须由用户控制 |
| 只允许模型调用 | `user-invocable: false` | Claude Code、DSH 支持；只提供背景知识且不适合作为命令 |
| 需要补充触发语境 | `when_to_use` | Claude Code 使用；DSH 读取 `whenToUse` 但不展示在目录中，不能依赖它承担触发 |
| 只在特定文件生效 | `paths` | 仅 Claude Code；按 Glob 匹配 |
| 需要参数提示 | `argument-hint` | 仅 Claude Code；只改善调用界面 |
| 需要访问位置参数 | `arguments` | 仅 Claude Code；按顺序声明调用参数 |
| 需要隔离上下文 | `context: fork` | 仅 Claude Code；任务应在独立 Subagent 上下文运行 |
| Fork 需要指定 Agent | `agent` | 仅 Claude Code；与 `context: fork` 配合 |
| Fork 必须等待结果 | `background: false` | 仅 Claude Code；与 `context: fork` 配合 |
| 需要固定模型或推理强度 | `model`、`effort` | 仅 Claude Code；有可验证理由时添加 |
| 需要 Skill 级 Hooks 或 Shell | `hooks`、`shell` | 仅 Claude Code；事件或命令确实随 Skill 生命周期生效 |
| Codex 展示或调用策略 | `agents/openai.yaml` | 只放 `interface` 和 `policy`，不复制工作流 |

设计方案只记录必填字段、拟新增或保留的可选字段，以及用户明确要求审查的字段；每项写明目标平台和依据。

## 2. `description` 与调用策略

- `description` 是模型路由的主要依据。用祈使句写清“做什么、何时用、何时不用”，并点出相邻 Skill 的边界；不要只写内部实现。
- DSH 的模型目录只展示 `name` 与 `description`，默认截断到 500 字符；触发条件必须放进 `description`，不能只写在 `whenToUse` 或正文里。
- 允许模型调用时，在跨平台 `description` 中写清触发与排除条件；仅限用户调用时，由 Frontmatter 或 `agents/openai.yaml` 限制，不在正文重复权限说明。
- 调用策略变化属于行为变化，必须来自明确需求或已确认设计，并验证应触发、不应触发和显式调用场景。
- 多平台 Skill 不依赖 Claude Code 的 `when_to_use` 承担唯一触发语义。ZCode 会把 `when_to_use` 与截断后的 `description` 一并交给模型；Pi 读取 `disable-model-invocation`，忽略其他不识别的字段；DSH 容忍未知字段，但只把 `name` 和 `description` 放进模型目录。

## 3. `compatibility`

默认省略。只有存在以下硬性条件时才填写：

- 必需的目标产品或运行时及最低版本；
- 必需的系统命令、软件或硬件；
- 必需的互联网访问；
- Skill 无法自行携带、安装或安全降级的环境条件。

推荐写法：

```yaml
compatibility: 需要 Python 3.9+ 运行内置校验脚本。
```

```yaml
compatibility: 需要 Git、Docker 和互联网访问。
```

不要写入：

- 笼统的平台支持说明；
- “当前”“目前”等容易过时的描述；
- Skill 会读写哪些文件；
- 调用权限、用户确认要求和副作用；
- 只在部分分支中可能用到的工具；
- 已由 Manifest、README 或正文维护的信息。

## 4. 平台隔离

多平台共用源可以包含 Claude Code 字段和 `agents/openai.yaml`，但独立安装产物要按平台隔离：

```text
Claude Code：保留通用字段和 Claude Code 字段，移除 agents/
Codex：只保留通用 Agent Skills 字段，保留 agents/openai.yaml
ZCode：保留全部字段（未识别的键被忽略），移除 agents/
Pi：保留全部字段（未识别的键被忽略），移除 agents/
DSH：保留全部字段（未识别的键被忽略），移除 agents/
```

不要把未知字段直接当作跨平台字段。平台规范变化后，先更新字段分类、安装转换和测试，再在 Skill 中使用新字段。

## 5. 完成标准

- 每个保留或新增字段都有真实依据；
- 默认值和装饰性字段已经省略；
- 平台专属字段只进入对应安装产物；
- 实际使用的调用权限、参数、工具授权和上下文行为有场景验证；
- `compatibility` 只包含仍然有效的硬性环境要求。
