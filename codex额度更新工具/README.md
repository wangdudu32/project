# Codex 多账号额度监测

监测多个 Codex 账号，在 5 小时剩余额度为 100% 时自动执行一个小任务，再按额度刷新时间循环检查。

## 快速开始

需要 Linux 或启用 systemd 的 WSL、Python 3.10+，以及已通过 ChatGPT 账号登录的 Codex CLI。后台服务使用 `systemctl --user`。

在项目目录执行以下命令。将 `YOUR_MODEL_ID` 换成账号可用的模型，`--home` 指向已登录的 Codex 目录。如需代理，请先配置当前终端的代理环境，初始化时会保存。

```bash
# 1. 初始化并添加账号
./quota-watch init
./quota-watch add account-a --home "$HOME/.codex" --model 'YOUR_MODEL_ID'

# 2. 安装后台服务
./quota-watch prepare-service
mkdir -p "$HOME/.config/systemd/user"
install -m 0644 systemd/codex-quota@.service "$HOME/.config/systemd/user/codex-quota@.service"
systemctl --user daemon-reload

# 3. 启动监测
./quota-watch start account-a
```

使用多个账号时，重复 `add`，为每个账号指定不同名称和独立的登录目录，再分别启动。

## 常用命令

```bash
./quota-watch check account-a       # 实时查看一个账号的额度
./quota-watch status --all          # 实时查看所有账号
./quota-watch start account-a       # 启动监测
./quota-watch stop account-a        # 停止监测
./quota-watch logs account-a        # 查看日志
```

`start` 同时启用用户服务自动启动，`stop` 同时取消。手动查询不会执行小任务。

## 运行规则与配置

- 北京时间每天 **08:00—22:00** 自动工作，夜间暂停。
- 满额时生成一条 Python 技巧，60 秒后复查，每个额度周期最多尝试 3 次。
- 额度不足 100% 时，等服务端刷新时间后 60 秒再检查。
- 查询或任务失败时，每 5 分钟重试；夜间顺延到次日 08:00。
- 电脑休眠、关机或 WSL 关闭期间不执行，恢复后不补跑错过的周期。

账号、模型和代理等设置保存在 `config.json`，结构见 [配置示例](config.example.json)。修改前停止对应账号，改完再启动。

真实配置、运行日志和任务结果仅留在本机，不要提交到 GitHub。
