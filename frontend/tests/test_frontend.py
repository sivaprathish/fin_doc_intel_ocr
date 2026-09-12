import unittest
from unittest.mock import Mock
from frontend.app import create_app
from frontend.services.api_client import APIError


class FrontendTests(unittest.TestCase):
    def setUp(self):
        self.api = Mock()
        self.app = create_app(self.api)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_upload_page(self):
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_csrf_rejected(self):
        self.assertEqual(self.client.post('/upload').status_code, 400)
        self.api.process.assert_not_called()

    def test_history_escapes_names(self):
        self.api.list_documents.return_value = [{'document_name': '<script>alert(1)</script>', 'document_type': 'invoice', 'processing_status': 'PASS', 'created_at': '2026-09-12'}]
        response = self.client.get('/documents')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'<script>alert(1)</script>', response.data)

    def test_detail(self):
        self.api.get_document.return_value = {'document_name': 'invoice.pdf', 'document_type': 'invoice', 'extracted_data': {'document_fields': {'total': {'value': 10}}, 'invoice_line_items': [{'description': {'value': 'Service'}}]}, 'validation': {'checks': [{'name': 'total', 'status': 'PASS', 'variance': 0}]}}
        self.assertEqual(self.client.get('/document?name=invoice.pdf').status_code, 200)

    def test_download(self):
        self.api.get_document.return_value = {'document_name': 'a.pdf'}
        response = self.client.get('/raw?name=a.pdf&download=1')
        self.assertEqual(response.mimetype, 'application/json')
        self.assertIn('attachment', response.headers['Content-Disposition'])

    def test_backend_error(self):
        self.api.list_documents.side_effect = APIError('Backend unavailable', 503)
        self.assertEqual(self.client.get('/documents').status_code, 503)

    def test_valid_upload(self):
        import io
        self.client.get('/')
        with self.client.session_transaction() as state:
            token = state['csrf']
        self.api.process.return_value = {'document_name': 'a.pdf'}
        response = self.client.post('/upload', data={'csrf_token': token, 'document_type': 'invoice', 'file': (io.BytesIO(b'%PDF'), 'a.pdf')})
        self.assertEqual(response.status_code, 200)
        self.api.process.assert_called_once()
