from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

try:
    import pypdf
except Exception:  # pragma: no cover
    pypdf = None


def _extract_with_fitz(pdf_path: Path) -> tuple[int, int, str]:
    doc = fitz.open(str(pdf_path))
    page_count = doc.page_count
    image_count = 0
    text = []
    for page in doc:
        image_count += len(page.get_images(full=True))
        text.append(page.get_text())
    return page_count, image_count, "\n".join(text)


def _extract_with_pypdf(pdf_path: Path) -> tuple[int, int, str]:
    reader = pypdf.PdfReader(str(pdf_path))
    page_count = len(reader.pages)
    image_count = 0
    text = []
    for page in reader.pages:
        try:
            text.append(page.extract_text() or "")
        except Exception:
            text.append("")
        try:
            image_count += len(getattr(page, "images", []) or [])
        except Exception:
            pass
        if image_count == 0:
            try:
                resources = page.get("/Resources")
                xobj = (resources or {}).get("/XObject")
                if xobj:
                    for obj in xobj.get_object().values():
                        try:
                            if obj.get_object().get("/Subtype") == "/Image":
                                image_count += 1
                        except Exception:
                            pass
            except Exception:
                pass
    return page_count, image_count, "\n".join(text)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python3 tests/check_newspaper_pdf.py <pdf_path>")
        return 2

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"FAIL: file not found: {pdf_path}")
        return 2

    if fitz is not None:
        page_count, image_count, full_text = _extract_with_fitz(pdf_path)
        backend = "PyMuPDF"
    elif pypdf is not None:
        page_count, image_count, full_text = _extract_with_pypdf(pdf_path)
        backend = "pypdf"
    else:
        print("FAIL: missing dependency (install PyMuPDF or pypdf)")
        return 2

    assert page_count >= 2, f"Expected multi-page issue, got {page_count}"
    assert image_count >= 3, f"Expected at least 3 embedded images, got {image_count}"

    banned = [
        "OODA Diagnostic",
        "MarkupGo API HTTP 400",
        "statusCode",
        "\"message\":",
        "\"code\":",
        "FST_ERR_VALIDATION",
        "Traceback",
    ]
    for token in banned:
        assert token not in full_text, f"Found banned debug token in PDF: {token}"

    required = [
        "Must know",
        "Worth knowing",
    ]
    for token in required:
        assert re.search(re.escape(token), full_text, re.IGNORECASE), f"Missing section heading: {token}"

    print(f"PASS: newspaper PDF smoke test ({backend})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
