# Plugin 实施

## Phase 1：记录实施前的状态与授权范围

实施前记录当前分支、工作区状态、Manifest 版本、现有安装接口和可回滚点。提交、推送、发布、删除和权限变更需要独立授权。

## Phase 2：实现共享核心

按已确认设计创建或更新 Skills、Agents、Hooks、MCP、UI、脚本和资源：

- 复用已有项目能力；
- 不复制业务实现；
- 不创建空目录和未来占位；
- 确定性工作交给脚本；
- 每个组件保持单一职责；
- 每个外部副作用都有明确入口。

## Phase 3：建立共享镜像

跨 Skill 运行依赖在共享文件清单中声明唯一规范源和镜像目标。先显式同步，再执行只读检查：

```bash
python3 <build-plugin-skill-dir>/scripts/sync_shared_files.py --root <plugin-root> --write
python3 <build-plugin-skill-dir>/scripts/sync_shared_files.py --root <plugin-root>
```

两条命令都必须成功；第二条命令只做检查，用于确认同步后的镜像文件均存在、未使用软链接、路径没有越界，且内容与规范源一致。

## Phase 4：写入平台配置

Claude Code：

```text
.claude-plugin/plugin.json
```

Codex：

```text
.codex-plugin/plugin.json
```

ZCode：

```text
.zcode-plugin/plugin.json
```

Pi：

```text
package.json
```

组件仍位于分发包根目录。Plugin Manifest 与 `pi` Manifest 的路径使用 `./` 开头的相对路径，不把 Skills、Hooks 或资源塞进平台配置目录。

## Phase 5：同步文档和版本

更新 README、版本、安装命令、调用方式、变更说明和验证命令。各平台 Plugin Manifest 与 Pi Package 的身份和版本保持一致，除非设计明确说明例外。

完成条件：设计中的全部组件已经实现，路径和版本一致，没有未授权副作用。
