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
            "Loading PP-OCRv6 Small models device=cpu threads=%s",
            cpu_threads,
        )
        self.pipeline = PaddleOCR(
            text_detection_model_name="PP-OCRv6_small_det",
            text_recognition_model_name="PP-OCRv6_small_rec",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device="cpu",
            engine="paddle_static",
            engine_config={
                "device_type": "cpu",
                "cpu_threads": cpu_threads,
                "run_mode": "paddle",
                "enable_new_ir": False,
            },
        )
        log.info("PP-OCRv6 Tiny models loaded")

    def transcribe(self, pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not pages:
            raise DocumentError("NO_PAGES", "No document pages were provided for OCR.")

        results: list[dict[str, Any]] = []
        for page in pages:
            page_number = int(page["page_number"])
            log.info("PaddleOCR processing started page=%s", page_number)
            try:
                image_array = self._decode_image(page["image_bytes"])
                with self._predict_lock:
                    predictions = list(self.pipeline.predict(input=image_array))

                entries: list[dict[str, Any]] = []
                for prediction in predictions:
                    payload = self._prediction_to_dict(prediction)
                    block = self._find_ocr_block(payload)
                    if block is not None:
                        entries.extend(self._entries_from_block(block))

                ocr_text = self._format_reading_order(entries)
                if not ocr_text.strip():
                    log.warning("PaddleOCR returned no usable text page=%s", page_number)
                    ocr_text = "[UNREADABLE]"

                results.append({
                    "page_number": page_number,
                    "ocr_text": ocr_text,
                    "native_text": page.get("native_text"),
                    "ocr_engine": "PP-OCRv6-tiny",
                })
                log.info(
                    "PaddleOCR processing completed page=%s characters=%s entries=%s",
                    page_number,
                    len(ocr_text),
                    len(entries),
                )
            except DocumentError:
                raise
            except Exception as exc:
                log.exception("PaddleOCR failed page=%s type=%s", page_number, type(exc).__name__)
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

    @staticmethod
    def _prediction_to_dict(prediction: Any) -> dict[str, Any]:
        if isinstance(prediction, dict):
            return prediction
        payload = getattr(prediction, "json", None)
        if callable(payload):
            payload = payload()
        if isinstance(payload, dict):
            return payload
        result = getattr(prediction, "res", None)
        if isinstance(result, dict):
            return {"res": result}
        raise ValueError("Unsupported PaddleOCR prediction result format.")

    @classmethod
    def _find_ocr_block(cls, node: Any) -> dict[str, Any] | None:
        if isinstance(node, dict):
            if isinstance(node.get("rec_texts"), (list, tuple)):
                return node
            for value in node.values():
                result = cls._find_ocr_block(value)
                if result is not None:
                    return result
        elif isinstance(node, (list, tuple)):
            for value in node:
                result = cls._find_ocr_block(value)
                if result is not None:
                    return result
        return None

    def _entries_from_block(self, block: dict[str, Any]) -> list[dict[str, Any]]:
        texts = self._to_list(block.get("rec_texts"))
        scores = self._to_list(block.get("rec_scores"))
        raw_boxes = block.get("rec_boxes")
        if raw_boxes is None:
            raw_boxes = block.get("dt_polys")
        boxes = self._to_list(raw_boxes)
        entries: list[dict[str, Any]] = []
        for index, value in enumerate(texts):
            text = str(value or "").strip()
            if not text:
                continue
            score = self._get_score(scores, index)
            if score is not None and score < self.minimum_score:
                continue
            box = self._normalize_box(boxes[index]) if index < len(boxes) else None
            entries.append({"text": text, "score": score, "box": box})
        return entries

    @staticmethod
    def _to_list(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]

    @staticmethod
    def _get_score(scores: list[Any], index: int) -> float | None:
        if index >= len(scores):
            return None
        try:
            return float(scores[index])
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_box(value: Any) -> tuple[float, float, float, float] | None:
        if value is None:
            return None
        try:
            array = np.asarray(value, dtype=float)
        except (TypeError, ValueError):
            return None
        if array.size == 4 and array.ndim == 1:
            x1, y1, x2, y2 = array.tolist()
            return float(x1), float(y1), float(x2), float(y2)
        if array.ndim == 2 and array.shape[1] >= 2:
            return (
                float(array[:, 0].min()),
                float(array[:, 1].min()),
                float(array[:, 0].max()),
                float(array[:, 1].max()),
            )
        return None

    @classmethod
    def _format_reading_order(cls, entries: list[dict[str, Any]]) -> str:
        if not entries:
            return ""
        positioned = [entry for entry in entries if entry["box"] is not None]
        if len(positioned) != len(entries):
            return "\n".join(entry["text"] for entry in entries)

        heights = [max(entry["box"][3] - entry["box"][1], 1.0) for entry in positioned]
        row_tolerance = max(float(np.median(heights)) * 0.60, 4.0)
        positioned.sort(key=lambda entry: ((entry["box"][1] + entry["box"][3]) / 2, entry["box"][0]))

        rows: list[list[dict[str, Any]]] = []
        row_centers: list[float] = []
        for entry in positioned:
            center_y = (entry["box"][1] + entry["box"][3]) / 2
            best_index = None
            best_distance = float("inf")
            for index, center in enumerate(row_centers):
                distance = abs(center_y - center)
                if distance <= row_tolerance and distance < best_distance:
                    best_index, best_distance = index, distance
            if best_index is None:
                rows.append([entry])
                row_centers.append(center_y)
            else:
                rows[best_index].append(entry)
                centers = [(item["box"][1] + item["box"][3]) / 2 for item in rows[best_index]]
                row_centers[best_index] = sum(centers) / len(centers)

        ordered_rows = sorted(zip(row_centers, rows), key=lambda item: item[0])
        formatted_rows: list[str] = []
        for _center, row in ordered_rows:
            row.sort(key=lambda entry: entry["box"][0])
            formatted_rows.append(" | ".join(entry["text"] for entry in row))
        return "\n".join(formatted_rows)
