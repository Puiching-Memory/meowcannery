# 喵罐头（MeowCannery）

把扫描复习指南转换为 **Exameow 1.5.0** 可导入题库。公共流程处理 OCR、检查、导出和组卷；每本书选择预设规则，特殊版式由插件处理。

**直接使用：双击 `启动喵罐头.cmd`。** 选择书籍后，依次点击“识别扫描页”和“生成题库”。已有识别缓存会自动复用。

生成文件位于 `output/<书籍ID>/`。在 Exameow 的题库导入界面选择其中的 `*_Exameow.xlsx`，检查题数和章节后完成导入。

当前已重新生成药理学 **2165 题**、分析化学 **878 题**，两份文件均通过 Exameow 1.5.0 官方导入器逐字段验证。分析化学共识别 899 题，另有 **21 题**涉及谱图、结构式或原书缺字，列在 `output/fenxi/原页核对.html` 中，可按章节筛选并查看扫描页。878 题是部分题库，结构检查通过不代表全文已人工审校。

2026-09-28 已处理 42 张分析化学反馈截图，并修复同组问题共 96 题。

| 书籍 ID | 书籍                           | 规则                                       |
| ------- | ------------------------------ | ------------------------------------------ |
| `yaoli` | 药理学复习指南                 | 专用解析插件，从扫描页缓存和已核实勘误重新生成 |
| `fenxi` | 分析化学复习指南（温金莲主编） | 分析化学预设，共用选项、分节答案、公式转写 |

## 常用命令

在项目目录打开 PowerShell，使用已有 `.venv`：

```powershell
# 查看环境、程序版本及识别进度
.\.venv\Scripts\python.exe -m meowcannery doctor

# 生成一本书；all 表示依次构建全部配置的书籍
.\.venv\Scripts\python.exe -m meowcannery build yaoli
.\.venv\Scripts\python.exe -m meowcannery build fenxi

# 分析化学：先导出检查通过的题目，另存待核对内容
.\.venv\Scripts\python.exe -m meowcannery build fenxi --allow-review

# 识别缺失页面，可中断后继续
.\.venv\Scripts\python.exe -m meowcannery ocr fenxi

# 组卷，答案单独保存
.\.venv\Scripts\python.exe -m meowcannery quiz yaoli --single 20 --multi 5 --seed 42

# 列出预设
.\.venv\Scripts\python.exe -m meowcannery presets
```

未安装环境时，使用 Python 3.11 或更新版本创建虚拟环境并安装项目：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

构建已有 OCR 只需基础依赖。首次本地 OCR 还需要 PaddleOCR-VL 及与设备匹配的 PaddlePaddle；本机已有可用环境，部署说明见 [开发指南](docs/开发指南.md)。

## 预设和插件

优先通过配置适配新书：

```powershell
.\.venv\Scripts\python.exe -m meowcannery init-book mybook --title "新书名称" --pdf "D:\资料\新书.pdf" --preset chapter_answers
```

生成 `books/mybook.json` 后，可修改页码范围、章节目录和 `rules` 覆盖项，不必修改公共代码。

| 预设               | 适用版式                               |
| ------------------ | -------------------------------------- |
| `chapter_answers`  | 每章先列习题，再按小节和题号给出答案   |
| `inline_answers`   | 每道题紧跟“答案：”“解析：”             |
| `medical_abx`      | A 型单选、B 型配伍、X 型多选，连续题号 |
| `analytical_guide` | 最佳选择、配伍选择、区间答案及计算题   |

需要代码时，在 `plugins/` 增加插件并在书籍配置中指定名称。也支持 Python `meowcannery.plugins` entry point。完整接口和示例见 [插件开发指南](docs/开发指南.md#新增书籍与插件)。

预设用于匹配版式，不会自动理解所有书籍；新书首次构建须检查章节、题号及答案覆盖情况。

## 输出与质量检查

- `*_Exameow.xlsx`：用于 Exameow 导入，固定 15 列。
- `bank.json`：题库文本、章节、小节题号和原页定位。
- `构建报告.md` / `report.json`：统计和逐项待核对内容。
- `原页核对.html` / `review_pages/`：离线核对页面与扫描页图片，移动时保留相对目录。
- `summary.json`：最近一次成功导出的统计，界面读取此文件。

默认遇到空答案、重复题号、答案越界、重复选项、无法转写的公式或图片等问题时停止，并保留已有题库。需要先使用检查通过的题目时，可加 `--allow-review`；此时结果会明确标注为**部分题库**，遗漏与原因保留在报告中。

桌面面板对应勾选“仅导出检查通过的题目”，再点击“生成题库”；点击“原页核对”查看未导出的题目。

结构检查不能代替逐题审读。答案以提供的原书为依据；OCR 修复和原书勘误必须记录原文及理由，不自动猜写答案。

## 项目结构

```text
books/             每本书的配置、章节及页面范围
rules/             可继承的规则预设
plugins/           自定义书籍插件
meowcannery/       公共流程、命令行、桌面入口及内置解析器
corrections/       新书的逐处勘误
tests/             独立回归测试及 1.5.0 导入格式验证
docs/              扩展方法、导入格式依据
data/books/        原始书籍 PDF
data/ocr/          按书籍隔离的 OCR 缓存
output/            生成的题库与质量报告
```

两本书统一使用新入口，从原始 OCR 和 `corrections/<书籍配置名>/`（同名于 `books/<书籍配置名>.json`）中的勘误重新构建。

运行测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
