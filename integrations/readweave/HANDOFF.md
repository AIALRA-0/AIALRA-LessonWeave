# 1 怎样接入 Trilium 与 ReadWeave

ReadWeave 使用 Trilium 的笔记、分支、附件和前端脚本，本项目按这些原生对象保存读本，正式 ReadWeave 的源码、数据库与服务由其维护者管理

当前实现已在独立的 ReadWeave 实例中验证，该实例使用与目标项目相同的 TriliumNext 0.104.0 镜像，验证包括 renderNote 挂载、附件读取、原生章节、笔记新建、修改与刷新后读取，宿主的后端脚本执行保持关闭

## 1.1 一份读本在原生树中怎样保存

```text
配置的父笔记
└── 用户选择的文件夹                         book 笔记
    └── 学习项目                            book 笔记，保留稳定 ID
        ├── 版本                            book 笔记，保存本版资源附件
        │   ├── 01 材料树                   JSON code 笔记
        │   ├── 02 问题树                   JSON code 笔记
        │   ├── 03 标题树                   JSON code 笔记
        │   ├── 04 承上启下                 JSON code 笔记
        │   ├── 章节                        book 笔记
        │   │   └── 小节                    readOnly text 笔记
        │   ├── 阅读组件                    frontend code 笔记
        │   └── 对照原材料阅读              render 笔记
        └── 我的学习笔记                    book 笔记，跨版本保留
```

阅读包中的原页、图片、译文、正文 JSON 与来源位置保存在版本笔记的附件中，普通原始 HTML 按文本提供，派生定位 HTML 带有禁止脚本执行的内容安全策略

SVG 原件按文本保留，阅读组件使用同源的 PNG 静态预览，图片区域继续对应原材料 ID，原始 SVG 字节仍在阅读包中

生成端通过 ETAPI 创建笔记与附件，文件夹重命名、移动和移入回收站同时更新对应原生分支，移动时先创建目标分支，再移除原分支，保留笔记 ID 与其他克隆位置

## 1.2 服务端需要配置什么

在仓库外的运行配置中设置以下环境变量，令牌只由服务端读取

```dotenv
LESSONWEAVE_TRILIUM_URL=http://127.0.0.1:8080
LESSONWEAVE_TRILIUM_TOKEN=YOUR_PRIVATE_ETAPI_TOKEN
LESSONWEAVE_TRILIUM_ROOT=YOUR_PARENT_NOTE_ID
LESSONWEAVE_TRILIUM_TRASH=YOUR_TRASH_NOTE_ID
LESSONWEAVE_TRILIUM_PUBLIC_URL=https://notes.example.com
```

ROOT 与 TRASH 必须是部署者创建的两个不同笔记，应用只在选定父笔记下保存学习项目，接入正式库时由 ReadWeave 维护者选择该分支

PUBLIC_URL 必须指向同一个笔记实例的浏览器入口，网站的“在 ReadWeave 打开”按钮会根据当前小节的导入回执读取真实父笔记路径，再跳转到原生笔记页，未关联正式库时按钮保持禁用，独立验证库中的笔记 ID 不用于正式库

网站中新建项目会自动保存到笔记树，已有项目可以使用以下命令导入当前结果，这个命令只保存已有产物，不调用模型

```bash
python -m lessonweave sync-trilium PROJECT_ID
```

SQLite 保存网站任务与目录索引，文件目录保留生成工作区，Trilium 保存原生阅读版本与宿主笔记，两份数据都需要备份，当前目录操作从 LessonWeave 写入 Trilium，宿主中的外部目录修改尚未自动反向导入

## 1.3 四栏组件怎样与宿主合作

trilium-render.js 通过 renderNote 加载 reader-component.js，在宿主笔记区域挂载四栏阅读组件，组件使用 Shadow DOM 隔离样式

前端脚本通过 lessonweaveEdition 和 lessonweaveUserNotes 关系查找实际版本与学习笔记目录，再按附件标题和 lessonweaveSectionId 标签获取当前实例的资源与章节 ID，脚本配置只保存逻辑项目 ID 和组件文件名

笔记新建使用宿主的 api.createNote，修改使用已登录会话与 CSRF 保护的笔记接口，浏览器中没有 ETAPI 令牌，也不调用 runOnBackend

完整对照阅读在 render 笔记中提供，点击“在原生章节中提问”会打开对应 text 笔记，由 ReadWeave 已有的选择、提问与保存流程处理追问，render 视图的来源选择事件也通过 lessonweave:source-selection 提供给维护者

当前已验证打开原生章节和笔记往返，ReadWeave 自带问答器的回答质量与跨选区上下文扩展留给其维护者验收

## 1.4 维护者还可以怎样挂载组件

```javascript
const reader = mountReader(container, {
  projectId: project.id,
  base: project.resourceBase,
  search: '?preview=true',
  resolveResource: path => attachmentStore.url(path),
  loadNote: key => noteStore.read(project.id, key),
  saveNote: (key, text) => noteStore.save(project.id, key, text),
  onNavigate: search => openSection(search),
  onSourceSelection: selection => questionPanel.setMaterial(selection)
});
// 宿主关闭阅读标签时释放事件、计时器和阅读视图
reader.unmount();
```

getState() 返回当前正文、来源包、覆盖记录和选中材料，提问上下文可以据此保留实际原句、图片区域、表格与源码位置

artifact-tree.js 提供 mountArtifactTree，用来展示四个中间阶段的真实 JSON，关闭后调用返回对象的 unmount()

## 1.5 阅读包怎样导入

05_writing/reading-package.zip 中的 manifest.json 使用 lessonweave-reading-package-v1 格式，Schema 位于 framework/05_writing/reading-package.schema.json

import_package 核对文件清单、路径、数量和解压大小后导入空工作区，再由 sync_project 保存到宿主，这条导入路径会重新建立实际附件与笔记对应，个人笔记不包含在阅读包中

宿主原生 ZIP 导出后再导入另一实例的完整往返尚未验证，跨实例交接目前使用上述阅读包导入路径

## 1.6 交接时怎样验收

- 分别用网页、PDF 与代码检查原页、译文、图表与真实位置，代码只标记实际字符范围
- 检查窄屏、主题、栏宽、上下比例、10%–300% 缩放、自由拖动与适配
- 保存学习笔记、刷新、再次修改，确认原有笔记与版本继续保留
- 打开对应原生 text 章节，用宿主已有问答器验证选择与追问
- 保留生成端真实检查状态，未通过的稿件继续显示待审
- 检查组件卸载后事件和计时器被释放，再次打开时交互正常

原生接口依据：[ETAPI](https://docs.triliumnotes.org/rest-api/etapi/)、[前端脚本 API](https://docs.triliumnotes.org/script-api/frontend/)、[附件](https://docs.triliumnotes.org/user-guide/concepts/notes/attachments)

## 2 为什么下一版要改造原生笔记页

当前 renderNote 组件可以完整阅读，但用户需要切换到 text 笔记才能使用宿主的划线与提问，因此它尚未实现同一个页面里的完整体验

推荐在 ReadWeave 的原生 text 笔记页增加原文对照、目录与术语表，正文继续使用宿主现有的笔记组件，生成网站承担上传、任务调度与版本发布，个人笔记、划线和问答统一由 ReadWeave 保存

若把问答器复制到生成网站，两边就需要同时处理选区、回答流、追问、保存状态、编辑冲突和离线重连，维护范围明显增大，共用原生笔记页可以直接沿用已经成熟的交互与保存流程

### 2.1 页面怎样组合

```text
宿主笔记树与章节目录 | 原页和译文 | 宿主原生正文 | 术语表与现有问答面板
```

只有带 LessonWeave 标记的笔记启用这个布局，普通笔记继续沿用宿主布局，问答打开时右栏切换到宿主问答面板，关闭后恢复术语列表与原先滚动位置，窄屏改为面板切换

正文保持在宿主原有的文本组件和 noteContext 中，旁栏组件按当前笔记创建和卸载，切换标签、分屏和编辑模式时分别管理自己的事件与滚动位置，具体挂载点由 ReadWeave 维护者按当前源码确认

Trilium 的 [NoteContextAwareWidget](https://docs.triliumnotes.org/user-guide/scripts/frontend-basics/custom-widget/note-context-aware-widget) 提供按笔记上下文挂载的扩展方式，正式接入还需要适配 ReadWeave 已有的侧栏与选区实现，单靠嵌入整套 reader 无法完成这些职责

### 2.2 哪一份数据负责保存什么

| 数据 | 由谁保存 | 其他位置怎样读取 |
|---|---|---|
| 上传材料、调用回执、生成任务与检查记录 | LessonWeave 工作区 | 网站显示实际状态，发布包保留检查记录 |
| 已发布正文、译文、来源位置、术语和覆盖记录 | ReadWeave 中不可变的版本资源 | 原生笔记保存版本关系，旁栏按该版本读取 |
| 用户笔记、划线、追问与回答 | ReadWeave 原生存储 | 网站需要展示时读取宿主结果，避免同时写两份副本 |
| 文件夹与笔记树 | ReadWeave 原生分支 | 网站经服务端读取实际分支，目录操作通过同一接口完成 |

现有实现仍在网站保存目录索引，且尚未反向接收宿主目录修改，迁移时需要把原生分支作为目录依据，网站索引只作可重建缓存

### 2.3 来源和提问怎样对应

导入回执需要保留 project_id、edition_id、section_id 与实际 noteId 的关系，每个正文块保留 block_id，材料映射继续记录 source_id、sentence_id、图片区域、PDF 页坐标或源码行列

用户在原生正文中选中文字后，宿主选区服务找到正文块，再从当前版本取得原句、译句和相关图表，交给现有问答器作为材料上下文，旁栏也按同一份映射定位原页

需要用宿主编辑器能够持久保存的字段或插件保存正文块关系，并验证刷新与编辑后仍能定位，临时 DOM 属性不足以保证这一点，覆盖标记与用户划线使用各自的 ID，删除一条划线时保留材料映射

编辑生成正文时保留原始版本，检查发生变化的正文块及其覆盖记录，在核对完成前显示映射待核对状态，个人笔记始终单独保存

### 2.4 发布、跳转和迁移怎样完成

1. 生成端产出已有格式的版本包，保留全部正文、材料映射与真实检查状态
2. ReadWeave 导入端核对包与版本，创建原生小节，返回实际 noteId 与版本回执，相同版本再次导入时复用已有结果
3. 网站保存回执，当前小节的跳转按钮使用实际笔记路径，导入尚未完成时显示未关联
4. 原生笔记页读取当前版本的来源与术语，划线、提问和笔记继续经过宿主现有接口
5. 既有网站笔记按原键一次迁入宿主，存在冲突时保留两份并标明来源，核对完成后由宿主负责后续保存

正式库导入和宿主代码修改由 ReadWeave 维护者执行，当前独立验证实例继续保留，验证实例的回执与正式实例分别保存

### 2.5 怎样确认接入成功

- 在同一原生小节中完成目录跳转、原页与译文对照、术语查询、来源定位和缩放，验证网页、PDF 与源码的实际位置
- 使用宿主的提问、定义、注解、总结和笔记动作，确认选区文字、材料上下文与保存目标属于当前小节和版本
- 新建与修改笔记、追问和回答后刷新，确认保存结果和原有笔记都在
- 验证多标签、分屏、明暗主题、窄屏和组件卸载，普通笔记继续正常使用
- 移动或重命名原生笔记后，从网站再次跳转，确认路径与目录同步更新
- 使用旧版正文核对旧版来源，发布新版时保留原来的笔记和问答，失效映射如实标记

以上为下一版的实施与验收方案，当前 renderNote 验证结果不计为原生笔记页验收通过
