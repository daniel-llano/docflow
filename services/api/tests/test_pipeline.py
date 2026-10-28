import pytest

from app.documents import UnreadableDocument, read_text
from app.pipeline import extract, language_guess, mask_pii
from app.settings import Settings


def test_masks_email_phone_valid_cards_and_ibans():
    text = "Mail a@b.co, call +44 20 7946 0958, card 4111-1111-1111-1111, IBAN GB82 WEST 1234 5698 7654 32."
    masked, counts = mask_pii(text)
    assert counts == {"email": 1, "phone": 1, "card": 1, "iban": 1}
    assert "[EMAIL]" in masked and "[CARD]" in masked and "[IBAN]" in masked


def test_ignores_numbers_that_fail_luhn():
    _, counts = mask_pii("Order 1234 5678 9012 3456 shipped.")
    assert counts["card"] == 0


@pytest.mark.parametrize(
    "text, lang",
    [
        ("The invoice for the services will be paid by the end of the month.", "en"),
        ("La factura de los servicios se paga para el final del mes con la tarjeta.", "es"),
        ("Die Rechnung ist nicht bezahlt und wir warten auf eine Antwort.", "de"),
        ("12345 67890", "unknown"),
    ],
)
def test_language_guess(text, lang):
    assert language_guess(text) == lang


def test_extract_fields():
    result = extract("Payment of €300.00 is due on Dec 5, 2026. The payment covers hosting. Thanks.")
    assert result["amounts"] == ["€300.00"]
    assert result["dates"] == ["Dec 5, 2026"]
    assert "payment" in result["keywords"]
    assert result["summary"].startswith("Payment of €300.00")


def test_extract_refuses_empty_text():
    with pytest.raises(ValueError):
        extract("   ")


def test_read_text_handles_text_and_rejects_others():
    assert read_text("a.txt", "héllo".encode()) == "héllo"
    with pytest.raises(UnreadableDocument):
        read_text("a.docx", b"PK")
    with pytest.raises(UnreadableDocument):
        read_text("a.pdf", b"not a pdf")


def test_production_requires_real_secrets():
    with pytest.raises(ValueError):
        Settings(_env_file=None, app_env="production")
    Settings(_env_file=None, app_env="production", jwt_secret="x" * 40, internal_key="y" * 30)


def test_dates_are_not_mistaken_for_phone_numbers():
    _, counts = mask_pii("Due 2026-11-15, signed 11/15/2026.")
    assert counts["phone"] == 0
