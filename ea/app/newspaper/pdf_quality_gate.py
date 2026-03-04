from __future__ import annotations


def _count_pdf_images(pdf_reader) -> int:
    total = 0
    for page in getattr(pdf_reader, "pages", []):
        try:
            res = page.get("/Resources") or {}
            xobj = res.get("/XObject") if hasattr(res, "get") else None
            if xobj is None:
                continue
            try:
                xobj = xobj.get_object()
            except Exception:
                pass
            if not hasattr(xobj, "items"):
                continue
            for _, obj in xobj.items():
                try:
                    target = obj.get_object()
                except Exception:
                    target = obj
                subtype = ""
                try:
                    subtype = str(target.get("/Subtype") or "")
                except Exception:
                    subtype = ""
                if subtype == "/Image":
                    total += 1
        except Exception:
            continue
    return total


def validate_newspaper_pdf_bytes(
    pdf_bytes: bytes, *, min_pages: int = 4, min_images: int = 3
) -> tuple[bool, str]:
    try:
        import io
        from pypdf import PdfReader
    except Exception as e:
        return False, f"pdf_validation_dependency_missing:{e}"
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        page_count = len(reader.pages)
        if page_count < min_pages:
            return False, f"page_count:{page_count}<min:{min_pages}"
        first_text = ""
        try:
            first_text = str(reader.pages[0].extract_text() or "")
        except Exception:
            first_text = ""
        if "Tibor Daily" not in first_text:
            return False, "missing_masthead:Tibor Daily"
        image_count = _count_pdf_images(reader)
        if image_count < min_images:
            return False, f"image_count:{image_count}<min:{min_images}"
        blob = first_text[:8000]
        for banned in ("OODA Diagnostic", "statusCode", "FST_ERR_VALIDATION", "Traceback"):
            if banned in blob:
                return False, f"banned_token:{banned}"
        return True, f"ok:pages={page_count},images={image_count}"
    except Exception as e:
        return False, f"pdf_validation_error:{e}"
