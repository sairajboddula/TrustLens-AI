"""
KYC Document Processing Agent

Retrieves document files from disk, runs EasyOCR, post-processes the raw text,
and extracts structured KYC fields (name, DOB, ID number, address) using
regex patterns.

Pipeline:
  1. For each document_id → load file path from DB (sync shim for LangGraph)
  2. Pre-process image (grayscale → adaptive threshold → resize)
  3. Run EasyOCR on image; for PDF pages convert to PIL images first
  4. Concatenate all page texts
  5. Regex-extract KYC fields from combined text
  6. Normalise and store extracted values in state
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List, Optional

from app.agents.state import KYCAgentState
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Lazy imports (heavy dependencies only when needed at runtime)
# ---------------------------------------------------------------------------

def _get_ocr_reader():
    """Return a cached EasyOCR reader instance."""
    import easyocr  # noqa: PLC0415
    # Use module-level singleton to avoid re-loading model for each call
    if not hasattr(_get_ocr_reader, "_reader"):
        from app.core.config import settings
        _get_ocr_reader._reader = easyocr.Reader(
            [settings.OCR_LANGUAGE],
            gpu=settings.OCR_GPU,
            verbose=False,
        )
    return _get_ocr_reader._reader


# ---------------------------------------------------------------------------
# Image pre-processing
# ---------------------------------------------------------------------------


def _preprocess_image(image_path: str):
    """
    Convert an image to a pre-processed NumPy array suitable for OCR.

    Steps:
    1. Open with PIL → convert to grayscale
    2. Apply adaptive Gaussian threshold via OpenCV
    3. Resize so the shorter side is at least 1 000 px (better OCR accuracy)
    4. Return as NumPy uint8 array
    """
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    pil_img = Image.open(image_path).convert("L")  # grayscale
    img_array = np.array(pil_img, dtype=np.uint8)

    # Adaptive threshold
    binary = cv2.adaptiveThreshold(
        img_array,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=10,
    )

    # Resize: ensure shorter dimension >= 1000px
    h, w = binary.shape
    min_dim = min(h, w)
    if min_dim < 1000:
        scale = 1000.0 / min_dim
        new_w = int(w * scale)
        new_h = int(h * scale)
        binary = cv2.resize(binary, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    return binary


def _pdf_to_images(pdf_path: str) -> list:
    """Convert each page of a PDF to a PIL Image."""
    try:
        from pdf2image import convert_from_path  # noqa: PLC0415
        images = convert_from_path(pdf_path, dpi=200)
        return images
    except Exception as exc:
        logger.warning(
            "pdf2image conversion failed, falling back to fitz",
            path=pdf_path,
            error=str(exc),
        )

    try:
        import fitz  # PyMuPDF  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415

        doc = fitz.open(pdf_path)
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        doc.close()
        return images
    except Exception as exc2:
        logger.error("PyMuPDF PDF conversion also failed", error=str(exc2))
        return []


# ---------------------------------------------------------------------------
# OCR execution
# ---------------------------------------------------------------------------


def _ocr_image_array(image_array) -> tuple[str, float]:
    """Run EasyOCR on a pre-processed image array. Returns (text, avg_confidence)."""
    reader = _get_ocr_reader()
    results = reader.readtext(image_array, detail=1)  # list of (bbox, text, conf)
    if not results:
        return "", 0.0
    texts = [r[1] for r in results]
    confidences = [r[2] for r in results]
    return " ".join(texts), (sum(confidences) / len(confidences))


def _ocr_pil_image(pil_image) -> tuple[str, float]:
    """Run OCR on a PIL Image by converting to a pre-processed array first."""
    import tempfile  # noqa: PLC0415

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
        pil_image.save(tmp_path, format="PNG")
    try:
        arr = _preprocess_image(tmp_path)
        return _ocr_image_array(arr)
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Field extraction via regex
# ---------------------------------------------------------------------------

# Name: look for "Name:", "Full Name:", etc.
_NAME_PATTERNS = [
    re.compile(
        r"(?:full\s*name|surname\s*/\s*given|name)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"([A-Z]{2,}(?:\s+[A-Z]{2,}){1,3})",  # ALL-CAPS block for machine-readable zones
    ),
]

# Date of birth: various date formats
_DOB_PATTERNS = [
    re.compile(
        r"(?:date\s+of\s+birth|dob|born)[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:date\s+of\s+birth|dob|born)[:\s]+(\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b",
        re.IGNORECASE,
    ),
]

# Document / ID number
_ID_PATTERNS = [
    re.compile(
        r"(?:passport\s*(?:no|number|#)|document\s*(?:no|number|#)|id\s*(?:no|number|#))[:\s]*([A-Z0-9]{6,12})",
        re.IGNORECASE,
    ),
    re.compile(r"\b([A-Z]{1,2}[0-9]{6,9})\b"),   # passport-style: AB1234567
    re.compile(r"\b([0-9]{9,12})\b"),              # national ID number
]

# Address: look for street/city/postcode block
_ADDRESS_PATTERNS = [
    re.compile(
        r"(?:address|residence|domicile)[:\s]+(.{10,120}?)(?:\n|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr)[,\s]+[A-Za-z\s]+(?:,\s*[A-Z]{2})?\s*\d{5,6})",
        re.IGNORECASE,
    ),
]


def _extract_field(text: str, patterns: list[re.Pattern]) -> Optional[str]:
    """Try each pattern in order; return the first match group 1 or None."""
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def _normalize_date(raw_date: str) -> Optional[str]:
    """
    Attempt to parse a raw date string and return ISO YYYY-MM-DD.
    Accepts DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD, and common variants.
    """
    from dateutil import parser as dateutil_parser  # noqa: PLC0415

    raw_date = raw_date.strip()
    try:
        dt = dateutil_parser.parse(raw_date, dayfirst=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    try:
        dt = dateutil_parser.parse(raw_date, dayfirst=False)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# DB helper (synchronous shim for use inside LangGraph node)
# ---------------------------------------------------------------------------


def _get_document_ids_for_submission(submission_id: str) -> List[str]:
    """
    Look up all document IDs belonging to *submission_id* from the DB.

    Used as a fallback when the initial state has no document_ids (e.g. when
    the Celery task was dispatched before the user finished uploading files).
    """
    import asyncio  # noqa: PLC0415

    from sqlalchemy import select  # noqa: PLC0415
    from app.core.database import AsyncSessionLocal  # noqa: PLC0415
    from app.models.document import Document  # noqa: PLC0415
    import uuid as _uuid  # noqa: PLC0415

    result: List[str] = []

    async def _fetch():
        async with AsyncSessionLocal() as session:
            rows = await session.execute(
                select(Document.id).where(
                    Document.kyc_submission_id == _uuid.UUID(submission_id)
                )
            )
            for row in rows.all():
                result.append(str(row[0]))

    try:
        try:
            asyncio.get_running_loop()
            import concurrent.futures  # noqa: PLC0415
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, _fetch())
                future.result(timeout=10)
        except RuntimeError:
            asyncio.run(_fetch())
    except Exception as exc:
        logger.warning("DB lookup for submission document IDs failed", error=str(exc))

    return result


def _get_document_paths(document_ids: List[str]) -> Dict[str, Optional[str]]:
    """
    Retrieve file storage paths for the given document IDs.

    Uses a synchronous DB session because LangGraph nodes run synchronously
    by default (async graph support requires AsyncGraph, which we compile
    separately).  Falls back to checking the UPLOAD_DIR on disk when the DB
    is unavailable.
    """
    import asyncio  # noqa: PLC0415

    from sqlalchemy import select  # noqa: PLC0415
    from app.core.database import AsyncSessionLocal  # noqa: PLC0415
    from app.models.document import Document  # noqa: PLC0415
    from app.core.config import settings  # noqa: PLC0415

    result: Dict[str, Optional[str]] = {doc_id: None for doc_id in document_ids}

    async def _fetch():
        async with AsyncSessionLocal() as session:
            rows = await session.execute(
                select(Document.id, Document.storage_path).where(
                    Document.id.in_(document_ids)
                )
            )
            for row in rows.all():
                result[str(row.id)] = row.storage_path

    try:
        # Python 3.10+ deprecates get_event_loop() when there is no running
        # loop; Python 3.12+ raises a DeprecationWarning that becomes an error
        # in 3.14.  Use get_running_loop() to detect the async context safely.
        try:
            asyncio.get_running_loop()
            # A loop is already running (e.g. inside FastAPI/uvicorn).
            # We cannot call loop.run_until_complete() here, so delegate to a
            # fresh thread that spins up its own event loop via asyncio.run().
            import concurrent.futures  # noqa: PLC0415

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, _fetch())
                future.result(timeout=10)
        except RuntimeError:
            # No running loop — safe to call asyncio.run() directly.
            asyncio.run(_fetch())
    except Exception as exc:
        logger.warning("DB lookup for document paths failed", error=str(exc))
        # Fallback: try UPLOAD_DIR
        upload_dir = settings.UPLOAD_DIR
        for doc_id in document_ids:
            for ext in (".jpg", ".jpeg", ".png", ".pdf"):
                candidate = os.path.join(upload_dir, doc_id + ext)
                if os.path.exists(candidate):
                    result[doc_id] = candidate
                    break

    return result


# ---------------------------------------------------------------------------
# Main agent node
# ---------------------------------------------------------------------------


def document_processing_agent(state: KYCAgentState) -> KYCAgentState:
    """
    LangGraph node: run OCR on all uploaded documents and extract KYC fields.

    Reads:
        state["document_ids"]

    Writes:
        state["ocr_results"]        – per-document OCR details
        state["extracted_name"]
        state["extracted_dob"]
        state["extracted_id_number"]
        state["extracted_address"]
        state["current_agent"]
        state["errors"]             – appends on failures
    """
    logger.info(
        "Document processing agent started",
        submission_id=state.get("kyc_submission_id"),
        document_count=len(state.get("document_ids") or []),
    )

    new_state: KYCAgentState = dict(state)  # type: ignore[assignment]
    new_state["current_agent"] = "document_processing_agent"

    document_ids: List[str] = state.get("document_ids") or []

    # Fallback: if no document_ids were passed in state (e.g. Celery task was
    # dispatched before documents were uploaded), look them up from the DB now.
    if not document_ids:
        submission_id = state.get("kyc_submission_id")
        if submission_id:
            document_ids = _get_document_ids_for_submission(submission_id)
            if document_ids:
                logger.info(
                    "Document processing: fetched document IDs from DB (state had none)",
                    submission_id=submission_id,
                    count=len(document_ids),
                )

    errors: List[str] = list(state.get("errors") or [])
    ocr_results: List[Dict[str, Any]] = []

    combined_text: List[str] = []

    # 1. Resolve file paths
    doc_paths = _get_document_paths(document_ids)

    for doc_id in document_ids:
        file_path = doc_paths.get(doc_id)
        if not file_path or not os.path.exists(file_path):
            msg = f"Document file not found for id={doc_id} (path={file_path})"
            logger.warning(msg, submission_id=state.get("kyc_submission_id"))
            errors.append(msg)
            ocr_results.append(
                {
                    "document_id": doc_id,
                    "raw_text": "",
                    "confidence": 0.0,
                    "processing_time_ms": 0,
                    "error": msg,
                }
            )
            continue

        t_start = time.perf_counter()
        raw_text = ""
        avg_conf = 0.0
        ocr_error: Optional[str] = None

        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".pdf":
                images = _pdf_to_images(file_path)
                if not images:
                    raise RuntimeError("PDF conversion produced no images")
                page_texts: List[str] = []
                page_confs: List[float] = []
                for img in images:
                    pt, pc = _ocr_pil_image(img)
                    page_texts.append(pt)
                    page_confs.append(pc)
                raw_text = " ".join(page_texts)
                avg_conf = sum(page_confs) / len(page_confs) if page_confs else 0.0
            else:
                img_array = _preprocess_image(file_path)
                raw_text, avg_conf = _ocr_image_array(img_array)

        except Exception as exc:
            ocr_error = f"OCR failed for document {doc_id}: {exc}"
            logger.error(
                "OCR error",
                submission_id=state.get("kyc_submission_id"),
                doc_id=doc_id,
                error=str(exc),
                exc_info=True,
            )
            errors.append(ocr_error)

        elapsed_ms = int((time.perf_counter() - t_start) * 1000)

        ocr_results.append(
            {
                "document_id": doc_id,
                "raw_text": raw_text,
                "confidence": round(avg_conf, 4),
                "processing_time_ms": elapsed_ms,
                "error": ocr_error,
            }
        )

        if raw_text:
            combined_text.append(raw_text)

    full_text = "\n".join(combined_text)

    # 2. Extract KYC fields from combined OCR text
    extracted_name = _extract_field(full_text, _NAME_PATTERNS)
    raw_dob = _extract_field(full_text, _DOB_PATTERNS)
    extracted_dob = _normalize_date(raw_dob) if raw_dob else None
    extracted_id_number = _extract_field(full_text, _ID_PATTERNS)
    extracted_address = _extract_field(full_text, _ADDRESS_PATTERNS)

    # 3. Write back to state
    new_state["ocr_results"] = ocr_results
    new_state["extracted_name"] = extracted_name
    new_state["extracted_dob"] = extracted_dob
    new_state["extracted_id_number"] = extracted_id_number
    new_state["extracted_address"] = extracted_address
    new_state["errors"] = errors

    logger.info(
        "Document processing agent completed",
        submission_id=state.get("kyc_submission_id"),
        documents_processed=len(ocr_results),
        extracted_name=extracted_name,
        extracted_dob=extracted_dob,
        extracted_id_number=extracted_id_number,
        ocr_errors=sum(1 for r in ocr_results if r.get("error")),
    )

    return new_state
