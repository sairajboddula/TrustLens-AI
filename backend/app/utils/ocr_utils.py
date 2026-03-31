"""
OCR Utilities

Provides image pre-processing, EasyOCR text extraction, PDF-to-image
conversion, and regex-based KYC field extraction.

All public functions are designed to be called from async contexts via
asyncio.to_thread() since EasyOCR and OpenCV are synchronous.
"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# EasyOCR reader (module-level singleton)
# ---------------------------------------------------------------------------

_ocr_reader = None


def _get_reader():
    """Return the cached EasyOCR Reader, creating it on first call."""
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr  # noqa: PLC0415
        from app.core.config import settings  # noqa: PLC0415

        _ocr_reader = easyocr.Reader(
            [settings.OCR_LANGUAGE],
            gpu=settings.OCR_GPU,
            verbose=False,
        )
    return _ocr_reader


# ---------------------------------------------------------------------------
# Image pre-processing
# ---------------------------------------------------------------------------


def preprocess_image(image_path: str):
    """
    Load an image and apply pre-processing to improve OCR accuracy.

    Steps:
      1. Open with PIL and convert to grayscale
      2. Apply adaptive Gaussian thresholding (OpenCV)
      3. Resize so the shortest side is at least 1 000 px

    Returns:
        NumPy uint8 array suitable for EasyOCR.

    Raises:
        FileNotFoundError: if *image_path* does not exist.
        RuntimeError: if OpenCV or PIL is unavailable.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    pil_img = Image.open(image_path).convert("L")
    arr = np.array(pil_img, dtype=np.uint8)

    # Adaptive threshold
    binary = cv2.adaptiveThreshold(
        arr,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=10,
    )

    # Upscale if too small
    h, w = binary.shape
    min_dim = min(h, w)
    if min_dim < 1000:
        scale = 1000.0 / min_dim
        new_w, new_h = int(w * scale), int(h * scale)
        binary = cv2.resize(binary, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    return binary


# ---------------------------------------------------------------------------
# Text extraction – image
# ---------------------------------------------------------------------------


def extract_text_from_image(image_path: str) -> Tuple[str, float]:
    """
    Extract text from an image file using EasyOCR.

    Returns:
        Tuple of (raw_text: str, average_confidence: float)
    """
    processed = preprocess_image(image_path)
    reader = _get_reader()
    results = reader.readtext(processed, detail=1)

    if not results:
        return "", 0.0

    texts = [r[1] for r in results]
    confidences = [r[2] for r in results]
    avg_conf = sum(confidences) / len(confidences)
    return " ".join(texts), round(avg_conf, 4)


async def async_extract_text_from_image(image_path: str) -> Tuple[str, float]:
    """Async wrapper: runs OCR in a thread pool."""
    return await asyncio.to_thread(extract_text_from_image, image_path)


# ---------------------------------------------------------------------------
# Text extraction – PDF
# ---------------------------------------------------------------------------


def extract_text_from_pdf(pdf_path: str) -> Tuple[str, float]:
    """
    Convert each PDF page to an image and run OCR.

    Returns:
        Tuple of (combined_text: str, average_confidence: float)

    Falls back to PyMuPDF if pdf2image / poppler are unavailable.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    images = _pdf_to_pil_images(pdf_path)
    if not images:
        logger.warning("PDF produced no images", path=pdf_path)
        return "", 0.0

    page_texts: List[str] = []
    page_confs: List[float] = []

    for pil_img in images:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
            pil_img.save(tmp_path, format="PNG")
        try:
            text, conf = extract_text_from_image(tmp_path)
            page_texts.append(text)
            page_confs.append(conf)
        finally:
            os.unlink(tmp_path)

    combined = " ".join(page_texts)
    avg_conf = sum(page_confs) / len(page_confs) if page_confs else 0.0
    return combined, round(avg_conf, 4)


async def async_extract_text_from_pdf(pdf_path: str) -> Tuple[str, float]:
    """Async wrapper: runs PDF OCR in a thread pool."""
    return await asyncio.to_thread(extract_text_from_pdf, pdf_path)


def _pdf_to_pil_images(pdf_path: str) -> list:
    """Try pdf2image first, fall back to PyMuPDF."""
    try:
        from pdf2image import convert_from_path  # noqa: PLC0415
        return convert_from_path(pdf_path, dpi=200)
    except Exception:
        pass
    try:
        import fitz  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415

        doc = fitz.open(pdf_path)
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        doc.close()
        return images
    except Exception as exc:
        logger.error("PDF-to-image conversion failed", error=str(exc))
        return []


# ---------------------------------------------------------------------------
# KYC field extraction
# ---------------------------------------------------------------------------

_NAME_RE = [
    re.compile(
        r"(?:full\s*name|surname\s*/\s*given\s*names?|name)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        re.IGNORECASE,
    ),
    re.compile(r"\b([A-Z]{2,}(?:\s+[A-Z]{2,}){1,4})\b"),
]

_DOB_RE = [
    re.compile(
        r"(?:date\s+of\s+birth|dob|born)[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:date\s+of\s+birth|dob|born)[:\s]+(\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})\b",
        re.IGNORECASE,
    ),
]

_ID_RE = [
    re.compile(
        r"(?:passport\s*(?:no|number|#)|document\s*(?:no|number)|id\s*(?:no|number|#))[:\s]*([A-Z0-9]{6,12})",
        re.IGNORECASE,
    ),
    re.compile(r"\b([A-Z]{1,2}[0-9]{6,9})\b"),
    re.compile(r"\b([0-9]{9,12})\b"),
]

_ADDR_RE = [
    re.compile(
        r"(?:address|residence|domicile)[:\s]+(.{10,150}?)(?:\n|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr)[,\s]+[A-Za-z\s]+(?:,\s*[A-Z]{2})?\s*[\d]{4,6})",
        re.IGNORECASE,
    ),
]


def _first_match(text: str, patterns: list) -> Optional[str]:
    for pat in patterns:
        m = pat.search(text)
        if m:
            return m.group(1).strip()
    return None


def _normalize_date_str(raw: str) -> Optional[str]:
    """Parse an arbitrary date string and return YYYY-MM-DD, or None."""
    try:
        from dateutil import parser as dp  # noqa: PLC0415

        dt = dp.parse(raw.strip(), dayfirst=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    try:
        from dateutil import parser as dp  # noqa: PLC0415

        dt = dp.parse(raw.strip(), dayfirst=False)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def extract_kyc_fields(text: str) -> Dict[str, Optional[str]]:
    """
    Extract structured KYC fields from raw OCR text using regex patterns.

    Args:
        text: Raw OCR text (may span multiple pages / documents).

    Returns:
        Dictionary with keys:
            name (str | None)
            date_of_birth (str | None)  – YYYY-MM-DD normalised
            id_number (str | None)
            address (str | None)
    """
    name = _first_match(text, _NAME_RE)
    raw_dob = _first_match(text, _DOB_RE)
    dob = _normalize_date_str(raw_dob) if raw_dob else None
    id_number = _first_match(text, _ID_RE)
    address = _first_match(text, _ADDR_RE)

    return {
        "name": name,
        "date_of_birth": dob,
        "id_number": id_number,
        "address": address,
    }


async def async_extract_kyc_fields(text: str) -> Dict[str, Optional[str]]:
    """Async wrapper (CPU-bound, runs in thread pool)."""
    return await asyncio.to_thread(extract_kyc_fields, text)
