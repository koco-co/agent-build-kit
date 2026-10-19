# Plugin 架构规则

## 1. Plugin 是分发边界

Plugin 负责组织可安装、可升级的能力包。它可以包含 Skills、Agents、Hooks、MCP、UI、脚本和资源，但不应把所有逻辑堆进一个 `SKILL.md`。

## 2. 组件职责

- Skills：模型驱动的工作流；
- Agents：独立角色和受控子任务；
- Hooks：固定事件自动执行；
- MCP：外部工具和数据；
- UI：MCP 资源的交互呈现；
- scripts：确定性转换和验证；
- Manifest：身份、版本、发现路径和平台元数据；
- Marketplace：插件目录与安装策略；
- CI：每次变更都必须通过的自动检查。

同一职责只保留一个权威实现。

## 3. 根目录布局

```text
<plugin-root>/
├── .claude-plugin/
│   ├── marketplace.json # 按需；ZCode 也读取该文件
│   └── plugin.json
├── .codex-plugin/plugin.json
├── .agents/plugins/marketplace.json # Codex Marketplace，按需
├── .zcode-plugin/plugin.json # 目标含 ZCode 时按需
├── package.json # Pi Package 的 Manifest，目标含 Pi 时按需
├── skills/
├── agents/          # 按需
├── hooks/           # 按需
├── .mcp.json        # 按需
├── .app.json        # Codex / ChatGPT 按需
├── assets/          # 按需
└── scripts/         # 按需
```

平台专属配置目录只放该平台规定的配置；组件留在 Plugin 根目录。

## 4. 单一规范源

多平台共用的 Skills、规则、模板和脚本只维护一份。允许的复用顺序：

```text
同一路径直接共用
→ 清单声明的普通镜像，并由脚本同步和校验
→ 构建临时产物时安全生成平台副本
→ 最后才考虑平台独立实现
```

普通镜像不成为第二个规范源。只有平台契约确实不同，才维护独立实现。

## 5. 最小结构

不要求 Plugin 包含全部目录。没有真实用途的目录、空文件、未来占位和示例配置不进入最终实现。
