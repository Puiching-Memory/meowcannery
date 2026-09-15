"""插件之外的统一流程：输入检查、解析、质量报告、导出。"""
import json
import re
import tempfile
from collections import Counter
from pathlib import Path

from .export import TARGET_VERSION, write_xlsx
from .corrections import apply_question_fixes
from .plugins import ParseResult, load_plugin
from .presets import book_rules
from .validation import question_errors, validate_bank


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def required_pages(book):
    ranges = book.rules.get("page_ranges", [[book.first_page, book.last_page]])
    pages = sorted({p for first, last in ranges for p in range(first, last + 1)})
    if not pages or pages[0] < book.first_page or pages[-1] > book.last_page:
        raise ValueError(f"{book.id} 页码配置超出允许范围。")
    return pages


def check_sources(book):
    missing = [page for page in required_pages(book) if not (book.cache / f"p{page:04d}.md").is_file()]
    if missing:
        raise ValueError(f"{book.title} 的 OCR 尚缺 {len(missing)} 页（如 {', '.join(map(str, missing[:8]))}）。"
                         f"请运行：python -m meowcannery ocr {book.id}")


def extra_errors(q):
    errors = list(q.get("review_reasons", []))
    values = [q.get("stem", ""), q.get("answer", ""), q.get("explanation", "")]
    if isinstance(q.get("options"), list):
        values.extend(q["options"])
    content = "\n".join(v for v in values if isinstance(v, str))
    if re.search(r"!\[[^]]*\]\(|\[原页图片\]", content):
        errors.append("题面或答案含图像，须对照原页补充；Exameow 1.5.0 导入题面为纯文本")
    commands = sorted(set(re.findall(r"\\[a-zA-Z]+", content)))
    if commands:
        errors.append("尚未转换的公式命令：" + "、".join(commands))
    return errors


def apply_fixes(book, questions):
    from .catalog import ROOT
    path = ROOT / "corrections" / book.id / "questions.json"
    return apply_question_fixes(questions, path)


def inspect_book(book, *, require_complete=True):
    if require_complete:
        check_sources(book)
    result = load_plugin(book.plugin)(book, book_rules(book))
    if not isinstance(result, ParseResult):
        raise TypeError("插件必须返回 ParseResult。")
    result.questions = apply_fixes(book, result.questions)
    accepted, review = [], []
    for q in result.questions:
        q.setdefault("subject", book.subject)
        errors = question_errors(q) + extra_errors(q)
        errors.extend(i["reason"] for i in result.issues
                      if i.get("chapter") == q.get("chapter") and i.get("section") == q.get("section")
                      and (i.get("number") is None or i["number"] == q.get("number")))
        errors = list(dict.fromkeys(errors))
        if errors:
            review.append({"question": q, "reasons": errors})
        else:
            accepted.append(q)
    return result, accepted, review


def build(book, *, allow_review=False):
    result, accepted, review = inspect_book(book)
    summary = dict(book=book.id, title=book.title, target_version=TARGET_VERSION,
                   detected=len(result.questions), valid=len(accepted), review=len(review),
                   parser_issues=len(result.issues),
                   types=dict(Counter(q["type"] for q in accepted)),
                   chapters=dict(Counter(q["chapter"] for q in accepted)))
    write_json(book.output / "report.json", {**summary, "questions_for_review": review, "issues": result.issues})
    from .review import write_review
    write_review(book, review, result.issues)
    notes = [f"# {book.title}构建报告", "", f"目标版本：Exameow {TARGET_VERSION}", "",
             f"识别 {len(result.questions)} 题；结构及文本检查通过 {len(accepted)} 题；待核对 {len(review)} 题；解析问题 {len(result.issues)} 项。", ""]
    if result.issues or review:
        notes.append("打开 [原页核对.html](原页核对.html) 按章节查阅待核对题目、答案及原书扫描页；详细记录见 `report.json`。默认构建会停止，不覆盖已有题库；`--allow-review` 仅导出检查通过的题目。\n")
    notes += ["| 章节 | 检查通过题数 |", "| --- | ---: |"]
    notes += [f"| {chapter} | {count} |" for chapter, count in summary["chapters"].items()]
    (book.output / "构建报告.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    if (result.issues or review) and not allow_review:
        raise ValueError(f"{book.title} 有待核对内容，未覆盖题库。查看 {book.output / '构建报告.md'}")
    validate_bank(accepted)
    write_xlsx(accepted, book.xlsx, book.subject)
    write_json(book.output / "bank.json", accepted)
    summary["exported"] = len(accepted)
    summary["partial"] = bool(result.issues or review)
    write_json(book.output / "summary.json", summary)
    print(f"{book.title}：已导出 {len(accepted)} 题 -> {book.xlsx}", flush=True)
    if summary["partial"]:
        print(f"本次为部分题库；另有 {len(review)} 题及 {len(result.issues)} 项解析问题待核对。", flush=True)
    return summary
