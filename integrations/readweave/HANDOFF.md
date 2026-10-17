# 1 接手后先检查什么

本目录包含独立的 ReadWeave 风格演示、实际公共阅读组件和生成脚本，正式 ReadWeave 仓库未由本项目修改

## 1.1 怎样挂载组件

导入 reader-component.js 的 mountReader，将空容器和下列配置交给它

```javascript
const reader = mountReader(container, {
  projectId: project.id,
  base: project.resourceBase,
  search: '?preview=true',
  loadNote: key => noteStore.read(project.id, key),
  saveNote: (key, text) => noteStore.save(project.id, key, text),
  onSourceSelection: selection => questionPanel.setMaterial(selection)
});
// 关闭阅读标签时释放事件、计时器与阅读 DOM
reader.unmount();
```

mountReader 使用 Shadow DOM 隔离样式，关闭时会释放计时器、动画、全局事件与尺寸观察器，宿主可以通过 fetch 配置代理自己的授权附件请求

artifact-tree.js 另行导出 mountArtifactTree，用于原生展示材料树、问题树、标题树和承上启下树，接收生成端对应阶段 JSON，调用返回对象的 unmount 释放视图

getState 返回当前正文、材料包、覆盖结果与选中来源，宿主提问时应同时提供当前问题、选区和实际原材料，图片继续作为图片传递，表格与源码保留结构

## 1.2 怎样接收阅读包

生成端导出 05_writing/reading-package.zip，其中 manifest.json 记录格式版本、书稿入口、资源文件、来源位置和真实检查状态

import_package 检查文件清单与越界路径后导入空目录，宿主将包内资源作为授权附件提供，保持各文件的相对路径，正文中的原始 ID 与版本继续保留

来源定位分为 PDF 页面与坐标、网页 DOM、源码行号和图片区域，现有 ReadWeave 文本定位需要增加这些类型，旧定位继续保留

阅读包的正式约束位于 04-framework/05_writing/reading-package.schema.json，格式标识为 lessonweave-reading-package-v1，导入时同时检查 schema、文件清单、解压大小和路径，用户笔记通过宿主接口保存，随书数据包不携带个人笔记

## 1.3 怎样保存笔记和追问

生成内容与用户内容分别保存，笔记按项目、小节和单元 ID 关联，生成新版本时保留旧版本与关联记录

演示页的问答接口用于验证上下文交接，正式接入时复用 ReadWeave 原有问答器、保存与追问流程

## 1.4 怎样验证接入

- 网页、PDF、代码三份阅读包都能重新导入和打开
- 目录、原页与译文、讲解和术语表均由组件原生渲染
- 逐句定位、译文灰底、10%–300% 缩放、自由拖动和适配按钮保持原规则
- 明暗主题、窄屏、栏宽与上下比例、术语联动、练习反馈和笔记保存均可操作
- 关闭标签后调用 unmount，再次挂载时保留笔记，旧事件不重复响应
- 未通过审查的版本继续显示实际状态，正式发布状态按生成端记录读取
