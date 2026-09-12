from urllib.parse import quote
import requests


class APIError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


class APIClient:
    def __init__(self, base_url, timeout=300):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    def request(self, method, path, **kwargs):
        try:
            response = requests.request(method, self.base_url + path,
                                        timeout=(10, self.timeout), **kwargs)
        except requests.Timeout:
            raise APIError('Processing timed out. Check document history before uploading again; the backend may still finish.', 504) from None
        except requests.RequestException:
            raise APIError('Cannot connect to the backend. Check that FastAPI is running.', 503) from None
        try:
            data = response.json()
        except ValueError:
            raise APIError('The backend returned an unreadable response.') from None
        if not response.ok:
            error = data.get('error', data.get('detail', {})) if isinstance(data, dict) else {}
            message = error.get('message') if isinstance(error, dict) else None
            raise APIError(message or 'The backend could not complete this request.', response.status_code)
        return data

    def process(self, file, document_type):
        return self.request('POST', '/documents/process',
                            data={'document_type': document_type},
                            files={'file': (file.filename, file.stream, file.mimetype)})

    def list_documents(self, offset=0, limit=25):
        return self.request('GET', '/documents', params={'offset': offset, 'limit': limit})

    def get_document(self, name):
        return self.request('GET', '/documents/' + quote(name, safe=''))
