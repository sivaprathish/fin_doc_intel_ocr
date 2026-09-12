"""Local OCR using PP-OCRv6 Tiny detection and recognition models."""

from __future__ import annotations

import logging
import os
import threading
from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image, ImageOps
from paddleocr import PaddleOCR

from .file_validation_service import DocumentError

log = logging.getLogger(__name__)


class PaddleOCRService:
    """Extract text and reconstruct table-like rows locally."""

    def __init__(
        self,
        pipeline: Any | None = None,
        *,
        minimum_score: float | None = None,
    ) -> None:
        self.minimum_score = (
            minimum_score
            if minimum_score is not None
            else float(os.getenv("PADDLEOCR_MIN_SCORE", "0.20"))
        )
        self._predict_lock = threading.Lock()

        if pipeline is not None:
            self.pipeline = pipeline
            return

        cpu_threads = int(
            os.getenv(
                "PADDLEOCR_CPU_THREADS",
                str(min(os.cpu_count() or 2, 4)),
            )
        )
        log.info(
            "Loading PaddleOCR 2.6.2 models device=cpu threads=%s",
            cpu_threads,
        )
        self.pipeline = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        log.info("PP-OCRv6 Tiny models loaded")

    def transcribe(self, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not pages:
            raise DocumentError("NO_PAGES", "No document pages were provided for OCR.")

        results = []

        for page in pages:
            page_number = int(page["page_number"])

            try:
                image_array = self._decode_image(page["image_bytes"])

                with self._predict_lock:
                    ocr_result = self.pipeline.predict(
                        input=image_array,
                        use_textline_orientation=False
                    )

                entries = []

                if ocr_result and ocr_result[0]:
                    for line in ocr_result[0]:
                        box = line[0]
                        text = line[1][0]
                        score = float(line[1][1])

                        if score >= self.minimum_score:
                            entries.append({
                                "text": text,
                                "score": score,
                                "box": box,
                            })

                ocr_text = self._format_reading_order(entries)

                if not ocr_text.strip():
                    ocr_text = "[UNREADABLE]"

                results.append({
                    "page_number": page_number,
                    "ocr_text": ocr_text,
                    "native_text": page.get("native_text"),
                    "ocr_engine": "PaddleOCR-2.6",
                })

            except Exception as exc:
                log.exception(
                    "PaddleOCR failed page=%s type=%s",
                    page_number,
                    type(exc).__name__,
                )
                raise DocumentError(
                    "OCR_PROCESSING_FAILED",
                    f"PaddleOCR failed for page {page_number}.",
                ) from exc

        return results

    @staticmethod
    def _decode_image(image_bytes: bytes) -> np.ndarray:
        if not image_bytes:
            raise ValueError("Page contains no image bytes.")

        with Image.open(BytesIO(image_bytes)) as source:
            image = ImageOps.exif_transpose(source)

            if image.mode in {"RGBA", "LA"}:
                rgba = image.convert("RGBA")
                background = Image.new(
                    "RGBA",
                    rgba.size,
                    (255, 255, 255, 255),
                )
                background.alpha_composite(rgba)
                image = background.convert("RGB")
            else:
                image = image.convert("RGB")

            # Enlarge low-resolution invoice images.
            target_width = 1200

            if image.width < target_width:
                scale = min(target_width / image.width, 2.5)

                new_size = (
                    int(image.width * scale),
                    int(image.height * scale),
                )

                image = image.resize(
                    new_size,
                    Image.Resampling.LANCZOS,
                )

            return np.asarray(image)

    
