"""Validate actual file contents before conversion or inference."""
from io import BytesIO
from pathlib import Path
import warnings
import pymupdf
from PIL import Image


class DocumentError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

    def as_dict(self):
        return {"error": {"code": self.code, "message": str(self)}}


class FileValidationService:
    EXTENSIONS = {".pdf": "application/pdf", ".jpg": "image/jpeg",
                  ".jpeg": "image/jpeg", ".png": "image/png"}

    def __init__(self, max_pages=3, max_bytes=10 * 1024 * 1024,
                 max_image_pixels=40_000_000):
        self.max_pages = max_pages
        self.max_bytes = max_bytes
        self.max_image_pixels = max_image_pixels

    def validate(self, data: bytes, filename: str, content_type=None):
        if not data:
            raise DocumentError("EMPTY_FILE", "The uploaded file is empty.")
        if len(data) > self.max_bytes:
            raise DocumentError("FILE_TOO_LARGE", "The file exceeds the size limit.")
        expected = self.EXTENSIONS.get(Path(filename).suffix.lower())
        if expected is None:
            raise DocumentError("UNSUPPORTED_FILE_TYPE", "Only PDF, JPG, JPEG and PNG are supported.")
        # Detect MIME from bytes; never trust a client-supplied MIME or extension.
        actual = ("application/pdf" if data.startswith(b"%PDF-") else
                  "image/png" if data.startswith(b"\x89PNG\r\n\x1a\n") else
                  "image/jpeg" if data.startswith(b"\xff\xd8\xff") else None)
        if actual != expected:
            raise DocumentError("FILE_TYPE_MISMATCH", "File contents do not match the extension.")
        if content_type:
            declared = content_type.split(";", 1)[0].strip().lower()
            if declared not in (actual, "application/octet-stream"):
                raise DocumentError("MIME_TYPE_MISMATCH", "Declared MIME does not match the file contents.")
        try:
            if actual == "application/pdf":
                with pymupdf.open(stream=data, filetype="pdf") as doc:
                    if doc.needs_pass:
                        raise DocumentError("ENCRYPTED_PDF", "Password-protected PDFs are not supported.")
                    if doc.is_repaired:
                        raise DocumentError("CORRUPTED_FILE", "The PDF required structural repair.")
                    count = doc.page_count
                    if count < 1:
                        raise DocumentError("EMPTY_DOCUMENT", "The PDF has no pages.")
                    if count > self.max_pages:
                        raise DocumentError("PAGE_LIMIT_EXCEEDED", f"Maximum {self.max_pages} pages are allowed.")
                    for page in doc:
                        if page.rect.is_empty or page.rect.is_infinite:
                            raise DocumentError("INVALID_PAGE", "The PDF contains an invalid page.")
                        page.get_text()
                        # Bounded render tests that each page is decodable.
                        scale = min(1, 1000 / max(page.rect.width, page.rect.height))
                        page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(BytesIO(data)) as img:
                        if img.format not in ("JPEG", "PNG"):
                            raise DocumentError("UNSUPPORTED_FILE_TYPE", "Unsupported image encoding.")
                        if img.width * img.height > self.max_image_pixels:
                            raise DocumentError("IMAGE_TOO_LARGE", "Image dimensions exceed the pixel limit.")
                        if getattr(img, "n_frames", 1) != 1:
                            raise DocumentError("ANIMATED_IMAGE", "Only single-frame images are supported.")
                        img.verify()
                    with Image.open(BytesIO(data)) as img:
                        img.load()
                count = 1
        except DocumentError:
            raise
        except Exception:
            raise DocumentError("CORRUPTED_FILE", "The document cannot be decoded safely.") from None
        return {"file_type": actual, "is_supported": True, "is_readable": True,
                "page_count": count, "status": "PASS"}
