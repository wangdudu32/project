"""PDF 校验与分页渲染。PDFium 操作使用锁，避免多线程同时进入。"""
import threading
from pathlib import Path

import pypdfium2 as pdfium

PDF_LOCK = threading.Lock()


def pdf_page_count(path: Path, max_pages: int = 200) -> int:
    try:
        with PDF_LOCK, pdfium.PdfDocument(path) as document:
            count = len(document)
            if not 1 <= count <= max_pages:
                raise ValueError(f"PDF 页数需要在 1～{max_pages} 页之间。")
            return count
    except pdfium.PdfiumError as exc:
        raise ValueError("无法读取 PDF，请上传未加密、未损坏的文件。") from exc


def parse_pdf_to_images(pdf_path: str, output_dir: str, max_pages: int = 10) -> list[dict]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    pages = []
    with PDF_LOCK, pdfium.PdfDocument(pdf_path) as document:
        count = min(len(document), max_pages)
        if not count:
            raise ValueError("PDF 没有可读取的页面。")
        indices = [round(i * (len(document) - 1) / max(1, count - 1)) for i in range(count)]
        for index in indices:
            page = document[index]
            try:
                scale = min(2, 1600 / max(page.get_size()))
                bitmap = page.render(scale=scale)
                try:
                    path = directory / f"page_{index + 1}.png"
                    image = bitmap.to_pil()
                    try:
                        image.save(path)
                    finally:
                        image.close()
                finally:
                    bitmap.close()
                pages.append({"image_path": str(path), "page": index + 1})
            finally:
                page.close()
    return pages
