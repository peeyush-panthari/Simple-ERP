"""Amount-in-words for generated financial documents (PO/invoice) - Indian
numbering (crore/lakh), matching the standard "Rupees X Only" convention
used on Indian purchase orders and tax invoices."""

from __future__ import annotations

from app.core.money import round_dp, to_decimal

_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two_digits(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return f"{_TENS[tens]} {_ONES[ones]}".strip()


def _three_digits(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    if hundreds and rest:
        return f"{_ONES[hundreds]} Hundred {_two_digits(rest)}"
    if hundreds:
        return f"{_ONES[hundreds]} Hundred"
    return _two_digits(rest)


def _integer_words(n: int) -> str:
    """Indian grouping: crore (1e7), lakh (1e5), thousand (1e3), then the
    last 3 digits as a single hundreds group."""
    if n == 0:
        return "Zero"
    parts: list[str] = []
    crore, n = divmod(n, 10_000_000)
    if crore:
        parts.append(f"{_integer_words(crore)} Crore")
    lakh, n = divmod(n, 100_000)
    if lakh:
        parts.append(f"{_two_digits(lakh)} Lakh")
    thousand, n = divmod(n, 1_000)
    if thousand:
        parts.append(f"{_two_digits(thousand)} Thousand")
    if n:
        parts.append(_three_digits(n))
    return " ".join(parts)


def amount_in_words_inr(amount) -> str:
    """E.g. 10752.00 -> "Ten Thousand Seven Hundred Fifty Two Rupees Only",
    10752.50 -> "... Rupees and Fifty Paise Only"."""
    value = round_dp(to_decimal(amount or 0), 2)
    rupees = int(value)
    paise = int((value - rupees) * 100)
    words = f"{_integer_words(rupees)} Rupees"
    if paise:
        words += f" and {_two_digits(paise)} Paise"
    return f"{words} Only"
