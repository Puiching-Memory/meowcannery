"""所有功能共用一个命令行入口。"""
import argparse
import json
import sys
from pathlib import Path

from .catalog import ROOT, books, get_book
from .export import TARGET_VERSION, read_xlsx
from .pipeline import build, required_pages
from .presets import book_rules, load_preset
from .validation import validate_bank


def executable_version(path):
    if sys.platform != "win32" or not Path(path).is_file():
        return None
    import ctypes
    from ctypes import wintypes
    dll = ctypes.windll.version
    size = dll.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return None
    buffer = ctypes.create_string_buffer(size)
    if not dll.GetFileVersionInfoW(str(path), 0, size, buffer):
        return None
    pointer = ctypes.c_void_p()
    length = wintypes.UINT()
    if not dll.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        return None
    values = ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD))
    return ".".join(map(str, (values[2] >> 16, values[2] & 65535, values[3] >> 16)))


def doctor():
    from importlib.util import find_spec
    version = executable_version(ROOT / "Exameow.exe")
    print(f"Python：{sys.version.split()[0]}\nExameow：{version or '未找到 Windows 版本信息'}（导出目标 {TARGET_VERSION}）")
    missing = []
    for module in ("openpyxl", "pymupdf"):
        found = find_spec(module) is not None
        print(f"{module}：{'可用' if found else '未安装'}")
        if not found:
            missing.append(module)
    print(f"PaddleOCR（仅 OCR 需要）：{'可用' if find_spec('paddleocr') else '未安装'}")
    for book in books():
        book_rules(book)
        pages = required_pages(book)
        cached = sum((book.cache / f"p{p:04d}.md").is_file() for p in pages)
        try:
            pdf = book.pdf.name
        except ValueError as error:
            pdf = str(error)
        print(f"\n{book.id} · {book.title}\n  PDF：{pdf}\n  OCR：{cached}/{len(pages)} 页\n  插件：{book.plugin} · 预设：{book.preset}")
    return 1 if missing or (version and version != TARGET_VERSION) else 0


def parser():
    command = argparse.ArgumentParser(prog="meowcannery", description="扫描复习指南题库构建 · Exameow 1.5.0")
    sub = command.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="列出书籍")
    sub.add_parser("presets", help="列出规则预设")
    sub.add_parser("doctor", help="检查程序版本、依赖和缓存进度")
    sub.add_parser("gui", help="打开桌面操作面板")
    ocr = sub.add_parser("ocr", help="本地识别，自动续跑缺失页面")
    ocr.add_argument("book")
    ocr.add_argument("--dpi", type=int, default=150)
    ocr.add_argument("--batch", type=int, default=4)
    ocr.add_argument("--pages", help="指定 PDF 页码，如 11-13,21（从 1 开始）")
    export = sub.add_parser("build", help="构建题库并输出质量报告")
    export.add_argument("book", help="书籍 ID 或 all")
    export.add_argument("--allow-review", action="store_true", help="有待核对项时仅导出检查通过的题目，并明确标为部分题库")
    check = sub.add_parser("validate", help="校验已有 Exameow XLSX")
    check.add_argument("path", type=Path)
    new = sub.add_parser("init-book", help="从预设生成新书配置")
    new.add_argument("id")
    new.add_argument("--title", required=True)
    new.add_argument("--pdf", required=True)
    new.add_argument("--preset", default="chapter_answers")
    new.add_argument("--subject", default="")
    quiz = sub.add_parser("quiz", help="从已生成题库抽题组卷")
    quiz.add_argument("book")
    quiz.add_argument("--single", type=int, default=10)
    quiz.add_argument("--multi", type=int, default=0)
    quiz.add_argument("--fill", type=int, default=0)
    quiz.add_argument("--short", type=int, default=0)
    quiz.add_argument("--chapter", default="")
    quiz.add_argument("--seed", type=int, default=7)
    quiz.add_argument("--out", type=Path)
    return command


def page_selection(value):
    pages = set()
    for part in value.split(","):
        pair = part.split("-")
        if len(pair) == 1:
            pages.add(int(pair[0]))
        elif len(pair) == 2 and int(pair[0]) <= int(pair[1]):
            pages.update(range(int(pair[0]), int(pair[1]) + 1))
        else:
            raise ValueError("页码格式应为 11-13,21。")
    return sorted(pages)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "list":
            for book in books():
                print(f"{book.id:10} {book.title}  [{book.plugin} / {book.preset}]")
        elif args.command == "presets":
            for path in sorted((ROOT / "rules").glob("*.json")):
                rule = load_preset(path.stem)
                print(f"{path.stem}\n  {rule['name']}：{rule['description']}")
        elif args.command == "doctor":
            return doctor()
        elif args.command == "gui":
            from .gui import launch
            launch()
        elif args.command == "ocr":
            from .ocr import recognize
            book = get_book(args.book)
            pages = page_selection(args.pages) if args.pages else required_pages(book)
            recognize(book.pdf, book.cache, pages=pages, dpi=args.dpi, batch=args.batch)
        elif args.command == "build":
            selected = books() if args.book == "all" else [get_book(args.book)]
            failed = False
            for book in selected:
                try:
                    build(book, allow_review=args.allow_review)
                except ValueError as error:
                    print(error, file=sys.stderr)
                    failed = True
            return int(failed)
        elif args.command == "validate":
            questions = read_xlsx(args.path)
            validate_bank(questions)
            print(f"通过：{len(questions)} 题，原生 15 列结构及答案校验无异常。")
        elif args.command == "init-book":
            import re
            import pymupdf
            if not re.fullmatch(r"[a-z][a-z0-9_]*", args.id):
                raise ValueError("书籍 ID 必须为小写字母、数字和下划线，首字符为字母。")
            load_preset(args.preset)
            path = ROOT / "books" / f"{args.id}.json"
            if path.exists():
                raise ValueError(f"配置已存在，未覆盖：{path}")
            pdf = Path(args.pdf).resolve()
            with pymupdf.open(pdf) as document:
                count = len(document)
            value = dict(id=args.id, title=args.title, subject=args.subject or args.title,
                         pdf_glob=str(pdf), ocr_dir=f"data/ocr/{args.id}", plugin="rule_based",
                         preset=args.preset, page_count=count, first_page=1, last_page=count)
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"已生成配置：{path}")
        elif args.command == "quiz":
            from .quiz import generate
            book = get_book(args.book)
            generate(read_xlsx(book.xlsx), args.out or book.output / "模拟卷",
                     single=args.single, multi=args.multi, fill=args.fill, short=args.short,
                     chapter=args.chapter, seed=args.seed)
        return 0
    except (ValueError, OSError, ImportError, KeyError) as error:
        print(f"无法完成：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
