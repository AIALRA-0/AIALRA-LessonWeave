# LessonWeave 怎样把读本保存到 ReadWeave

ReadWeave 是这套流程使用的中央笔记库，采用 Trilium 的笔记、分支、附件和前端组件保存正式读本。LessonWeave 在第 13 阶段（流程内部编号 12）按顺序完成两件事：先用 `trilium.sync_project` 保存阅读包、材料树、章节和附件，再用 `readweave.publish_project` 登记正文、原文、译文和术语定义。两件事共用同一个阶段，不会因为服务健康或能力接口响应，就预先记成发布成功。

本说明记录当前代码结构、隔离导入和正式 cutover 结果。五本读本已经在 staging 库和正式库完成登记，文章与章节映射均为 100%；正式库逐本数量和登记耗时列在验证表中，这些耗时不包含模型生成。普通文章读取默认跳过大型来源附件，调用方明确传入 `includeSource=1` 时才读取来源；附件仍完整保存在 ReadWeave 中。首次安装、回环监听和令牌配置请看[部署指南](../../docs/deployment.md)。

## 第 13 阶段怎样先保存阅读包再登记正文

`trilium.sync_project` 会把项目放入已配置的 LessonWeave 根目录，在其中创建版本笔记，保存材料树、问题树、章节树、承接内容、章节和小节，并把阅读包里的文件作为附件上传。`runtime/trilium/current.json` 和该版本的 `mapping.json` 会记录项目、版本、章节、附件与原生笔记之间的对应关系；二进制原件继续留在附件中，不会被猜成可读文本。

随后，`readweave.publish_project` 会按项目与版本生成稳定的导入身份，并将每节连续讲解、可读的原文、中文译文、可读的文本来源和术语定义分别登记到 ReadWeave。服务器将各类正文保存为 `text/html`，并把来源位置和原始结构作为版本映射传给桥接。定义由 ReadWeave 的原生存储创建，这一步不调用生成模型。

ReadWeave 会返回真实的版本与文章 `noteId`。LessonWeave 把导入身份、已登记文章和章节对应关系写入 `runtime/readweave/current.json`。重试时，桥接按稳定身份补齐未登记条目；已存在的改稿和已删除条目不会被旧快照覆盖或复活。网站项目标题与 ReadWeave 原生笔记标题各自保存，文章 `noteId` 是它们共同引用的原生身份。

这两个保存动作属于同一第 13 阶段。工作台当前显示这个阶段的合并状态；运行记录分别保存在 `runtime/trilium/` 与 `runtime/readweave/`。遇到导入问题时，应查看任务结果和这两类映射记录，不能把笔记树已保存解释为 ReadWeave 正文已经登记。

## ReadWeave 原生侧栏怎样复用既有交互

LessonWeave 的集成将 ReadWeave 自带的 `Panel` 挂到原生文章页面中，继续使用宿主已有的提问、定义、注解、总结和笔记操作。集成提供当前正文与材料位置，不复制另一套问答面板，也不把服务端 ETAPI 令牌放进浏览器。ReadWeave 原生笔记页使用当前登录会话；浏览器写入仍由宿主的 CSRF 校验保护。

LessonWeave 的 `/p/<项目>/readweave.html` 路由会转到同一项目的 `book.html`，不会再创建一套平行阅读外壳。阅读页仍读取当前版本，用户笔记、批注和问答则由 ReadWeave 原生接口保存。正文变更通过共享更新事件刷新已保存内容，保持尚未保存的草稿，不必卸载并重新挂载侧栏。

## 修改、并发和删除怎样与原生笔记保持一致

文章正文按当前修订号提交，服务端用比较并交换和持久编辑租约处理并发。租约带有递增围栏号；文章或链接发生修订冲突时，客户端保留草稿并显示当前版本。共享变更记录与删除墓碑保存在 ReadWeave，网站可以按游标回读已删除或已恢复的版本，不会用旧本地快照把已删除文章重新创建。

版本删除会使用 ReadWeave 原生回收站和墓碑。若将要删除的文章仍有活动编辑租约，服务端会先拒绝删除，避免只移动了一部分树枝。恢复也使用原生版本关系和幂等操作编号；桥接不另造一套独立的回收站目录。

接入不会改变生成 harness、模型参数或生成任务租约。ReadWeave 桥接只接收已生成的正文、来源、译文和定义，管理正式库中的文章身份、修订、删除和用户编辑。

普通文章读取默认跳过大型来源附件；调用方只有明确提供 `includeSource=1` 时才会读取完整来源附件。来源附件仍保存在 ReadWeave 中。本轮接口验证结果见[验证结果](../../docs/readweave-validation.md)。

## 服务器怎样认证 ReadWeave

服务端通过 `LESSONWEAVE_READWEAVE_BRIDGE=1` 启用桥接，并读取 `LESSONWEAVE_READWEAVE_URL`、`LESSONWEAVE_READWEAVE_TOKEN`。同一实例还必须提供兼容 provider 使用的 `LESSONWEAVE_TRILIUM_URL`、`LESSONWEAVE_TRILIUM_TOKEN`，两组网址与令牌都应指向同一正式库。阅读包同步还会使用 `LESSONWEAVE_TRILIUM_ROOT` 和 `LESSONWEAVE_TRILIUM_TRASH`；`LESSONWEAVE_TRILIUM_PUBLIC_URL` 用于生成浏览器入口。

部署器可以复用现有实例，也可以用公开源码附件构建一个独立 ReadWeave。新实例默认只监听本机回环地址、使用单独的数据卷；首次设置、登录和 ETAPI token 仍由管理员在浏览器中完成。配置 token 时，部署器会检查 `GET /api/lessonweave/capabilities` 返回 `version=1`、`schemaVersion=1.2`，并幂等确认 LessonWeave 根目录与回收站。浏览器不会收到 ETAPI token。

能力接口通过只证明桥接版本匹配；`/api/health-check` 通过只证明原生服务能够响应。两种检查都不能代替读本写入、原生侧栏操作、回读和恢复的端到端验收。

## 哪些行为已经验证，哪些还需要继续验证

| 检查内容 | 已有证据 | 当前结论 |
|---|---|---|
| 能力接口与认证 | 独立 HTTP 检查确认 `version=1`、`schemaVersion=1.2`；ETAPI token 与 Bearer token 都可访问，无凭据或无效 token 会被拒绝；浏览器会话写入仍要求 CSRF | 接口和认证路径已通过定向检查 |
| 后端、HTTP、BFF、界面和有界状态检查 | 冻结版本后端测试 129 项通过；最终 HTTP 检查 113 个请求、53 条断言通过；BFF 66 个请求、28 条断言通过；原生界面 36/36 项通过，0 个浏览器错误、0 次模型调用、0 次用户数据写入；有界检查遍历 240 个状态并核对 5,658 条不变量 | 这些检查覆盖了本轮测试的输入和状态范围，不能证明所有环境与状态都绝对稳定；详细范围见[验证结果](../../docs/readweave-validation.md) |
| 五本读本的完整导入 | 隔离 staging 库完整导入了 web 112 篇、26 个讲解单元；PDF 108 篇、36 个讲解单元；OpenROAD 3,084 篇、60 个讲解单元（其中 2,904 篇为 source）；fresh-web 293 篇、24 个讲解单元；Vera 561 篇、22 个讲解单元。五本的 article 与 section 登记映射都为 100% | 五本完整导入与登记映射检查已通过 |
| 普通文章读取来源附件 | 普通 GET 默认跳过大型来源附件；请求 `includeSource=1` 时读取来源，库内附件继续保留 | 当前版本已包含这一读取行为 |
| 正式库 cutover | 158.844 秒内迁移 435 条笔记、458 个分支、520 项属性、4 条修订记录、11,942 个附件和 9,608 个新数据块；模型调用 0 次 | 没有覆盖已有记录、没有缺失外部关系 |
| 五本读本的正式登记 | web 112 篇/26 节（65.058 秒）；PDF 108 篇/36 节（65.327 秒）；OpenROAD 3,084 篇/60 节（1,462.737 秒，其中 2,904 篇为 source）；fresh-web 293 篇/24 节（177.172 秒）；Vera 561 篇/22 节（232.095 秒） | 合计 4,158 篇/168 节；登记错误 0、模型调用 0、原正文文件改动 0。以上是逐本登记耗时，不是模型生成耗时 |
| 最终映射与术语引用核验 | 五本正式读本的 section mapping、article registration、default definition mapping 和 7,123 条术语引用；核验用时 29.771 秒 | 三类映射均为 100%；每条默认定义正文回读均匹配；错误 0、模型调用 0 |
| 正式库锚点读取 | 新负载 168 个 anchors GET 全部返回 200；handler p50 136 ms、p95 254 ms、最大 942 ms，批次共 26,197 ms。旧负载为 35 个读取，p50 9,776 ms、p95 18,105 ms、最大 20,119 ms | 两组负载不同，不按严格成对测试计算速度倍数。每个请求只扫描一次全部链接，并只在当前请求内复用结果；没有跨请求缓存，没有改动术语或正文 |
| Linux 部署器首次启动 | 最终源码包构建用时 269.958 秒，总用时 273.209 秒；health、根页面、`/bootstrap`、5 个入口 JS 和 13,383 字节的首次设置动态分块均返回 200 | 新库 `dbInitialized=false`，桥接关闭，未创建账号、token 或模型调用 |
| staging 重启 | 编辑租约与 fencing 重启后仍有效；删除和恢复事件仍保留 | 重启套件 50/52 条断言通过；一次 GET 遇到 38.55 秒启动一致性检查，超过 35 秒测试期限后仍返回 200，当前回读为 8.717 ms；因此重启套件没有全绿 |

## 怎样构建公开源码包

当前分支使用[阅读修复版源码包](https://github.com/AIALRA-0/AIALRA-LessonWeave/releases/download/v0.2.0/readweave-source-reader-followup-20261022.tar.gz)，SHA-256 为 `560945276b663e2038b48301eca8975fc4430051ad0bab712f8e758f064ad23a`，包含 34 项桥接覆盖与 2,731 个源文件；旧源码包和公开案例包仍保留在 [v0.2.0 版本页面](https://github.com/AIALRA-0/AIALRA-LessonWeave/releases/tag/v0.2.0)，供对应旧提交使用。当前安装器核对归档后，还会应用仓库自带的 `patches/scoped-export.patch`，让文章导出只读取该篇关联的对象；手动构建时也应先用 Git 应用这份补丁，再运行下列命令

```bash
corepack pnpm install --frozen-lockfile --ignore-scripts
corepack pnpm client:build
corepack pnpm server:build
```

`--ignore-scripts` 是必要参数：脱敏源码包保留 `apps/web-clipper` 的 workspace 清单以匹配锁文件，但省略了无关的扩展入口；正常 postinstall 会因缺少这些入口而停止。部署器在 Linux Docker builder 中执行源码构建。`server:build` 会重新生成客户端和 PDF viewer，因此容器构建只需执行这一项构建命令。

公开归档的文件清单和各文件哈希保存在根目录的 `SOURCE-MANIFEST.json`；桥接覆盖文件还须逐项匹配 LessonWeave 的 `integrations/readweave/backend-source-manifest.json`。归档仅包含已授权公开的源码和对应许可证文件，不含私有部署历史、运行数据、凭据或数据库。

## 阅读修复版怎样沿用当前库

网站在切节开始时清除旧文章关联，再给新正文、原文与译文绑定各自的共享 ID，选区和打开、编辑入口都使用当前文章；数学选区的保存与恢复共用公式源码，避免把 KaTeX 的辅助文字算进引用。提问、定义、注解、总结和笔记继续使用原生面板与现有生成 harness。

启动时只为缺少共享登记的成书补登记，并补已有 PDF 的可选文字层；已有文章和墓碑继续沿用原 ID。术语名称可用 `display-title` 操作单独整理，定义正文仍从共享对象读取，独立的用户展示改稿也会保留。网站不再创建正文编辑框，编辑会打开 ReadWeave；回收需要确认，ReadWeave 的两个清空入口也共用确认逻辑，取消时不发送删除请求。Trilium 后端脚本执行保持关闭。
