import json


def parse_strict_json_object(text: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("JSON response is empty.")
    cleaned = text.strip()
    decoder = json.JSONDecoder(
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value))
    )
    value, end = decoder.raw_decode(cleaned)
    if cleaned[end:].strip() or not isinstance(value, dict):
        raise ValueError("Expected exactly one JSON object.")
    return value

