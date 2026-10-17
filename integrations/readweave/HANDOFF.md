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
```

ROOT 与 TRASH 必须是部署者创建的两个不同笔记，应用只在选定父笔记下保存学习项目，接入正式库时由 ReadWeave 维护者选择该分支

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

05_writing/reading-package.zip 中的 manifest.json 使用 lessonweave-reading-package-v1 格式，Schema 位于 04-framework/05_writing/reading-package.schema.json

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
