# 当前网页怎样获取与保存

正式入口仍是 `framework/00_source/acquire.py` 的 `acquire`，URL 输入统一调用 Browsertrix Crawler 1.15.0，一次生成 WACZ，不回退到自行拼装 HTML 的旧下载器

## 怎样准备执行环境

执行端需要已有 Docker 引擎和 `webrecorder/browsertrix-crawler:1.15.0` 镜像，Python 依赖包含 warcio 1.7.5，Playwright 需要可用的 Chromium

默认在本机 Docker 执行；设置 `LESSONWEAVE_ARCHIVE_SSH` 时，脚本在该 SSH 主机运行 Docker，再用 scp 取回 WACZ，`LESSONWEAVE_ARCHIVE_WORKDIR` 指定远端存放目录，默认是 `/tmp/lessonweave-archives`

ReplayWeb.page 2.5.3 的原版前端与 Service Worker 保存在 `framework/reader/archive`，服务器通过 `/archive/` 提供这些文件，并为项目内 WACZ 提供 HTTP Range 读取

## 一次获取会保存什么

| 文件 | 保存的内容 |
| --- | --- |
| `original.wacz` | Browsertrix 捕获的原始页面、资源与网络响应，后续不会改写此文件 |
| `capture.json`、`capture.log` | 实际命令、一次执行的退出码、采集与传输耗时 |
| `archive-check.json` | ZIP 校验结果、资源清单和原站 HTTP 失败记录 |
| `original.html`、`dom.json`、`original.png` | 只从本地归档回放读取的 DOM、定位与截图，供后续解析使用 |
| `assets` | 只从本地回放取得的图片与 SVG 等静态素材副本 |
| `replay-check.json` | 回放文字、公式、图片解码状态、外部连接尝试与具体缺口 |
| `00_source/source.json` | 统一材料清单，以及 `web_archive`、`integrity` 和 `acquisition` 字段 |

`snapshot.html` 与 `snapshot.offline_html` 保存本地 DOM 路径，供解析和逐句定位读取；`snapshot.replay` 保存 WACZ 回放地址，供用户打开可交互的原页，两种输入不再混用

长截图逐屏读取 iframe 的真实可见画面，再按实际滚动坐标拼接，固定栏与吸顶栏在派生快照中只保留一次，原 WACZ 不变；`replay-check.json` 记录每屏覆盖范围与完整高度，本地回放通过拒绝外部连接的代理运行，不再从原网站补文件

PDF 继续原样复制，记录字节一致性与页数，不进入材料树解析

## 怎样理解完整性结果

`status=acquired` 表示材料已经保存，`integrity` 另行记录文件校验和实际缺口；第三方视频是否完整播放、交互状态是否与原页一致，需要按具体测试记录阅读，不能从命令退出码推断

脚本分别记录采集、传输、归档检查、离线 DOM 保存及总耗时；没有模型调用、自动返修或静默重抓

旧的自制网页下载与静态改写实现已移到 `archive/legacy-web-acquisition-20261019`，正式框架不再调用
