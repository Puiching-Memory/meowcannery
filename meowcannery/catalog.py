"""书籍配置及与当前工作目录无关的路径解析。"""
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Book:
    id: str
    title: str
    subject: str
    pdf_glob: str
    ocr_dir: str
    plugin: str
    page_count: int
    first_page: int
    last_page: int
    preset: str = "chapter_answers"
    rules: dict = field(default_factory=dict)
    chapters: dict = field(default_factory=dict)
    config: str = ""

    @property
    def pdf(self):
        path = Path(self.pdf_glob)
        matches = ([path] if path.is_file() else []) if path.is_absolute() else list(ROOT.glob(self.pdf_glob))
        if len(matches) != 1:
            raise ValueError(f"{self.title}：需要唯一 PDF，匹配到 {len(matches)} 个（{self.pdf_glob}）。")
        return matches[0]

    @property
    def cache(self):
        return ROOT / self.ocr_dir

    @property
    def output(self):
        return ROOT / "output" / self.id

    @property
    def corrections(self):
        """勘误目录跟随 books/<配置名>.json 的文件名，未加载自配置文件时退回 id。"""
        return ROOT / "corrections" / (self.config or self.id)

    @property
    def xlsx(self):
        return self.output / f"{self.title}_Exameow.xlsx"


def books():
    return [Book(**json.loads(p.read_text(encoding="utf-8")), config=p.stem)
            for p in sorted((ROOT / "books").glob("*.json"))]


def get_book(book_id):
    for book in books():
        if book.id == book_id:
            return book
    raise ValueError(f"未知书籍 {book_id!r}，可用：" + "、".join(b.id for b in books()))


def create_book(book_id, title, pdf, *, preset="chapter_answers", subject=""):
    """创建仅保存在本地的资料配置，供 CLI 和桌面面板共用。"""
    from .presets import load_preset
    import pymupdf

    if not re.fullmatch(r"[a-z][a-z0-9_]*", book_id):
        raise ValueError("资料 ID 必须为小写字母、数字和下划线，首字符为字母。")
    if not title.strip():
        raise ValueError("资料名称不能为空。")
    if re.search(r'[\\/:*?"<>|\x00-\x1f]', title):
        raise ValueError("资料名称不能包含路径分隔符或文件名保留字符。")
    load_preset(preset)
    path = ROOT / "books" / f"{book_id}.json"
    if path.exists() or any(book.id == book_id for book in books()):
        raise ValueError(f"资料 ID 已存在，未覆盖：{book_id}")
    pdf = Path(pdf).expanduser().resolve()
    with pymupdf.open(pdf) as document:
        count = len(document)
    if count < 1:
        raise ValueError("PDF 没有可读取的页面。")
    value = dict(id=book_id, title=title.strip(), subject=subject.strip() or title.strip(),
                 pdf_glob=str(pdf), ocr_dir=f"data/ocr/{book_id}", plugin="rule_based",
                 preset=preset, page_count=count, first_page=1, last_page=count)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return get_book(book_id)


def install_demo():
    """复制原创演示到本地工作目录；不覆盖用户编辑过的缓存。"""
    source = ROOT / "examples" / "demo"
    value = json.loads((source / "book.json").read_text(encoding="utf-8"))
    path = ROOT / "books" / "demo.json"
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != value:
        raise ValueError("demo 配置已被修改，未覆盖。请使用已有配置或另取资料 ID。")
    cache = ROOT / value["ocr_dir"]
    cache.mkdir(parents=True, exist_ok=True)
    for page in (source / "ocr").glob("p*.md"):
        target = cache / page.name
        if not target.exists():
            shutil.copyfile(page, target)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return get_book("demo")
