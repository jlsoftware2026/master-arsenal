"""Independent structural and rendered-page quality checks for PDF artifacts."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def inspect_pdf_artifact(
    path: str | Path,
    *,
    render_directory: str | Path | None = None,
    minimum_text_characters: int = 20,
) -> dict[str, Any]:
    """Parse, extract, and raster-render each page using PyMuPDF.

    This is independent of ReportLab's writer checks. It detects malformed PDFs,
    empty/unreadable pages, clipped text spans, and pages that render nearly blank.
    Optional PNG previews are written only to the caller-selected directory.
    """
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - dependency installation failure
        raise RuntimeError("PDF quality inspection requires PyMuPDF") from exc

    source = Path(path).resolve(strict=True)
    if not source.is_file() or source.suffix.lower() != ".pdf":
        raise ValueError("PDF quality inspection requires an existing .pdf file")
    if minimum_text_characters < 0:
        raise ValueError("minimum_text_characters must be non-negative")
    preview_root = Path(render_directory).resolve() if render_directory is not None else None
    if preview_root is not None:
        preview_root.mkdir(parents=True, exist_ok=True)

    pages: list[dict[str, Any]] = []
    with fitz.open(source) as document:
        if document.is_encrypted:
            raise ValueError("Encrypted PDF artifacts are not accepted")
        if document.page_count < 1:
            raise ValueError("PDF contains no pages")
        for number, page in enumerate(document, start=1):
            rect = page.rect
            if rect.width <= 0 or rect.height <= 0:
                raise ValueError(f"PDF page {number} has invalid dimensions")
            text = page.get_text("text").strip()
            if len(text) < minimum_text_characters:
                raise ValueError(f"PDF page {number} contains insufficient extractable text")
            spans = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            spans.append(fitz.Rect(span["bbox"]))
            tolerance = 1.0
            for span in spans:
                if (span.x0 < -tolerance or span.y0 < -tolerance or
                    span.x1 > rect.width + tolerance or span.y1 > rect.height + tolerance):
                    raise ValueError(f"PDF page {number} contains text outside page bounds")
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
            samples = pixmap.samples
            if not samples or len(set(samples)) < 2:
                raise ValueError(f"PDF page {number} renders blank")
            if preview_root is not None:
                pixmap.save(preview_root / f"page-{number:03d}.png")
            pages.append({
                "page": number,
                "width_points": round(rect.width, 2),
                "height_points": round(rect.height, 2),
                "text_characters": len(text),
                "text_spans": len(spans),
                "rendered_width_px": pixmap.width,
                "rendered_height_px": pixmap.height,
            })
        metadata = document.metadata or {}
    return {
        "path": str(source),
        "page_count": len(pages),
        "file_size_bytes": source.stat().st_size,
        "title": metadata.get("title") or "",
        "pages": pages,
        "checks": {
            "parsed": True,
            "extractable_text": True,
            "text_within_page_bounds": True,
            "rendered_pages_nonblank": True,
        },
    }
