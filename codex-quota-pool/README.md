# codex-quota-pool

一个本地 Codex 多账号额度池 demo，安装后的命令叫 **`cdx`**。按顺序使用已登录账号，额度不足时保存进度、切换账号并继续同一会话。

适用环境：Linux / WSL、Python 3.11+、Codex CLI **0.163.0**。仅依赖 Python 标准库。会话迁移适配固定的 Codex 存储格式，其他版本会在启动时被拒绝。

## 安装与配置

在 `~/project/codex-quota-pool/` 中执行：

```bash
npm install -g @openai/codex@0.163.0   # 已安装该版本则跳过
cp config.example.json config.json
make install
```

`make install` 将 `~/.local/bin/cdx` 链接到本项目的入口。该目录需要在 PATH 中；已有其他同名命令时安装会拒绝覆盖。可用 `make install BIN_DIR=/path/to/bin` 指定安装目录。

编辑 `config.json`：

```json
{
  "accounts": ["codex_main", "codex_alt"],
  "switch_below_percent": 1,
  "poll_seconds": 15,
  "resume_when_available": false
}
```

内置账号目录：`codex_main` → `~/.codex`、`codex_alt` → `~/.codex-account-2`、`codex3` → `~/.codex-account-3`。先在各自目录登录不同账号，例如：

```bash
env CODEX_HOME="$HOME/.codex" codex login
env CODEX_HOME="$HOME/.codex-account-2" codex login
```

自定义目录使用 `account_homes`，代理使用 `proxy_env`：

```json
{
  "accounts": ["work", "personal"],
  "account_homes": {"work": "~/.codex-work", "personal": "~/.codex-personal"},
  "switch_below_percent": 1,
  "proxy_env": {"HTTPS_PROXY": "http://127.0.0.1:7890"}
}
```

代理地址请按本机实际情况填写。可选字段还包括 `sync_seconds`（默认 5）、`query_timeout_seconds`（默认 30）、`codex_binary` 和 `limit_ids`。配置在启动时读取，修改后重启生效。

## 使用

```bash
cd /path/to/your-project
cdx
cdx '修复测试失败并验证结果'
cdx -C /path/to/project -m model-name
cdx status --refresh
cdx status --json
cdx resume <会话UUID>
cdx resume --last                  # 当前项目最近会话
cdx resume                        # 选择当前项目会话
cdx resume --all                   # 跨项目选择
cdx resume <会话UUID> '继续'
```

界面内的 `/plan`、`/fast`、`/model` 和审批交互由原生 Codex 处理。按一次 Ctrl+C 会停止任务、同步进度并退出，随后显示可直接使用的 `cdx resume` 命令。主动暂停后恢复默认等待输入；显式提供消息才会发送新任务。

支持的启动参数见 `cdx --help`。本 demo 只提供启动、`resume` 和 `status`；检查在启动时完成，同步自动进行。旧 `quota-pool` 入口、`pause/sync/doctor/check-config` 子命令及 `resume --from` 接管功能已移除。

默认配置为项目目录中的 `config.json`，运行数据为 `runtime/`，从其他工作目录调用仍使用同一套数据。也可显式指定：

```bash
cdx --pool-config /path/to/config.json --pool-runtime /path/to/runtime
```

## 换号与恢复

- 周额度为 **0%** 时停用账号；周额度仍可用时，只用 **5h** 剩余判断切换阈值。
- 5h 剩余严格低于阈值时按配置顺序寻找接力账号。没有达到阈值的接力账号，就继续用当前账号的剩余额度。
- 当前账号耗尽且没有达到阈值的接力账号时，同步并暂停；`resume_when_available: true` 会等待额度恢复后接续未完成任务。
- 查询失败视为未知，不当作额度耗尽。等待审批或用户回答时暂缓切换。
- 启动时找到首个可用账号就复用其后端，运行中复用连接查询额度；退出时取消查询并回收进程。

换号保持同一会话 UUID、工作目录及权限设置。同步包含会话日志和相关数据库记录，账号凭据和其他会话不会被复制。文件锁、校验及未完成同步记录用于阻止两个账号同时推进或从过期副本恢复。

`runtime/` 内含会话内容和本地后端认证信息，已由 `.gitignore` 排除。异常退出后使用 `cdx resume` 核验并恢复；若提示副本分叉或同步失败，保留数据并检查错误。恢复不会自动重发送达状态不确定的消息。请避免用其他 Codex 客户端同时推进池内会话。

## 代码与测试

五个功能模块：`cli.py` 负责命令和配置，`pool.py` 负责调度，`codex.py` 负责账号及进程通信，`session.py` 负责保存同步，`terminal.py` 负责终端连接。

```bash
make check          # 单元测试，无需安装或登录 Codex
make integration    # 加上真实 Codex 的换号、恢复和终端测试
```

测试集中在 `tests/` 的三个测试文件，共用一个模拟服务文件。集成测试使用隔离的临时账号目录和本地模型服务，不消耗真实账号额度。
