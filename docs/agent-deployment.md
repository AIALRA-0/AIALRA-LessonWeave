# 可交给部署 Agent 的基础提示词

下面的提示词适用于准备把 LessonWeave 部署到一台 Ubuntu 或 Debian VPS 的 Agent；使用前请把方括号中的内容换成自己的实际值；不要把密码、访问令牌或私钥写进提示词

```text
请把 LessonWeave 部署到我授权管理的 Ubuntu 或 Debian VPS

仓库地址：[Git 仓库地址]
服务器登录方式：[已配置的 SSH 别名或连接方式]
公开 HTTPS 域名：[自己的域名]
认证代理：[现有认证代理名称或配置路径]
翻译需求：[需要英译中 / 不需要]
ReadWeave：[复用已配置实例 / 新建独立实例；若新建，填写公开源码归档路径]

请先读取仓库当前版本的 deploy/install-vps.sh、deploy/readweave_bootstrap.py、deploy/lessonweave.service、deploy/nginx.conf.template、.env.example、docs/deployment.md 和 integrations/readweave/HANDOFF.md，再据此执行；不要假设命令行参数、目录或配置字段；如果安装器和文档不一致，请先按安装器实际行为说明差异并修正文档建议

部署时请遵守以下要求：
1. 服务只监听 127.0.0.1；不要把应用端口直接暴露到公网
2. 先检查服务器、仓库状态、磁盘空间、现有服务和防火墙，再备份将要改动的配置及数据
3. 保留服务器上已有的认证代理、TLS 证书和其他服务；只改动 LessonWeave 部署所需的配置
4. 认证成功后，由代理覆盖客户端提交的 X-Aialra-User 请求头，并设置为认证系统确认的登录名；该登录名必须与 LESSONWEAVE_OWNER 相同
5. 将密钥和令牌写入服务器权限受限的环境配置或受保护的密钥存储，不要写入仓库、命令行参数、公开日志或本地报告
6. 完成 Codex CLI 的官方登录流程，确认服务账号可以读取登录状态，再启动或重启 systemd 服务
7. 若复用 ReadWeave，请先检查 `LESSONWEAVE_READWEAVE_URL` 与 `LESSONWEAVE_READWEAVE_TOKEN` 是否完整可用；如果它们存在，就复用同一实例并确认 `LESSONWEAVE_TRILIUM_URL` 与 `LESSONWEAVE_TRILIUM_TOKEN` 指向相同网址和令牌，不得另建重复库
8. 若需要新建 ReadWeave，请用公开源码归档运行安装器提供的 `--readweave-source` 选项；让部署脚本把新库放进独立 Docker 数据卷并只绑定 `127.0.0.1`；不要对公网开放 `18961`
9. 新库的 ReadWeave 原生首次设置、登录和 ETAPI token 必须由我或获授权的管理员在浏览器里完成；不要猜测或代造账号、登录态、令牌、模型设置；在我完成首次设置后，再用 `deploy/readweave_bootstrap.py --configure-token --env-file /etc/lessonweave.env` 通过隐藏输入保存 token，并让部署器验证 `version=1`、`schemaVersion=1.2` 的桥接接口，再确认或幂等创建 LessonWeave 根目录和回收站
10. 若私有环境文件已有 LessonWeave 根目录或回收站笔记 ID，保留并验证其可访问性及从属关系；不要移动或替换这些原有笔记
11. 重启工作台服务后检查服务状态、本机 `/workspace` 页面和 HTTPS 认证行为，确认未登录请求被拒绝、正确登录的所有者能够访问；按交接说明核对 ReadWeave 当前已验证的行为，不要把服务健康或桥接版本检查写成完整生成、发布和回读已通过
12. 不上传或公开个人笔记、输入材料、调用历史、凭据、账号、服务器私有路径或未脱敏日志

执行前若发现数据丢失风险、认证链路无法验证、域名或凭据缺失，或新库仍需我完成原生首次设置，请停在具体步骤并说明我需要亲自完成的动作；结束时只报告部署结果、检查结果、改动过的配置类别和后续需要人工完成的事项；敏感值用“已设置”描述，不要回显
```

该提示词不是对所有服务器环境的保证；运行前要确认域名、认证代理、SSH 访问和密钥已经由部署者准备；具体参数和服务路径以当前仓库文件为准
