import json
import os
import secrets
import hmac
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, Response
from dotenv import load_dotenv
try:
    from .services.api_client import APIClient, APIError
except ImportError:
    from services.api_client import APIClient, APIError

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
TYPES = {'invoice': 'Invoice', 'balance_sheet': 'Balance sheet',
         'profit_and_loss': 'Profit and loss', 'cash_flow_statement': 'Cash Flow Statement'}


def create_app(client=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.getenv('FLASK_SECRET_KEY') or secrets.token_hex(32),
                      MAX_CONTENT_LENGTH=11 * 1024 * 1024,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.getenv('FLASK_COOKIE_SECURE') == 'true')
    api = client or APIClient(os.getenv('BACKEND_API_URL', 'http://127.0.0.1:8000/api/v1'),
                              int(os.getenv('BACKEND_TIMEOUT_SECONDS', '300')))

    @app.context_processor
    def context():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(32)
        return {'document_types': TYPES, 'csrf_token': session['csrf']}

    @app.template_filter('display')
    def display(value):
        if isinstance(value, dict) and 'value' in value:
            value = value['value']
        if value is None:
            return '—'
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/')
    def index():
        return render_template('index.html')

    @app.post('/upload')
    def upload():
        if not hmac.compare_digest(session.get('csrf', ''), request.form.get('csrf_token', '')) or not session.get('csrf'):
            return render_template('error.html', message='Form expired. Return to upload and try again.'), 400
        file = request.files.get('file')
        kind = request.form.get('document_type')
        if not file or not file.filename or kind not in TYPES:
            return render_template('error.html', message='Choose a document and valid document type.'), 400
        result = api.process(file, kind)
        return render_template('document_detail.html', doc=result)

    @app.get('/documents')
    def dashboard():
        page = max(1, request.args.get('page', 1, type=int))
        docs = api.list_documents((page - 1) * 25, 25)
        return render_template('dashboard.html', documents=docs, page=page)

    @app.get('/document')
    def detail():
        return render_template('document_detail.html', doc=api.get_document(request.args.get('name', '')))

    @app.get('/raw')
    def raw():
        doc = api.get_document(request.args.get('name', ''))
        content = json.dumps(doc, indent=2, ensure_ascii=False)
        if request.args.get('download') == '1':
            return Response(content, mimetype='application/json', headers={'Content-Disposition': 'attachment; filename=document-result.json'})
        return render_template('raw_json.html', content=content, name=doc.get('document_name', ''))

    @app.errorhandler(APIError)
    def api_error(error):
        return render_template('error.html', message=str(error)), error.status

    @app.errorhandler(413)
    def oversized(error):
        return render_template('error.html', message='File is too large. Upload a file under 10 MB.'), 413

    @app.errorhandler(404)
    def missing(error):
        return render_template('error.html', message='This page could not be found.'), 404

    return app


app = create_app()
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.getenv('FRONTEND_PORT', '5000')), debug=False)
