"""书籍配置及与当前工作目录无关的路径解析。"""
import json
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
