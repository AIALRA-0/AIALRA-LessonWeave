# 1 怎样直接运行输入文件

00_source/input.schema.json 规定 kind、material、mode 和 system_prompt 四个字段，kind 与 mode 均为非空字符串，文件路径可以相对输入 JSON 所在目录填写

```bash
# 在项目根目录使用同一正式入口生成自编 PDF 示例
python examples/create_fixtures.py
python -m lessonweave run --input examples/pdf.input.json --name "鸟类观察示例"
```

运行数据默认保存在用户目录下的 .local/share/lessonweave，设置 LESSONWEAVE_DATA 可以指定独立位置

网站使用者打开 `/workspace`，先选择或新建文件夹，再点击“生成读本”，选择网页、PDF 或项目 ZIP 并提交，任务卡显示实际阶段和已完成任务数，关闭页面后后台继续执行

点击“停止”会结束该任务及其模型、解析子进程，已完成的阶段和调用回执保留，点击“继续”后复用已完成结果，达到返修上限的稿件保留真实问题与预览

左侧目录支持搜索、折叠、重命名、移动、移入回收站和恢复，正在执行的项目先停止再移入回收站，用户笔记随项目保留

## 1.1 怎样配置模型

LESSONWEAVE_BACKEND 默认为 codex，LESSONWEAVE_MODEL 默认为 gpt-6.1-sol，LESSONWEAVE_EFFORT 默认为 high

LESSONWEAVE_CODEX 可以明确指定已登录的 CLI，Windows 默认优先寻找桌面应用附带的 CLI，再寻找系统命令

## 1.2 怎样恢复与查看结果

使用同一个 --project 标识恢复项目，程序复用已完成的调用，保留已有修复轮次，响应结果不确定时先保留原请求状态

网站中可以查看阶段树、当前完整预览与实际用量，检查通过时保存正式 book.json，未通过时保留 preview-book.json 和逐项问题

## 1.3 怎样导出

```bash
# 根据当前项目的真实引用导出阅读材料
python -m lessonweave export /path/to/project
```

阅读包不包含用户笔记，笔记继续由站点数据库或接收阅读器独立保存
