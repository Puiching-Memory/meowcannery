import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import ts from 'typescript';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const manifest = JSON.parse(await fs.readFile(path.join(here, 'upstream/manifest.json'), 'utf8'));
const compiled = path.join(here, '.cache');
await fs.mkdir(compiled, { recursive: true });
for (const name of ['importParser.ts', 'types.ts']) {
  const bytes = await fs.readFile(path.join(here, 'upstream', name));
  assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), manifest.files[name], `${name} 上游源码发生变化`);
  // 只重定向 monorepo 模块路径；保持官方导入逻辑原样。
  const source = bytes.toString('utf8').replaceAll("'@exameow/shared'", "'./types.mjs'");
  const { outputText, diagnostics } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
    reportDiagnostics: true,
  });
  assert.equal(diagnostics?.length ?? 0, 0, '上游 TypeScript 转译失败');
  await fs.writeFile(path.join(compiled, name.replace('.ts', '.mjs')), outputText);
}
const { parseExcel } = await import(pathToFileURL(path.join(compiled, 'importParser.mjs')));
const types = { 单选题: 'single_choice', 多选题: 'multi_choice', 判断题: 'true_false', 填空题: 'fill_blank', 简答题: 'short_answer' };
const selected = process.argv.slice(2);
const ids = selected.length ? selected : ['yaoli', 'fenxi'];
for (const id of ids) {
  const directory = path.join(root, 'output', id);
  const bank = JSON.parse(await fs.readFile(path.join(directory, 'bank.json'), 'utf8'));
  const files = (await fs.readdir(directory)).filter(f => f.endsWith('_Exameow.xlsx'));
  assert.equal(files.length, 1, `${id} 应恰有一个导入文件`);
  const bytes = await fs.readFile(path.join(directory, files[0]));
  const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  const { questions } = parseExcel(buffer, files[0]);
  assert.equal(questions.length, bank.length, `${id} 导入题数不符`);
  bank.forEach((q, i) => {
    assert.deepEqual({ type: questions[i].type, stem: questions[i].stem, options: questions[i].options,
      answer: questions[i].answer, analysis: questions[i].analysis, subject: questions[i].subject,
      chapter: questions[i].chapter, difficulty: questions[i].difficulty }, {
      type: types[q.type], stem: q.stem.trim(), options: q.options.map(s => s.trim()),
      answer: q.answer.trim(), analysis: (q.explanation ?? '').trim(), subject: q.subject || undefined,
      chapter: q.chapter.trim(), difficulty: q.difficulty || undefined,
    }, `${id} 第 ${i + 1} 题导入发生变化`);
  });
  console.log(`Exameow ${manifest.version}: ${id} ${questions.length} 题逐字段导入验证通过`);
}
