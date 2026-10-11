"""Port of the document service's PDF template builders, exercised directly
against app.services.document_templates - no Node test file exists to port
1:1 from, so this is fresh coverage of the ported behavior."""

from app.services.document_templates import customer_invoice, format_money, purchase_order


class TestFormatMoneyIndianGrouping:
    def test_groups_seven_digits_in_indian_style(self):
        assert format_money("1234567", "INR") == "INR 12,34,567.00"

    def test_groups_a_nine_digit_value_with_repeated_pairing(self):
        assert format_money("123456789", "INR") == "INR 12,34,56,789.00"

    def test_three_or_fewer_digits_are_not_grouped(self):
        assert format_money("567", "INR") == "INR 567.00"
        assert format_money("42", "INR") == "INR 42.00"

    def test_rounds_half_up_to_two_decimal_places(self):
        assert format_money("1234567.505", "INR") == "INR 12,34,567.51"

    def test_negative_values_keep_the_sign_before_the_grouped_digits(self):
        assert format_money("-1234567", "INR") == "INR -12,34,567.00"

    def test_none_renders_an_em_dash(self):
        assert format_money(None, "INR") == "—"

    def test_invalid_value_renders_an_em_dash(self):
        assert format_money("not-a-number", "INR") == "—"

    def test_uses_the_given_currency_code(self):
        assert format_money("1000", "USD") == "USD 1,000.00"


def _invoice_line(**overrides):
    base = {"sku": "SKU-1", "description": "Widget", "hsnCode": "8507", "quantity": "2", "uom": "UNIT", "unitPrice": "100", "netAmount": "200", "taxRate": "18", "grossAmount": "236"}
    base.update(overrides)
    return base


class TestCustomerInvoiceGstSplit:
    """Rewritten for the reference-template redesign: IGST/SGST/CGST are now
    always-present percentage columns per line (matching the sample invoice
    layout), not conditionally-rendered rows - which of the three carries
    the line's real rate (vs "0%") is driven by intraState."""

    def test_header_always_shows_all_three_gst_columns(self):
        html = customer_invoice({"number": "INV-1", "total": "100", "subtotal": "100"})
        assert "<th>IGST</th>" in html
        assert "<th>SGST</th>" in html
        assert "<th>CGST</th>" in html

    def test_inter_state_line_puts_the_full_rate_under_igst_and_zeroes_sgst_cgst(self):
        html = customer_invoice({"number": "INV-2", "total": "236", "subtotal": "200", "intraState": False, "lines": [_invoice_line(taxRate="18")], "gst": {"igst": "36", "cgst": "0", "sgst": "0"}})
        assert '<td class="num">18%</td>' in html
        assert html.count('<td class="num">0%</td>') == 2  # SGST + CGST columns

    def test_intra_state_line_splits_the_rate_across_sgst_and_cgst_and_zeroes_igst(self):
        html = customer_invoice({"number": "INV-3", "total": "236", "subtotal": "200", "intraState": True, "lines": [_invoice_line(taxRate="18")], "gst": {"igst": "0", "cgst": "18", "sgst": "18"}})
        assert html.count('<td class="num">18%</td>') == 2  # SGST + CGST columns
        assert '<td class="num">0%</td>' in html  # IGST column

    def test_bank_details_only_render_when_the_seller_has_them(self):
        no_bank = customer_invoice({"number": "INV-4", "total": "100", "subtotal": "100", "seller": {"name": "Simple"}})
        assert "Bank details for payment" not in no_bank

        with_bank = customer_invoice({"number": "INV-5", "total": "100", "subtotal": "100", "seller": {"name": "Simple", "bankName": "HDFC Bank", "bankBranch": "MG Road", "bankAccountNumber": "000123456789", "bankIfsc": "HDFC0001234"}})
        assert "Bank details for payment" in with_bank
        assert "HDFC Bank" in with_bank
        assert "IDFC0001234" not in with_bank  # sanity: not hardcoded, reflects the passed seller
        assert "HDFC0001234" in with_bank


class TestPurchaseOrderRevisionLine:
    def test_revision_zero_hides_the_revision_line(self):
        html = purchase_order({"number": "PO-1", "revision": 0, "vendor": {"name": "Vendor Co"}, "lines": [], "total": "0"})
        assert "Revision" not in html

    def test_absent_revision_hides_the_revision_line(self):
        html = purchase_order({"number": "PO-1", "vendor": {"name": "Vendor Co"}, "lines": [], "total": "0"})
        assert "Revision" not in html

    def test_revision_above_zero_shows_the_revision_line(self):
        html = purchase_order({"number": "PO-1", "revision": 2, "vendor": {"name": "Vendor Co"}, "lines": [], "total": "0"})
        assert "Revision" in html
        assert "Revision: 2" in html
