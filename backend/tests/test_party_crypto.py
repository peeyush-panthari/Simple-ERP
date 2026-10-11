"""New coverage - the Node party service had no tests for crypto.ts."""

import pytest

from app.services.party_crypto import last_four, mask_account_number, matches_sealed, open_, seal

SECRET = "test-secret-at-least-16-bytes-long"


def test_round_trip():
    envelope = seal("123456789012", SECRET)
    assert open_(envelope, SECRET) == "123456789012"


def test_envelope_has_versioned_four_part_format():
    envelope = seal("123456789012", SECRET)
    parts = envelope.split(".")
    assert len(parts) == 4
    assert parts[0] == "v1"


def test_random_iv_per_call():
    a = seal("123456789012", SECRET)
    b = seal("123456789012", SECRET)
    assert a != b  # different IV each time
    assert open_(a, SECRET) == open_(b, SECRET)


def test_tampered_ciphertext_fails_closed():
    envelope = seal("123456789012", SECRET)
    version, iv, tag, ciphertext = envelope.split(".")
    tampered = ".".join([version, iv, tag, ciphertext[:-2] + ("AA" if ciphertext[-2:] != "AA" else "BB")])
    with pytest.raises(Exception):
        open_(tampered, SECRET)


def test_wrong_secret_fails_to_decrypt():
    envelope = seal("123456789012", SECRET)
    with pytest.raises(Exception):
        open_(envelope, "a-completely-different-secret-value")


def test_mask_and_last_four():
    assert mask_account_number("123456789012") == "****9012"
    assert last_four("1234 5678 9012") == "9012"


def test_matches_sealed():
    envelope = seal("123456789012", SECRET)
    assert matches_sealed("123456789012", envelope, SECRET) is True
    assert matches_sealed("999999999999", envelope, SECRET) is False
