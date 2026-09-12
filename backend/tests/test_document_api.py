from app.main import app


def test_mandatory_document_routes_are_registered():
    paths = app.openapi()["paths"]
    assert "post" in paths["/api/v1/documents/process"]
    assert "get" in paths["/api/v1/documents"]
    assert "get" in paths["/api/v1/documents/{document_name}"]
