import math
import re


def parse_financial_number(value):
    """Parse explicit numeric text; parentheses/brackets represent negatives."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
        return result if math.isfinite(result) else None
    text = str(value).strip()
    if not text or text.casefold() in {"null", "n/a", "na", "-", "—", "unreadable"}:
        return None
    negative = ((text.startswith("(") and text.endswith(")")) or
                (text.startswith("[") and text.endswith("]")))
    text = text.strip("()[]").replace(",", "")
    text = re.sub(r"^[^0-9+\-.]*|[^0-9.]*$", "", text)
    try:
        number = float(text)
    except ValueError:
        return None
    return -abs(number) if negative else number


NUMERIC_DOCUMENT_FIELDS = {
    "subtotal", "tax_amount", "discount", "total_amount", "cash_paid", "change",
    "total_assets", "total_capital_and_liabilities", "total_liabilities", "total_equity",
    "interest_earned", "other_income", "total_income", "interest_expended",
    "operating_expenses", "provisions_and_contingencies", "total_expenditure",
    "consolidated_net_profit_before_minority_interest", "minority_interest",
    "consolidated_net_profit_attributable_to_group", "current_profit",
    "brought_forward_profit", "total_available_for_appropriation",
    "operating_cash_flow", "investing_cash_flow", "financing_cash_flow",
    "fx_translation_adjustment", "net_increase_in_cash", "opening_cash",
    "cash_acquired_on_amalgamation", "other_cash_adjustments", "closing_cash",
}


def normalize_extraction_numbers(payload: dict) -> dict:
    """Normalize explicit financial strings in a model payload, in place."""
    for key, field in payload.get("document_fields", {}).items():
        if key not in NUMERIC_DOCUMENT_FIELDS or not isinstance(field, dict):
            continue
        value = field.get("value")
        if isinstance(value, dict):
            field["value"] = {period: parse_financial_number(item)
                              for period, item in value.items()}
        else:
            field["value"] = parse_financial_number(value)
    for item in payload.get("invoice_line_items", []):
        for key in ("quantity", "unit_price", "amount"):
            field = item.get(key)
            if isinstance(field, dict):
                field["value"] = parse_financial_number(field.get("value"))
    for item in payload.get("financial_line_items", []):
        if isinstance(item.get("values"), dict):
            item["values"] = {period: parse_financial_number(value)
                              for period, value in item["values"].items()}
    return payload
