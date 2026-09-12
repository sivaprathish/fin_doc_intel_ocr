import math
from collections.abc import Callable
from app.schemas.document import DocumentType
from app.schemas.extraction import StructuredExtraction
from app.schemas.validation import CheckStatus, FinancialValidation, ValidationCheck


class FinancialValidationService:
    def __init__(self, abs_tolerance=0.01, rel_tolerance=0.0001):
        self.abs_tolerance = abs_tolerance
        self.rel_tolerance = rel_tolerance

    @staticmethod
    def _number(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        value = float(value)
        return value if math.isfinite(value) else None

    def _field(self, extraction, key, period=None):
        field = extraction.document_fields.get(key)
        if not field:
            return None
        value = field.value
        if period is not None:
            return self._number(value.get(period)) if isinstance(value, dict) else None
        return self._number(value) if not isinstance(value, dict) else None

    def _periods(self, extraction, keys):
        periods = list(extraction.periods)
        for key in keys:
            field = extraction.document_fields.get(key)
            if field and isinstance(field.value, dict):
                for period in field.value:
                    if period not in periods:
                        periods.append(period)
        return periods or [None]

    def _check(self, name, formula, operands, calculated, reported, period=None, message=None):
        clean = {k: self._number(v) for k, v in operands.items()}
        calculated, reported = self._number(calculated), self._number(reported)
        if calculated is None or reported is None or any(v is None for v in clean.values()):
            return ValidationCheck(name=name, formula=formula, period=period, operands=clean,
                status=CheckStatus.NOT_APPLICABLE,
                message=message or "One or more required source values are missing or unreadable.")
        variance = calculated - reported
        passed = math.isclose(calculated, reported, rel_tol=self.rel_tolerance,
                              abs_tol=self.abs_tolerance)
        return ValidationCheck(name=name, formula=formula, period=period, operands=clean,
            calculated_value=calculated, reported_value=reported, variance=variance,
            status=CheckStatus.PASS if passed else CheckStatus.FAIL,
            message=None if passed else "Calculated and reported values do not reconcile within tolerance.")

    def validate(self, document_type: DocumentType, extraction: StructuredExtraction):
        handlers: dict[DocumentType, Callable] = {
            DocumentType.invoice: self._invoice,
            DocumentType.balance_sheet: self._balance_sheet,
            DocumentType.profit_and_loss: self._profit_and_loss,
            DocumentType.cash_flow_statement: self._cash_flow,
        }
        checks = handlers[document_type](extraction)
        if any(c.status == CheckStatus.FAIL for c in checks):
            overall = CheckStatus.FAIL
        elif any(c.status == CheckStatus.PASS for c in checks):
            overall = CheckStatus.PASS
        else:
            overall = CheckStatus.NOT_APPLICABLE
        issues = [f"{c.name}{' (' + c.period + ')' if c.period else ''}: {c.message}"
                  for c in checks if c.status == CheckStatus.FAIL]
        return FinancialValidation(checks=checks, overall_status=overall, issues=issues)

    def _invoice(self, extraction):
        checks = []
        amounts = []
        for index, item in enumerate(extraction.invoice_line_items, start=1):
            quantity = self._number(item.quantity.value)
            unit_price = self._number(item.unit_price.value)
            amount = self._number(item.amount.value)
            calculated = quantity * unit_price if quantity is not None and unit_price is not None else None
            checks.append(self._check(f"invoice_line_{index}_amount_check",
                "quantity * unit_price", {"quantity": quantity, "unit_price": unit_price},
                calculated, amount))
            amounts.append(amount)
        subtotal = self._field(extraction, "subtotal")
        checks.append(self._check("invoice_subtotal_check", "sum(line_item.amount)",
            {f"line_{i}_amount": amount for i, amount in enumerate(amounts, 1)},
            sum(amounts) if amounts and all(v is not None for v in amounts) else None, subtotal,
            "Line items or reported subtotal are unavailable."))

        tax = self._field(extraction, "tax_amount")
        discount = self._field(extraction, "discount")
        total = self._field(extraction, "total_amount")
        included_field = extraction.document_fields.get("tax_included_in_total")
        tax_included = included_field.value if included_field else None
        if tax_included is True:
            checks.append(self._check("invoice_total_check", "NOT_APPLICABLE: tax included in displayed total",
                {}, None, total, message="Tax is stated as included; no explicit tax-exclusive base was extracted."))
        else:
            # An absent discount is not assumed to be zero. The check remains N/A.
            calculated = subtotal + tax - discount if None not in (subtotal, tax, discount) else None
            checks.append(self._check("invoice_total_check", "subtotal + tax_amount - discount",
                {"subtotal": subtotal, "tax_amount": tax, "discount": discount}, calculated, total))

        cash = self._field(extraction, "cash_paid")
        change = self._field(extraction, "change")
        calculated = cash - total if cash is not None and total is not None else None
        checks.append(self._check("invoice_change_check", "cash_paid - total_amount",
            {"cash_paid": cash, "total_amount": total}, calculated, change))
        return checks

    def _component_sum(self, extraction, category, period):
        values = [self._number(row.values.get(period)) for row in extraction.financial_line_items
                  if row.category == category and period is not None]
        if not values or any(v is None for v in values):
            return None, values
        return sum(values), values

    def _balance_sheet(self, extraction):
        keys = ["total_assets", "total_capital_and_liabilities"]
        checks = []
        for period in self._periods(extraction, keys):
            assets = self._field(extraction, "total_assets", period)
            capital_liabilities = self._field(extraction, "total_capital_and_liabilities", period)
            checks.append(self._check("balance_sheet_equation_check",
                "total_assets = total_capital_and_liabilities",
                {"total_capital_and_liabilities": capital_liabilities}, capital_liabilities, assets, period))
            asset_sum, asset_values = self._component_sum(extraction, "asset_component", period)
            checks.append(self._check("asset_components_check", "sum(asset_components)",
                {f"asset_{i}": v for i, v in enumerate(asset_values, 1)}, asset_sum, assets, period,
                "No complete asset-component values were extracted for this period."))
            liability_sum, liability_values = self._component_sum(
                extraction, "capital_liability_component", period)
            checks.append(self._check("capital_liability_components_check",
                "sum(capital_liability_components)",
                {f"component_{i}": v for i, v in enumerate(liability_values, 1)},
                liability_sum, capital_liabilities, period,
                "No complete capital/liability-component values were extracted for this period."))
        return checks

    def _statement_formula(self, extraction, period, name, formula, operand_keys,
                           reported_key, operation):
        operands = {key: self._field(extraction, key, period) for key in operand_keys}
        calculated = operation(operands) if all(v is not None for v in operands.values()) else None
        return self._check(name, formula, operands, calculated,
                           self._field(extraction, reported_key, period), period)

    def _profit_and_loss(self, extraction):
        keys = ["interest_earned", "other_income", "total_income", "interest_expended",
                "operating_expenses", "provisions_and_contingencies", "total_expenditure",
                "consolidated_net_profit_before_minority_interest", "minority_interest",
                "consolidated_net_profit_attributable_to_group", "current_profit",
                "brought_forward_profit", "total_available_for_appropriation"]
        checks = []
        for period in self._periods(extraction, keys):
            checks.extend([
                self._statement_formula(extraction, period, "total_income_check",
                    "interest_earned + other_income", ["interest_earned", "other_income"],
                    "total_income", lambda x: x["interest_earned"] + x["other_income"]),
                self._statement_formula(extraction, period, "total_expenditure_check",
                    "interest_expended + operating_expenses + provisions_and_contingencies",
                    ["interest_expended", "operating_expenses", "provisions_and_contingencies"],
                    "total_expenditure", lambda x: sum(x.values())),
                self._statement_formula(extraction, period, "profit_before_minority_check",
                    "total_income - total_expenditure", ["total_income", "total_expenditure"],
                    "consolidated_net_profit_before_minority_interest",
                    lambda x: x["total_income"] - x["total_expenditure"]),
                self._statement_formula(extraction, period, "group_net_profit_check",
                    "consolidated_net_profit_before_minority_interest - minority_interest",
                    ["consolidated_net_profit_before_minority_interest", "minority_interest"],
                    "consolidated_net_profit_attributable_to_group",
                    lambda x: x["consolidated_net_profit_before_minority_interest"] - x["minority_interest"]),
                self._statement_formula(extraction, period, "appropriation_check",
                    "current_profit + brought_forward_profit", ["current_profit", "brought_forward_profit"],
                    "total_available_for_appropriation", lambda x: sum(x.values())),
            ])
        return checks

    def _cash_flow(self, extraction):
        keys = ["operating_cash_flow", "investing_cash_flow", "financing_cash_flow",
                "fx_translation_adjustment", "net_increase_in_cash", "opening_cash",
                "cash_acquired_on_amalgamation", "other_cash_adjustments", "closing_cash"]
        checks = []
        for period in self._periods(extraction, keys):
            checks.append(self._statement_formula(extraction, period, "net_cash_increase_check",
                "operating_cash_flow + investing_cash_flow + financing_cash_flow + fx_translation_adjustment",
                ["operating_cash_flow", "investing_cash_flow", "financing_cash_flow",
                 "fx_translation_adjustment"], "net_increase_in_cash", lambda x: sum(x.values())))
            checks.append(self._statement_formula(extraction, period, "closing_cash_check",
                "opening_cash + net_increase_in_cash + cash_acquired_on_amalgamation + other_cash_adjustments",
                ["opening_cash", "net_increase_in_cash", "cash_acquired_on_amalgamation",
                 "other_cash_adjustments"], "closing_cash", lambda x: sum(x.values())))
        return checks
