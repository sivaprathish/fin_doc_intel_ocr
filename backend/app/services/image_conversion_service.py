"""Return page-numbered PNG bytes and native PDF text, without disk writes."""
from io import BytesIO
import pymupdf
from PIL import Image, ImageOps
try:
    from .file_validation_service import FileValidationService, DocumentError
except ImportError:  # Direct execution from this folder.
    from file_validation_service import FileValidationService, DocumentError


class ImageConversionService:
    def __init__(self, validator=None, dpi=200, max_render_pixels=16_000_000):
        self.validator = validator or FileValidationService()
        if dpi <= 0 or max_render_pixels <= 0:
            raise ValueError("DPI and pixel budget must be positive.")
        self.dpi = dpi
        self.max_render_pixels = max_render_pixels

    def convert(self, data: bytes, filename: str, content_type=None):
        result = self.validator.validate(data, filename, content_type)
        pages = []
        try:
            if result["file_type"] == "application/pdf":
                with pymupdf.open(stream=data, filetype="pdf") as doc:
                    for number, page in enumerate(doc, start=1):
                        scale = self.dpi / 72
                        pixels = page.rect.width * page.rect.height * scale ** 2
                        if pixels > self.max_render_pixels:
                            raise DocumentError("RENDER_TOO_LARGE", "Page exceeds the rendering pixel budget.")
                        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale),
                                              colorspace=pymupdf.csRGB, alpha=False)
                        pages.append({"page_number": number,
                                      "native_text": page.get_text("text", sort=True),
                                      "image_bytes": pix.tobytes("png"), "image_mime": "image/png"})
            else:
                with Image.open(BytesIO(data)) as source:
                    normalized = ImageOps.exif_transpose(source)
                    rgba = normalized.convert("RGBA")
                    # Transparent pixels become white rather than black.
                    rgb = Image.new("RGB", rgba.size, "white")
                    rgb.paste(rgba, mask=rgba.getchannel("A"))
                    output = BytesIO()
                    rgb.save(output, format="PNG")
                    pages.append({"page_number": 1, "native_text": "",
                                  "image_bytes": output.getvalue(), "image_mime": "image/png"})
        except DocumentError:
            raise
        except Exception:
            raise DocumentError("CONVERSION_FAILED", "Could not prepare document pages.") from None
        return pages
