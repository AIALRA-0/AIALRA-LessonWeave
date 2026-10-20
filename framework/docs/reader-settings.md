# 阅读页怎样使用生成设置

阅读设置中的模型选择保存到当前项目的 `runtime/generation-settings.json`，后续创建的任务从这份文件读取模型与思考力度，已有正文、译文、笔记和调用回执继续保留

| 任务 | 默认模型 | 默认思考力度 |
| --- | --- | --- |
| 问题与章节规划、讲解、承上启下和阅读组件 | `gpt-6.1-sol` | `high` |
| 原句翻译 | `gpt-6-luna` | `max` |

项目中显式保存的选择优先于服务器环境变量，服务器可以使用 `LESSONWEAVE_GENERATION_MODEL`、`LESSONWEAVE_GENERATION_EFFORT`、`LESSONWEAVE_TRANSLATION_MODEL`、`LESSONWEAVE_TRANSLATION_EFFORT` 分别设置默认值，旧的 `LESSONWEAVE_MODEL` 和 `LESSONWEAVE_EFFORT` 仍可统一覆盖两类任务的默认值

页面通过 `/api/projects/{project_id}/generation-settings` 读取和保存设置，保存操作只更新设置文件，下一次调用在回执中记录实际使用的模型、力度和用量

阅读页保留章、节和核心问题编号，问题内部通过标题层级区分核心问题、讲解组和本段总结，内部字段、稳定 ID、素材编号与来源对应关系继续保留

素材加载完成后自动适配一次，读者随后可以自由缩放、拖动和调整高度，点击适配按钮会按当前预览框重新计算一次，字号随正文字号变化，内容标题始终大于正文
