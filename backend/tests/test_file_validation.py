import unittest
from io import BytesIO
from types import SimpleNamespace as NS
import pymupdf
from PIL import Image
from app.services.file_validation_service import FileValidationService, DocumentError
from app.services.image_conversion_service import ImageConversionService
from app.services.paddle_ocr_service import PaddleOCRService


def pdf(count=1, scanned=False):
    with pymupdf.open() as doc:
        for _ in range(count):
            page = doc.new_page()
            if scanned:
                page.insert_image(page.rect, stream=picture())
            else:
                page.insert_text((72, 72), "Invoice INV-001 Total USD 100.00")
        return doc.tobytes()


def picture(fmt="PNG"):
    output = BytesIO()
    Image.new("RGB", (100, 80), "white").save(output, format=fmt)
    return output.getvalue()


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.validator = FileValidationService()

    def check_error(self, code, fn):
        with self.assertRaises(DocumentError) as cm:
            fn()
        self.assertEqual(code, cm.exception.code)

    def test_valid_pdf(self):
        self.assertEqual(self.validator.validate(pdf(2), "a.pdf"), {
            "file_type": "application/pdf", "is_supported": True,
            "is_readable": True, "page_count": 2, "status": "PASS"})

    def test_images(self):
        for fmt, ext in [("PNG", "png"), ("JPEG", "jpg"), ("JPEG", "jpeg")]:
            self.assertEqual(self.validator.validate(picture(fmt), f"a.{ext}")["status"], "PASS")

    def test_empty(self):
        self.check_error("EMPTY_FILE", lambda: self.validator.validate(b"", "a.pdf"))

    def test_extension(self):
        self.check_error("UNSUPPORTED_FILE_TYPE", lambda: self.validator.validate(b"text", "a.txt"))

    def test_fake_extension(self):
        self.check_error("FILE_TYPE_MISMATCH", lambda: self.validator.validate(picture(), "a.pdf"))

    def test_mime(self):
        self.check_error("MIME_TYPE_MISMATCH", lambda: self.validator.validate(pdf(), "a.pdf", "image/png"))

    def test_corrupt_pdf(self):
        self.check_error("CORRUPTED_FILE", lambda: self.validator.validate(b"%PDF-1.7\nbroken", "a.pdf"))

    def test_corrupt_image(self):
        self.check_error("CORRUPTED_FILE", lambda: self.validator.validate(picture()[:40], "a.png"))

    def test_page_limit(self):
        self.check_error("PAGE_LIMIT_EXCEEDED", lambda: self.validator.validate(pdf(4), "a.pdf"))
        self.assertEqual(self.validator.validate(pdf(3), "a.pdf")["page_count"], 3)

    def test_size(self):
        self.check_error("FILE_TOO_LARGE", lambda: FileValidationService(max_bytes=2).validate(pdf(), "a.pdf"))

    def test_native_conversion(self):
        pages = ImageConversionService().convert(pdf(2), "a.pdf")
        self.assertEqual([p["page_number"] for p in pages], [1, 2])
        self.assertIn("INV-001", pages[0]["native_text"])
        with Image.open(BytesIO(pages[0]["image_bytes"])) as img:
            self.assertEqual(img.mode, "RGB")
            self.assertGreater(img.width, 1000)

    def test_scanned_pdf(self):
        pages = ImageConversionService().convert(pdf(scanned=True), "scan.pdf")
        self.assertEqual(pages[0]["native_text"], "")
        self.assertTrue(pages[0]["image_bytes"].startswith(b"\x89PNG"))

    def test_transparency(self):
        output = BytesIO()
        Image.new("RGBA", (20, 10), (0, 0, 0, 0)).save(output, format="PNG")
        page = ImageConversionService().convert(output.getvalue(), "a.png")[0]
        with Image.open(BytesIO(page["image_bytes"])) as img:
            self.assertEqual(img.getpixel((0, 0)), (255, 255, 255))

    def test_orientation(self):
        img = Image.new("RGB", (20, 10), "white")
        exif = img.getexif()
        exif[274] = 6
        output = BytesIO()
        img.save(output, format="JPEG", exif=exif)
        page = ImageConversionService().convert(output.getvalue(), "a.jpg")[0]
        with Image.open(BytesIO(page["image_bytes"])) as converted:
            self.assertEqual(converted.size, (10, 20))

    def test_revalidate_conversion(self):
        self.check_error("EMPTY_FILE", lambda: ImageConversionService().convert(b"", "a.pdf"))

    def test_paddle_ocr_transcription(self):
        prediction = NS(
            json={
                "rec_texts": ["Invoice INV-001", "Total", "100.00"],
                "rec_scores": [0.99, 0.98, 0.97],
                "rec_boxes": [
                    [10, 10, 120, 30],
                    [10, 40, 50, 60],
                    [60, 40, 120, 60],
                ],
            },
        )
        pipeline = NS(predict=lambda input: [prediction])
        pages = PaddleOCRService(pipeline=pipeline).transcribe([
            {"page_number": 1, "image_bytes": picture(), "native_text": ""}])
        self.assertIn("INV-001", pages[0]["ocr_text"])
        self.assertEqual(pages[0]["ocr_engine"], "PP-OCRv6-tiny")

    def test_paddle_ocr_empty_result(self):
        pipeline = NS(predict=lambda input: [NS(json={"rec_texts": [], "rec_scores": []})])
        pages = PaddleOCRService(pipeline=pipeline).transcribe([
            {"page_number": 1, "image_bytes": picture()}])
        self.assertEqual(pages[0]["ocr_text"], "[UNREADABLE]")


if __name__ == "__main__":
    unittest.main()
