from fastapi import APIRouter, UploadFile, File
from pdfminer.high_level import extract_text
from io import BytesIO
from pdf2image import convert_from_bytes
import pytesseract

router = APIRouter()

@router.post("/debug/extract-text")
async def debug_extract_text(file: UploadFile = File(...)):
    data = await file.read()
    # PDFMiner
    try:
        pdfminer_text = extract_text(BytesIO(data)) or ""
    except Exception:
        pdfminer_text = ""
    # OCR (prima pagina)
    try:
        images = convert_from_bytes(data, dpi=300, first_page=1, last_page=1, fmt="png", thread_count=1)
        ocr_text = pytesseract.image_to_string(images[0], lang="ita+eng") if images else ""
    except Exception:
        ocr_text = ""

    return {
        "len_pdfminer": len(pdfminer_text),
        "len_ocr": len(ocr_text),
        "sample_pdfminer": pdfminer_text[:600],
        "sample_ocr": ocr_text[:600]
    }
