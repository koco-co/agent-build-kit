# Plugin 设计与关键决策

## 先澄清真正未决的选择

只有同时满足以下条件才提问：

1. 无法从需求、仓库、环境或平台文档中确定；
2. 用户此前没有回答；
3. 不同答案会改变结构、权限、安装、发布或验收结果。

没有真实未决事项时，写明“无待确认决策”，直接设计。每轮只问一个主要问题，给出推荐、原因和其他选择的影响：

```markdown
### 问题：<需要决定的事项>

**推荐：** <推荐选择>

**原因：**
<为什么更适合当前目标>

**其他选择的影响：**

- <选择 A>：
- <选择 B>：
```

常见目标平台包括 Claude Code、Codex、ZCode、Pi；只声明本次需要的平台。

常见决策包括：目标平台组合；Skills-only、MCP-only、混合型或包含 Hooks、Agents、UI；新建、升级、迁移或包装已有组件；用户级、项目级、Marketplace 或公开发布；认证、网络、数据和权限边界；版本兼容与破坏性迁移；是否需要真实客户端测试；哪些 Skill 已存在，哪些交给 `build-skill`；哪些文件共用、镜像或平台独立。

完成条件：实现范围、平台差异、权限和验收标准都能被唯一解释。

## 再确定插件形态

选择最小可用形态：Skills-only、MCP-only、Skills + MCP、Skills + Hooks/Agents、Skills + MCP + UI、已有仓库迁移、多平台封装。只纳入当前需要的组件。

逐项判断职责：

- Skill：模型驱动、可复用的工作流；
- Agent：具有独立角色、工具和返回格式的子任务；
- Hook：必须由固定事件自动触发的行为；
- MCP：外部工具、服务或数据接入；
- UI：需要交互呈现的 MCP 资源；
- CLI/script：可确定性执行的转换和校验；
- Manifest：身份、组件路径和平台元数据；
- CI：每次提交都必须执行的自动检查。

## 设计平台层

多平台方案必须：

- 核心组件只维护一份；
- `.claude-plugin/plugin.json` 只描述 Claude Code 差异；
- `.codex-plugin/plugin.json` 只描述 Codex 差异；
- 目标包含 ZCode 时增加 `.zcode-plugin/plugin.json`；目标包含 Pi 时在 `package.json` 中声明 `pi.skills`；
- 多平台分发的名称、版本和 Skills 规范源保持一致；
- 跨 Skill 运行依赖使用清单声明的普通镜像，并说明如何同步和校验；
- 无法等价实现的能力明确分支或降级。

只设计当前方案实际需要的文件，不为未采用的平台入口、组件或目录创建占位结构。平台配置按需读取 `templates/claude-plugin.template.json`、`templates/codex-plugin.template.json`、`templates/zcode-plugin.template.json` 或 `templates/pi-package.template.json`；模板只提供字段结构，不扩大组件范围。

## 落实方案

用 `templates/plugin-design-proposal.template.md` 汇总目标、分支、目录、组件职责、Skill 委派、权限、平台、安装发布、验证、实施范围和回滚；不在本工作流重复模板字段。

用户要求先看设计时，输出后只请求一次实施确认。存在会改变 Plugin 形态、平台、权限或验收的未知选择时，说明差异和推荐方案后询问。明确的创建、升级或迁移请求且无未决选择时直接实施。
