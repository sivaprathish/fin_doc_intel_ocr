from pathlib import PurePath


def safe_document_name(filename: str) -> str:
    name = PurePath(filename or "").name
    if not name or name in {".", ".."}:
        raise ValueError("A valid document filename is required.")
    return name

