# 术语名称怎样写

本项目沿用现有 Writing Format 第 2、3 条的名称结构与大小写要求，名称与检查器一同随当前版本发布

现有 Course OS 的 docs/generation-writing-standards.md 也要求把术语规范带入教学生成，并在输出后核对实际含义，本项目只采用与当前写作有关的规范，不引入其他项目的工作流

## 名称需要满足哪些格式

- 有可确认完整展开的缩写时，使用 ABBR 中文全称（English Full Name）
- 没有缩写时，使用 中文全称（English Full Name）
- 括号使用全角，只放对应英文全称，定义、用途和别名放在条目其他位置
- 英文全称不重复写缩写，不以缩写代替本应完整展开的单词
- 普通名称使用标题式大小写，of、and 等连接词按名称中的位置处理
- 正式名称保持有来源的官方大小写，例如 npm 和 iOS，不为了统一大写而改错
- 形似缩写但没有可靠展开的正式名称按正式名称登记，不补造全称
- 能展开的缩写保留完整英文，components 供检查器核对对应单词，阅读页不再单独展示字母拆解
- MB 与 GB 按单位前缀和字节拆开，不能为了凑字母而制造一个不存在的英文全称

## 怎样清点所有术语

先完成正文，再由外层 agent 逐段列出专业概念、中文别名、英文名称、缩写和单位，保存在独立的 terminology.catalog.json

脚本按这份清单扫描上方全部内容，同时单独扫描英文与缩写；出现未登记的英文或缩写会失败，由外层 agent 补充清单或修正写法

生成的术语表必须恰好包含清点结果，每一项都能回到实际出现的位置，删除术语表条目不会缩小分母

术语表自身不作为新的正文候选来源，以免定义中的解释无限递归加入术语，用户自写笔记也不进入教材术语清单

## 检查器核对什么

demo.schema.json 约束条目字段非空、条目结构和正文结构，build_demo.py 核对中英文排列、括号、大小写、缩写重复、逐字母拆解、完整收录与实际出现位置

外层 agent 对中文专业概念逐段清点，并核对完整英文与当前语境的含义，脚本负责把这份独立清点与最终术语表逐项对应

## 术语解释怎样保持连贯

新版 glossary.schema.json 将名称保存为 abbreviation、chinese、english 三个字段，缩写允许为空，但与英文全称不同，脚本组装显示名称

professional_definition 的 genus、differentia、boundary、extension 组成完整专业定义，intuitive_explanation 的 anchor、mapping、intuition、extension 组成直观解释，typical_example 的 initial_conditions、mechanism、outcome、extension 组成典型案例，各组前三项必填，extension 保留且可为空

三组内容各显示一段，段内没有小标题，定义先解释概念本身，直观解释说明关系怎样对应，案例交代实际条件、过程和结果，术语与本问正文同次生成，已有词义复用完整三段，最后由脚本合并术语表

writing_contract.py 只把确定字段转换为阅读器使用的 definition 和两段 explanation，完整结构化原稿保存在 glossary.json，旧词条继续沿用原内容
