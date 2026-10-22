# 怎样在本机或 VPS 部署 LessonWeave

LessonWeave 提供本机工作台和受保护的 VPS 服务两种部署方式；本机安装器负责创建虚拟环境、安装依赖并启动工作台；VPS 安装脚本会把当前仓库安装为 systemd 服务，并让服务只监听本机回环地址

## 本机怎样安装并启动工作台

准备 Python 3.11 或更新版本；若系统还没有 Codex CLI，再准备 Node.js 20 或更新版本，让安装器安装官方 CLI；网页归档需要 Docker 正在运行；需要英译中翻译时，请在当前终端环境或 `.env` 中设置 DeepSeek 官方密钥

在仓库根目录运行：

```bash
# 安装依赖并启动本机工作台
python deploy/bootstrap.py
```

首次运行会创建仓库内的 `.venv`、安装 LessonWeave 及 PDF 依赖、按需安装浏览器组件，并检查 Codex CLI 登录状态；若 CLI 还未登录，安装器会启动设备登录流程；完成后，浏览器访问 `http://127.0.0.1:8960/workspace`

安装器默认使用 Docling 处理 PDF；电脑资源有限时可以改用较轻的 PyMuPDF 路径：

```bash
# 切换到 PyMuPDF PDF 路径后安装依赖并启动工作台
python deploy/bootstrap.py --without-docling
```

只安装依赖而暂时不启动工作台：

```bash
# 安装依赖但暂时不启动工作台
python deploy/bootstrap.py --install-only
```

需要更换端口时使用 `--port`，例如 `python deploy/bootstrap.py --port 8970`；如果浏览器组件已经安装，可以用 `--skip-browser` 跳过本次安装

配置文件可放在仓库根目录未跟踪的 `.env` 中，或由当前 shell 设置环境变量；安装器读取 `.env` 时会保留 shell 已有的值；默认数据目录是当前操作系统用户的 `~/.lessonweave`；设置 `LESSONWEAVE_DATA` 可以指定其他持久目录；不要把 `.env`、访问令牌或模型密钥提交到 Git

## 怎样另建 ReadWeave 并接入工作台

ReadWeave 由独立源码包和 Docker 数据卷运行；部署器不会调用生成模型，也不会伪造 ReadWeave 登录或模型凭据；如果你已经有带 LessonWeave 桥接的 ReadWeave 实例，安装器会检查并复用它，不会再启动一套

当前分支请下载[阅读修复版源码包](https://github.com/AIALRA-0/AIALRA-LessonWeave/releases/download/v0.2.0/readweave-source-reader-followup-20261022.tar.gz)，保存为 `readweave-source.tar.gz`，然后在仓库根目录运行；归档 SHA-256 为 `560945276b663e2038b48301eca8975fc4430051ad0bab712f8e758f064ad23a`，其中 34 项桥接源码与仓库 `backend-source-manifest.json` 对应，旧提交仍使用版本页中的旧包：

```bash
# 从公开源码包构建独立 ReadWeave，并只绑定本机回环地址
python deploy/bootstrap.py --readweave-source ./readweave-source.tar.gz --readweave-port 18961
```

安装器会校验归档中的桥接文件，使用 Docker 构建 ReadWeave，并把原生数据保存在独立的 `lessonweave-readweave-data` 数据卷；服务只映射到 `127.0.0.1:18961`；健康检查通过后，安装器会把本机网址写入未跟踪的 `.env`，但会让 LessonWeave 桥接保持关闭

浏览器打开 ReadWeave 根页面 `http://127.0.0.1:18961/`，按单页应用显示的首次引导步骤创建账号和初始数据。`/bootstrap` 是用于检查启动状态的接口，首次设置前应返回 `dbInitialized=false`；不要把它当作设置页面直接打开。登录后在 ReadWeave 中创建 ETAPI token；部署器不会代替用户登录，也不会重置已有账号、令牌或库内容

完成首次设置后，运行下列命令；脚本会在终端隐藏输入 token，确认 ReadWeave 提供兼容的 `version=1`、`schemaVersion=1.2` 桥接接口，再确认或幂等创建 LessonWeave 根目录与回收站；通过检查后，脚本才把两组环境变量写成同一网址和令牌并启用桥接；如果私有环境文件已经保存这两个目录 ID，脚本会先验证并沿用：

```bash
# 隐藏输入 ETAPI token，并配置正式库所需的目录
python deploy/readweave_bootstrap.py --configure-token
```

Unix 系统会把保存 token 的环境文件权限设为 `600`；Windows 用户应确保 `.env` 只允许自己的账户读取；配置写好后，重启 LessonWeave 工作台，让应用重新读取 `.env`

如果已经有带 LessonWeave 桥接的 ReadWeave 实例，把私有环境文件中的 `LESSONWEAVE_READWEAVE_URL` 与 `LESSONWEAVE_READWEAVE_TOKEN` 设为同一实例；兼容旧 provider 的 `LESSONWEAVE_TRILIUM_URL` 和 `LESSONWEAVE_TRILIUM_TOKEN` 也必须指向同一实例。你运行本机安装器或 VPS 安装脚本时，只要这两组配置完整，部署器就会验证并复用现有实例、确认桥接版本、沿用或创建 LessonWeave 根目录与回收站，不启动重复容器；手动完成这些配置时，也可以运行 `python deploy/readweave_bootstrap.py --configure-token` 完成同一检查。已有实例无法通过健康、桥接或 ETAPI 检查时，脚本会停止，不会另建空库

`--dry-run` 只检查源码包和配置并显示计划，不启动容器、不写 token：

```bash
# 检查公开源码包和本机部署计划，不改变环境
python deploy/readweave_bootstrap.py --source ./readweave-source.tar.gz --dry-run
```

健康检查只说明原生服务能够响应，桥接能力检查只说明接口版本匹配；它们都不能代替完整生成、发布和回读的端到端验证。适配器当前支持的行为及每项验证状态，见[ReadWeave 交接说明](../integrations/readweave/HANDOFF.md)

## 怎样在 Ubuntu 或 Debian VPS 安装服务

先在服务器上取得 LessonWeave 仓库，然后从仓库根目录运行安装脚本：

```bash
# 在已取得的 LessonWeave 仓库内安装并启动 VPS 服务
sudo bash deploy/install-vps.sh
```

脚本会安装 Python、Node.js、Docker 和项目依赖，配置 systemd 服务，并让应用监听 `127.0.0.1:18960`；项目数据保存在 `/var/lib/lessonweave`，服务配置保存在权限为 `600` 的 `/etc/lessonweave.env`；服务单元从当前仓库路径启动，因此升级时应先备份数据，再更新仓库并重启 `lessonweave.service`

首次安装后，编辑 `/etc/lessonweave.env`，设置 `LESSONWEAVE_OWNER`、`LESSONWEAVE_CODEX` 和需要的翻译凭据；该文件从 `.env.example` 初始化，不能保留示例所有者值；服务使用的 Codex CLI 也必须完成登录；请以服务运行账号完成 CLI 的官方登录流程，再重启服务；不要把登录令牌或 API 密钥贴进终端记录、公开工单或仓库文件

如果你要另建独立 ReadWeave，可以在同一次 VPS 安装中提供公开源码包：

```bash
# 安装工作台并构建一个只监听 VPS 本机回环地址的 ReadWeave
sudo bash deploy/install-vps.sh --readweave-source ./readweave-source.tar.gz --readweave-port 18961
```

ReadWeave 使用独立 Docker 数据卷，并且不会对公网开放 `18961`；远程完成原生首次设置时，可从自己的电脑建立 SSH 隧道，再在本机浏览器打开对应回环网址：

```bash
# 把 VPS 的本机 ReadWeave 端口转到当前电脑的 18961 端口
ssh -L 18961:127.0.0.1:18961 your-vps
```

完成 ReadWeave 原生设置并创建 ETAPI token 后，在 VPS 上运行下面的命令；token 通过隐藏输入传入，不会出现在命令行参数中；脚本会沿用私有环境文件中已有的根目录和回收站 ID，或幂等创建这两个目录；随后重启 LessonWeave 服务：

```bash
# 把同一 ReadWeave 实例写入权限受限的服务环境文件
sudo python3 deploy/readweave_bootstrap.py --configure-token --env-file /etc/lessonweave.env
sudo systemctl restart lessonweave.service
```

若 VPS 已经配置带 LessonWeave 桥接的 ReadWeave 实例，可不提供 `--readweave-source`；安装脚本会检查 `/etc/lessonweave.env` 中的网址和令牌，复用同一实例，不启动重复容器，并验证桥接版本，再确认或创建 LessonWeave 根目录与回收站；两个网址变量和两个令牌变量需要指向同一个实例

VPS 服务默认启用身份校验；请让 LessonWeave 只通过已经配置 TLS 和认证的反向代理访问；认证成功后，代理必须用可信登录名覆盖客户端可能伪造的 `X-Aialra-User` 请求头，该身份必须与 `LESSONWEAVE_OWNER` 完全一致；未通过认证的请求应由代理拒绝，直接访问 `18960` 和 `18961` 的公网流量应无法到达服务

仓库中的 `deploy/nginx.conf.template` 只提供反向代理结构，不会启用或假造认证；部署者必须填写已有认证系统的 include 路径和它实际提供的已验证用户名变量，并保留服务器上已有的 nginx 配置；变量值要写入 `proxy_set_header X-Aialra-User`，让 nginx 覆盖客户端同名请求头；填完后先运行 `nginx -t`，再按服务器现有流程加载配置

安装和配置完成后检查服务状态：

```bash
# 查看服务状态
sudo systemctl status lessonweave.service
# 查看服务最近的运行记录
sudo journalctl -u lessonweave.service -n 100 --no-pager
```

远程访问请使用自己的 HTTPS 站点地址；不要把示例域名、服务器地址、账号或服务日志中的个人信息放进公开文档

## 部署前后要检查什么

本机或 VPS 都应确认 Codex CLI 已登录，所选模型有可用额度，并且需要的翻译凭据已经通过环境变量提供；首次生成会调用模型并消耗额度；浏览工作台和内置架构视图不需要先生成读本

VPS 上还要确认防火墙不对公网开放 `18960`，外部流量只经过 HTTPS 认证代理；升级前备份数据目录和配置文件；排查问题时只分享经过脱敏的错误摘要，不要公开 `.env`、令牌、账号、机器路径或原始历史记录

本机提交材料及生成读本的步骤见[使用指南](usage.md)，13 阶段的实际数据流见[架构说明](architecture.md)
