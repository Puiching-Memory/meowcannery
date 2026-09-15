"""按书籍隔离缓存，逐页落盘，支持中断后继续的本地 OCR。"""
import hashlib
import json
import os
import time
from pathlib import Path


def recognize(pdf, output, *, pages=None, dpi=150, batch=4):
    import pymupdf

    pdf, output = Path(pdf), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    with pdf.open("rb") as source:
        fingerprint = hashlib.file_digest(source, "sha256").hexdigest()
    with pymupdf.open(pdf) as document:
        selected = sorted(set(pages if pages is not None else range(1, len(document) + 1)))
        if not selected or min(selected) < 1 or max(selected) > len(document):
            raise ValueError("OCR 页码必须在 PDF 范围内（从 1 开始）。")
        manifest = {"pdf": pdf.name, "sha256": fingerprint, "page_count": len(document),
                    "dpi": dpi, "engine": "PaddleOCR-VL-1.6"}
        if manifest_path.exists():
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
            if any(previous.get(k) != manifest[k] for k in ("sha256", "dpi", "engine")):
                raise ValueError("OCR 缓存与 PDF 或识别配置不一致，请使用新缓存目录。")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        pending = [p for p in selected if not (output / f"p{p:04d}.md").exists()]
        print(f"OCR：{len(selected) - len(pending)}/{len(selected)} 页已缓存，待识别 {len(pending)} 页", flush=True)
        if not pending:
            return
        if batch < 1 or dpi < 72:
            raise ValueError("batch 必须为正整数，dpi 至少为 72。")
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        from paddleocr import PaddleOCRVL
        pipeline = PaddleOCRVL(pipeline_version="v1.6")
        started = time.monotonic()
        for start in range(0, len(pending), batch):
            chunk = pending[start:start + batch]
            images = []
            for page in chunk:
                path = output / f"p{page:04d}.png"
                if not path.exists():
                    document[page - 1].get_pixmap(dpi=dpi).save(str(path))
                images.append(str(path))
            results = pipeline.predict(images)
            count = 0
            for page, result in zip(chunk, results):
                # 每页独立暂存，完整结果生成后才原子替换 Markdown。
                # 图片也按页隔离，避免不同页面的相同坐标文件名互相覆盖。
                staging = output / "pages" / f"p{page:04d}"
                staging.mkdir(parents=True, exist_ok=True)
                result.save_to_json(save_path=str(staging))
                result.save_to_markdown(save_path=str(staging))
                markdown = staging / f"p{page:04d}.md"
                if not markdown.exists():
                    raise RuntimeError(f"第 {page} 页 OCR 没有写出 Markdown。")
                content = markdown.read_text(encoding="utf-8")
                content = content.replace("imgs/", f"pages/p{page:04d}/imgs/")
                temporary = output / f"p{page:04d}.md.tmp"
                temporary.write_text(content, encoding="utf-8")
                temporary.replace(output / f"p{page:04d}.md")
                count += 1
                elapsed = time.monotonic() - started
                print(f"[{start + count}/{len(pending)}] PDF 第 {page} 页，耗时 {elapsed:.0f}s", flush=True)
            if count != len(chunk):
                raise RuntimeError("OCR 返回页数不足；重新运行可以继续。")
