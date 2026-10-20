# 1 怎样在本地或 VPS 启动

网站、工作流、Schema、提示词、检查器和阅读器共用本仓库，材料和账号放在仓库外，默认 Sol high 写作、Flash 非推理英译中

## 1.1 怎样在本地一键启动

准备 Python 3.11+、Node.js 20+，网页归档还需要可运行的 Docker；已有 Codex CLI 时继续使用，否则安装器在 .tools 中安装官方 CLI

```bash
# 下载源码并安装独立环境、PDF 解析器和浏览器，然后启动网站
 git clone https://github.com/AIALRA-0/AIALRA-LessonWeave.git
 cd AIALRA-LessonWeave
 python deploy/bootstrap.py
```

首次使用先在官方 CLI 完成 codex login，把 DeepSeek 官方密钥放入环境变量 AIALRA_DEEPSEEK_OFFICIAL_KEY；账号和密钥不写入源码

安装与设备登录方式沿用 [OpenAI 官方 Codex CLI 文档](https://learn.chatgpt.com/docs/codex/cli)和[身份验证说明](https://learn.chatgpt.com/docs/auth)

打开 http://127.0.0.1:8960/workspace，选择网页、PDF 或项目 ZIP 并提交，关闭页面后后台继续处理

安装器读取未跟踪的 .env，已有环境变量优先，默认数据放在用户目录的 .lessonweave 中；--install-only 只安装，--port 修改本地端口，--without-docling 使用保留原页与坐标的 PyMuPDF 路径

## 1.2 怎样在 VPS 一键安装服务

Ubuntu 或 Debian 主机在克隆后的仓库中执行下面命令，脚本安装依赖和 systemd 服务，保留已经存在的 /etc/lessonweave.env

```bash
# 安装服务，只监听服务器本机
sudo bash deploy/install-vps.sh
```

在执行账户中完成 codex login，并在 /etc/lessonweave.env 设置 LESSONWEAVE_OWNER、LESSONWEAVE_CODEX 和翻译密钥，再执行 systemctl restart lessonweave

服务监听 127.0.0.1:18960，deploy/nginx.conf.template 提供反向代理模板，替换域名、证书和现有认证片段后使用 nginx -t 检查并重载；认证代理必须覆盖 X-Aialra-User，应用端口保持回环绑定

PDF 解析使用 CPU，公式保留原图，不启用公式增强；首次使用 Docling 会下载模型，HF_HOME 可指向持久缓存目录

## 1.3 哪些并发值已经生效

正文并发 144，翻译并发 12、每批约 24000 UTF-8 字节，承接每批 16 节、并发 7，修复并发 3，同一进程的 Sol 总额度为 144

默认值保存在 framework/05_writing/runtime-profile.json，环境变量和项目已保存的模型设置仍可覆盖默认值，工作台系统信息显示实际生效配置

项目按提交顺序执行，项目内部并行，服务模板不设置旧的内存、CPU 和进程数量限制，部署者可根据机器承载能力调整并发

## 1.4 怎样升级与恢复

升级前使用 SQLite backup 接口备份数据库，并备份材料、笔记与仓库外配置；把新版本安装到独立目录，再切换服务

已有任务正在执行时保留旧进程，新实例设置 LESSONWEAVE_RECOVER_JOBS=0；没有并行旧进程时使用默认恢复设置，已完成的模型调用可复用

回退时切回旧代码目录，生成数据和笔记继续保留

## 1.5 怎样确认网站可以使用

登录后打开 /workspace，系统信息应显示模型、并发、解析器和可用资源；提交小网页和小 PDF，确认阶段列表更新、正文和原文定位可读、阅读包可下载

每次调用保存输入、输出和缓存 token，缺失用量显示未返回，任务实际经过时间与并行调用累计时间分别统计

