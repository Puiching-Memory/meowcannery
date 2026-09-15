"""把待核对题目和扫描原页放在可离线打开的页面中。"""
import html
import re


def write_review(book, review, issues):
    esc = lambda value: html.escape(str(value), quote=True)
    entries = []
    for item in review:
        q = item["question"]
        entries.append(dict(chapter=q["chapter"], title=f"{q.get('section', q['type'])} · 第 {q.get('number', '?')} 题",
                            text="\n".join([q["stem"], *[f"{chr(65+i)}. {o}" for i, o in enumerate(q["options"])]]),
                            answer=q["answer"], reasons=item["reasons"],
                            sources=[q.get("source", ""), q.get("answer_source", "")]))
    for item in issues:
        entries.append(dict(chapter=item.get("chapter", "未定位"),
                            title=f"解析记录 · {item.get('section', '')} {item.get('number') or ''}", text="",
                            answer="", reasons=[item["reason"]], sources=[item.get("source", "")]))
    pages = set()
    for entry in entries:
        related = []
        for source in entry["sources"]:
            match = re.fullmatch(r"p(\d{4})\.md", source)
            if match:
                page = int(match[1])
                related.extend(p for p in (page, page+1) if 1 <= p <= book.page_count)
        entry["pages"] = sorted(set(related))
        pages.update(related)
    available = set()
    note = ""
    if pages:
        try:
            pdf_path = book.pdf
        except ValueError:
            note = "当前未找到原 PDF；以下保留页码定位，恢复 PDF 后重新构建即可生成原页图像。"
        else:
            import pymupdf
            folder = book.output / "review_pages"
            folder.mkdir(parents=True, exist_ok=True)
            with pymupdf.open(pdf_path) as document:
                for page in sorted(pages):
                    if page <= len(document):
                        # 每次从 PDF 重建，避免更换原书后展示旧的扫描图。
                        document[page-1].get_pixmap(dpi=120).save(folder / f"p{page:04d}.png")
                        available.add(page)
    chapters = list(dict.fromkeys(e["chapter"] for e in entries))
    cards = []
    for entry in entries:
        scans = []
        for page in entry["pages"]:
            content = (f'<a href="review_pages/p{page:04d}.png" target="_blank" rel="noopener">'
                       f'<img loading="lazy" src="review_pages/p{page:04d}.png" alt="PDF 第 {page} 页扫描原文"></a>') if page in available else "原 PDF 暂不可用"
            scans.append(f'<details class="scan"><summary>PDF 第 {page} 页</summary>{content}</details>')
        cards.append(f'''<article data-chapter="{esc(entry['chapter'])}">
<p class="chapter">{esc(entry['chapter'])}</p><h2>{esc(entry['title'])}</h2>
<ul class="reasons">{''.join('<li>'+esc(r)+'</li>' for r in entry['reasons'])}</ul>
<pre>{esc(entry['text'])}</pre>
<details><summary>查看当前识别的答案（待核对）</summary><pre>{esc(entry['answer']) or '未识别到答案'}</pre></details>
<p class="hint">相关原页及下一页，供查看共用选项、跨页续题和答案。点击图像可放大。</p>
<div class="scans">{''.join(scans)}</div></article>''')
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ · 原页核对</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f3f6f9;color:#243447;font:16px/1.65 "Microsoft YaHei",sans-serif}
header,main{max-width:1100px;margin:auto;padding:28px}header{padding-bottom:8px}h1{font-size:28px;margin:0 0 8px}
h2{font-size:20px;margin:4px 0 12px}.lead,.hint{color:#617285}.hint{font-size:13px}nav{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}
input,select{font:inherit;padding:10px 14px;border:1px solid #c9d4de;border-radius:8px;background:white;max-width:100%}input{flex:1;min-width:220px}
article{background:white;border:1px solid #dce3eb;border-radius:12px;padding:24px;margin-bottom:20px;overflow-wrap:anywhere}
article[hidden]{display:none}.chapter{color:#267566;font-size:14px;margin:0}.reasons{background:#fff5df;border-radius:6px;padding:12px 12px 12px 34px;font-size:14px}
pre{white-space:pre-wrap;font:inherit;margin:14px 0}summary{cursor:pointer;color:#1c665a;padding:8px 0}details{border-top:1px solid #e8edf1}
img{display:block;width:100%;height:auto;border:1px solid #e4e8ed}.scans{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,400px),1fr));gap:16px}
.scan{align-self:start}.count{color:#617285;font-size:14px}@media(max-width:600px){header,main{padding:16px}article{padding:16px}h1{font-size:23px}}
</style>
<header><h1>__TITLE__ · 原页核对</h1>
<p class="lead">这些记录尚未进入导入题库。结构式、谱图及识别疑点请以扫描原页为准；识别的答案也可能需要修正。</p>
<p class="hint">__NOTE__</p><nav><select id="chapter" aria-label="按章节筛选"><option value="">全部章节</option>__OPTIONS__</select>
<input id="search" type="search" placeholder="搜索题目、题号或问题原因" aria-label="搜索核对记录"></nav><p class="count" id="count"></p></header>
<main>__CARDS__</main>
<script>
const cards=[...document.querySelectorAll('article')],chapter=document.querySelector('#chapter'),search=document.querySelector('#search');
function filter(){let n=0;for(const card of cards){card.hidden=(chapter.value&&card.dataset.chapter!==chapter.value)||!card.textContent.toLowerCase().includes(search.value.toLowerCase());if(!card.hidden)n++}document.querySelector('#count').textContent=`显示 ${n} / ${cards.length} 条记录`}
chapter.addEventListener('change',filter);search.addEventListener('input',filter);filter();
</script></html>'''
    for key, value in {"__TITLE__": esc(book.title), "__NOTE__": esc(note),
                       "__OPTIONS__": "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in chapters),
                       "__CARDS__": "".join(cards) or '<p>当前没有待核对记录。</p>'}.items():
        document = document.replace(key, value)
    path = book.output / "原页核对.html"
    path.write_text(document, encoding="utf-8")
    return path
