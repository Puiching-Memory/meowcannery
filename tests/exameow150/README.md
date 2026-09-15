# Exameow 1.5.0 导入格式验证

上游文件固定来自 [v1.5.0](https://github.com/heshengtao/exameow/tree/v1.5.0)：

- `frontend/src/utils/importParser.ts`
- `packages/shared/src/types.ts`

原文件与 Apache-2.0 LICENSE 位于 `upstream/`，SHA-256 记录在 `manifest.json`。测试只将工作区包导入路径改为本地 `types.mjs`，不修改导入行为。

```powershell
npm ci --prefix tests/exameow150 --ignore-scripts
node tests/exameow150/check.mjs yaoli fenxi
```

先运行 Python 构建命令生成 `output/<id>/bank.json` 和 XLSX。测试通过官方 `parseExcel` 读取实际 Excel 文件，比较所有题目的内容、题型、选项、答案、解析、学科、章节、难度及总题数。

Node 仅用于开发验证，不是用户构建题库的运行依赖。此测试不启动桌面程序或修改练习记录。
