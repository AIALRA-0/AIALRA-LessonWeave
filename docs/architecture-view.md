# 怎样在网站查看当前框架

工作台顶部的“流程与架构”打开 `/architecture`，从读本进入时自动选择该项目，页面按阶段连续展示转换图、字段、实际内容和检查规则

字段类型读取现有 Schema，案例读取项目当前保存的产物，选择“框架说明”可以只看公共流程，任务运行时每三秒读取进度，页面隐藏时暂停刷新

## 文件放在哪里

```text
04-framework/
  architecture/
    index.html             页面入口
    compact.css            从 v0.4 原型复制的样式与网站适配
    flow.js                渲染、字段定位、项目选择与刷新
    stages.json            阶段关系、可见字段与实际规则位置
    vendor/
      mermaid-10.9.3.min.js
      LICENSE-mermaid.txt
lessonweave/
  architecture.py          读取当前框架、项目结果和已有统计
  server.py                页面与只读接口，沿用所有者登录保护
web/
  workspace.html           工作台入口
  workspace.js             将所选项目带入架构页面
tests/
  test_architecture.py     检查版本、缺项、只读访问与路径范围
```

完整 v0.4 原型副本单独保存在任务工作目录的 `architecture-template-v0.4/`，公共实现只带展示代码和 Mermaid，私人案例快照、图片和历史草案留在原型副本中

## 怎样对应当前执行步骤

00 至 04 分别对应材料保存、解析、问题、章节和承接，05 对应写作，06 和 07 展示 05_writing 内的审查、阅读定位与导出步骤

教学信息点目前仍在 05 清点，页面按实际实现显示，覆盖数字分别读取提取、对象、问题归属、章节分配和讲解审查记录，缺失数字显示未记录

架构页面只读取已有结果，生成流程、Schema、正文、笔记和检查状态继续使用原文件
