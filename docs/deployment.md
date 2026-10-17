# 1 怎样部署个人网站

首版使用 Python 服务、SQLite、文件目录和 Nginx，生成后端直接调用本机登录的 Codex CLI，生产环境只监听回环地址并由认证代理提供入口

## 1.1 怎样准备运行环境

安装 requirements.txt 和 Playwright 浏览器，Linux 缺少浏览器系统库时使用 playwright install --with-deps chromium

本次运行验证使用官方 Codex CLI 0.163.0-alpha.10.2，旧版 CLI 可能拒绝所选模型或缺少参数，部署时先核对 codex --version，多个版本并存时用 LESSONWEAVE_CODEX 指定经过实际调用验证的执行文件

默认用 PyMuPDF 保存 PDF 文本、图片、矢量图所在原页与坐标，安装 Docling 后也可使用其解析路径，图片 OCR 句框是可选能力，缺少时保留原图区域与实际定位状态

## 1.2 怎样配置目录与登录

复制 .env.example 并在仓库外保存生产配置，LESSONWEAVE_DATA 指向持久目录，LESSONWEAVE_CODEX 指向官方 CLI，在执行账户中完成 codex login

生产服务设置 LESSONWEAVE_AUTH_REQUIRED=1 和 LESSONWEAVE_OWNER，可信代理覆盖 X-Aialra-User，应用仅接受配置的所有者身份，应用端口保持回环绑定

deploy/lessonweave.service 和 deploy/nginx.conf.template 提供配置模板，按目标机的真实路径、证书和认证入口替换，再检查 Nginx 配置并启动服务

## 1.3 怎样备份与升级

备份站点数据目录、SQLite 数据库与仓库外配置，数据库使用 SQLite backup 接口取得一致副本，升级前保留当前版本目录与数据备份

新版本使用新的代码目录，健康检查与阅读验收完成后切换 current 链接，回滚时切回旧代码目录，保留生成数据和笔记

## 1.4 怎样检查上线

- 未登录访问由认证入口处理，API 不提供私人材料
- 所有者登录后可提交材料、关闭页面、重新打开并继续查看任务
- 三类材料的原文、翻译、非文字资源和定位都使用实际文件
- 独立 ReadWeave 演示使用相同阅读包，正式 ReadWeave 服务保持独立
- 重启服务后保留笔记与任务记录，处理中断状态供恢复核对

## 1.5 怎样选择 Trilium 存储

按 [ReadWeave 交接说明](../integrations/readweave/HANDOFF.md) 配置 ETAPI 地址、令牌、父笔记与回收站，新生成的读本会保存为原生笔记与附件，令牌留在服务端配置中

Trilium 未配置时，网站使用本地目录和 SQLite，配置后仍保留生成工作区与任务数据库，备份时同时包含 Trilium 数据库和附件

升级时若旧服务仍有任务正在执行，可以让旧进程继续处理已有任务，新实例临时设置 `LESSONWEAVE_RECOVER_JOBS=0`，两个实例通过 SQLite 原子领取不同任务，旧实例退出后恢复默认值 `1`，下次启动会把遗留的运行状态标记为可继续

正常单实例部署沿用默认值，进程终止与模型调用通过独立进程组管理，模型运行期间显示已完成的实际任务数，单个调用的剩余时间保持未知
