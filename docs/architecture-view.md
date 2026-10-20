# 怎样在网站查看当前框架

工作台顶部的“流程与架构”打开 `/architecture`，从读本进入时自动选择该项目，页面按阶段连续展示转换图、字段、实际内容和检查规则

字段类型读取现有 Schema，案例读取项目当前保存的产物，默认展示框架内置的真实网页案例，任务运行时每三秒读取进度，页面隐藏时暂停刷新

## 文件放在哪里

```text
framework/
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

完整 v0.4 原型副本继续作为历史参考，框架内置案例保存在 `framework/examples/minimal-web`，材料来自 IANA 公共说明页，字段直接读取本次完整生成的产物

## 怎样对应当前执行步骤

页面依次展示保存材料、解析为材料树、规划第 0 章与正文问题、编排章节、编写正文、补写承上启下、统一整理术语表、脚本检查和交付阅读，共九步，显示编号与实际产物目录的对应见 [架构说明](architecture.md)

材料树直接进入问题规划，脚本按用途和具体问题查缺，有缺项才补；章节规划检查所有问题的唯一归属，覆盖数字读取当前产物，缺失数字显示未记录

架构页面只读取已有结果，生成流程、Schema、正文、笔记和检查状态继续使用原文件
