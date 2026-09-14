"""Local Tesseract OCR with the existing page input/output interface."""
from __future__ import annotations

import logging
import os
import threading
from io import BytesIO
from typing import Any

import pytesseract
from PIL import Image, ImageOps

from .file_validation_service import DocumentError

log = logging.getLogger(__name__)
# Shared across service instances in this process, including request dependencies.
_OCR_LOCK = threading.Lock()


class TesseractOCRService:
    def __init__(self) -> None:
        self.lang = os.getenv("TESSERACT_LANG", "eng")
        self.timeout = float(os.getenv("TESSERACT_TIMEOUT_SECONDS", "120"))
        self.psm = int(os.getenv("TESSERACT_PSM", "3"))
        self.max_side = int(os.getenv("TESSERACT_MAX_SIDE", "2400"))
        if self.timeout <= 0 or self.max_side < 1 or self.psm not in range(3, 14):
            raise ValueError("Invalid Tesseract timeout, maximum side, or page segmentation mode.")
        os.environ.setdefault("OMP_THREAD_LIMIT", "1")
        command = os.getenv("TESSERACT_CMD", "").strip()
        if command:
            pytesseract.pytesseract.tesseract_cmd = command

    def transcribe(self, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not pages:
            raise DocumentError("NO_PAGES", "No document pages were provided for OCR.")
        results = []
        for page in pages:
            page_number = page.get("page_number", "unknown")
            try:
                page_number = int(page["page_number"])
                log.info("Tesseract processing started page=%s", page_number)
                # Lock includes decoding so simultaneous requests do not decode
                # multiple OCR images here. PDF conversion happens upstream.
                with _OCR_LOCK:
                    image = self._decode_image(page["image_bytes"])
                    try:
                        text = pytesseract.image_to_string(
                            image, lang=self.lang,
                            config=f"--psm {self.psm} -c preserve_interword_spaces=1",
                            timeout=self.timeout,
                        ).strip()
                    finally:
                        image.close()
                results.append({
                    "page_number": page_number,
                    "ocr_text": text or "[UNREADABLE]",
                    "native_text": page.get("native_text"),
                    "ocr_engine": "Tesseract",
                })
                log.info("Tesseract processing completed page=%s characters=%s",
                         page_number, len(text))
            except pytesseract.TesseractNotFoundError as exc:
                raise DocumentError("OCR_NOT_INSTALLED",
                                    "Install the Tesseract executable on this server.") from exc
            except Exception as exc:
                log.exception("Tesseract failed page=%s type=%s", page_number, type(exc).__name__)
                raise DocumentError("OCR_PROCESSING_FAILED",
                                    f"Tesseract failed for page {page_number}.") from exc
        return results

    def _decode_image(self, image_bytes: bytes) -> Image.Image:
        if not isinstance(image_bytes, bytes) or not image_bytes:
            raise ValueError("Page contains no image bytes.")
        with Image.open(BytesIO(image_bytes)) as source:
            with ImageOps.exif_transpose(source) as oriented:
                # No automatic upscaling. Large original images still require
                # decoding memory before thumbnailing.
                oriented.thumbnail((self.max_side, self.max_side), Image.Resampling.LANCZOS)
                if oriented.mode in {"RGBA", "LA"} or "transparency" in oriented.info:
                    with oriented.convert("RGBA") as rgba:
                        with Image.new("RGBA", rgba.size, "white") as background:
                            background.alpha_composite(rgba)
                            return background.convert("L")
                return oriented.convert("L")
