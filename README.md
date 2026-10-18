# 喵罐头（MeowCannery）

把带有习题和参考答案的扫描资料整理成可导入 [Exameow（过了喵）](https://github.com/heshengtao/exameow) 的题库。支持本地 OCR、按版式解析、题目检查、Excel 导出与抽题组卷。

本仓库提供程序、通用规则和原创示例。自己的 PDF、识别缓存、资料配置、勘误和生成题库保存在本地，默认由 Git 忽略。

[下载 Exameow](https://github.com/heshengtao/exameow/releases) · [开发与扩展指南](docs/开发指南.md)

## 开始使用

### 1. 安装基础环境

需要 Python 3.11 或更新版本；下面以 Windows、Python 3.12 为例。桌面面板需要 Python 自带的 Tkinter。

下载本项目源码，在项目目录打开 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

基础安装用于解析已有 OCR 文本、导出和组卷。识别自己的扫描 PDF 还需配置本地 OCR 环境，见下文。

### 2. 先体验原创示例

```powershell
.\.venv\Scripts\python.exe -m meowcannery demo
```

示例由六道原创常识题组成，覆盖单选、多选、判断、填空和简答，不需要 PDF、GPU 或 OCR 模型。运行后可在 `output/demo/` 找到 `原创入门示例_Exameow.xlsx`。示例输入为手写文本，用于体验流程，不代表扫描识别效果。

也可以双击 `启动喵罐头.cmd`，在桌面面板点击“体验示例”。

### 3. 添加自己的 PDF

1. 打开桌面面板，点击“添加 PDF”。
2. 填写资料名称，选择接近原书的答案版式。
3. 如需缩小页码范围或指定章节起点，编辑新生成的 `books/<资料ID>.json`。
4. 配置 OCR 环境后点击“识别扫描页”，已有页面缓存会复用。
5. 点击“生成题库”，查看输出目录中的报告和待核对记录。
6. 在 Exameow 的题库导入页面选择生成的 `*_Exameow.xlsx`，检查题数、章节和内容。

输入资料需包含可对应的习题与答案。多栏、跨页、图片题、结构式和特殊答案排版可能需要调整规则并人工核对。

## 本地 OCR

扫描识别使用 PaddleOCR-VL。请先按 [PaddleOCR 官方安装说明](https://www.paddleocr.ai/latest/en/version3.x/installation.html) 安装适合系统和设备的 PaddlePaddle 及支持 VL 的 PaddleOCR，然后检查：

```powershell
.\.venv\Scripts\python.exe -c "from paddleocr import PaddleOCRVL"
.\.venv\Scripts\python.exe -m meowcannery doctor
```

当前代码调用 `PaddleOCRVL(pipeline_version="v1.6")`；使用的 PaddleOCR 版本须提供该接口。首次加载可能下载模型，耗时和资源需求取决于设备。基础安装不自动安装识别模型或 GPU 驱动。Windows 桌面面板是主要操作入口，命令行也可用于独立部署；其他系统的 OCR 环境请以官方支持范围为准。

## 选择规则

| 预设 | 适合的版式 |
| --- | --- |
| `chapter_answers` | 每章先列习题，再集中给出答案 |
| `inline_answers` | 每道题后紧跟“答案：”“解析：” |
| `matching_answers` | 共用选项、配伍选择、区间答案及综合题 |
| `medical_abx` | A 型单选、B 型配伍、X 型多选，题号连续 |

预设匹配的是排版结构。新资料先用一个完整章节试跑，确认题目、选项和答案对应后再处理更多页面。资料特有规则放在本地配置的 `rules` 字段中；插件扩展见 [开发指南](docs/开发指南.md)。

## 常用命令

命令中的 `mybook` 是你创建的资料 ID，可用 `list` 查看。面板创建的 ID 也可直接用于命令行。

```powershell
# 查看资料、规则和环境
.\.venv\Scripts\python.exe -m meowcannery list
.\.venv\Scripts\python.exe -m meowcannery presets
.\.venv\Scripts\python.exe -m meowcannery doctor

# 从命令行添加自己的资料
.\.venv\Scripts\python.exe -m meowcannery init-book mybook --title "我的学习资料" --pdf "D:\资料\练习.pdf" --preset chapter_answers

# 按资料配置的页码范围识别，中断后可继续
.\.venv\Scripts\python.exe -m meowcannery ocr mybook

# 生成题库；all 表示处理全部本地资料
.\.venv\Scripts\python.exe -m meowcannery build mybook

# 仅导出检查通过的题目，其余内容保留在核对报告中
.\.venv\Scripts\python.exe -m meowcannery build mybook --allow-review

# 从生成的题库抽题组卷
.\.venv\Scripts\python.exe -m meowcannery quiz mybook --single 20 --multi 5 --seed 42
```

OCR 页码从 PDF 的第 1 个物理页开始计数，可能与印刷页码不同。范围应覆盖完整习题和对应答案；同一资料再次运行会继续识别缺失页。

## 输出与核对

文件位于 `output/<资料ID>/`：

| 文件 | 用途 |
| --- | --- |
| `*_Exameow.xlsx` | 导入 Exameow 的 15 列 Excel 题库 |
| `bank.json` | 导出的题目、章节、解析和来源定位 |
| `构建报告.md`、`report.json` | 统计、解析问题和待核对项 |
| `原页核对.html`、`review_pages/` | 在浏览器中对照原页核查问题 |
| `summary.json` | 最近一次成功导出的摘要，供桌面面板显示 |

默认发现空答案、重复题号、选项异常、未转写公式或图像内容时停止，保留已有题库。使用 `--allow-review` 或勾选“仅导出检查通过的题目”后，结果会标明为部分题库，遗漏与原因写入报告。

结构检查不能替代内容审校。请对照原资料核查 OCR 和答案，尤其留意题目数量、章节归属、公式、单位和图片信息。

## Exameow 兼容性

已验证的版本范围为 **1.4.4–1.6.1，含两端**，针对本项目原生 15 列 XLSX 的导入字段：题型、题干、选项、答案、解析、学科、章节和难度。范围内五个版本的官方导入器均经过运行验证，1.4.4 和 1.6.1 另有源码构建浏览器界面的导入与持久化验证；这不等同于各平台原生安装包的全功能验证。

更早的被测版本会丢失学科、章节和难度；范围外的新版尚未验证。

新生成的 XLSX 已处理非 BMP 字符的编码问题，验证覆盖 emoji、生僻汉字、数学字母和组合表情。旧题库应从原始数据重新生成再导入；已经损坏的导入记录不能自动恢复。该处理针对喵罐头生成的文件。

## 仓库与个人资料

公开目录：

```text
meowcannery/       程序、通用解析、导出和操作面板
rules/            通用版式预设
plugins/          插件入口与通用扩展示例
examples/demo/    原创入门示例
docs/             配置和扩展说明
```

以下内容仅用于本地，默认不纳入 Git：

- `books/*.json`：个人资料配置，可能含本机 PDF 路径。
- `corrections/<资料ID>/`：个人原文修正与勘误依据。
- `data/`：PDF、OCR 文本、扫描页和识别模型相关缓存。
- `output/`：个人题库、报告、组卷与核对页面。
- `tests/`、`reports/`：本地测试与验证产物。
- `plugins/local_*.py`、`rules/local_*.json`：个人扩展。

保留自己的原始资料和备份，只分享有权公开的内容。
