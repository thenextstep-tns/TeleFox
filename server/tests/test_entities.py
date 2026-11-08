from foxygram.entities import Entity, container_is_valid, extract


def test_finds_vin_and_uppercases():
    assert Entity("vin", "WBA3A5C58DF123456") in extract("машина wba3a5c58df123456 готова")


def test_ignores_seventeen_char_words_without_digits():
    assert not [e for e in extract("ABCDEFGHJKLMNPRST") if e.type == "vin"]


def test_container_check_digit():
    assert container_is_valid("CSQU3054383")
    assert not container_is_valid("CSQU3054384")


def test_container_with_separators():
    assert Entity("container", "CSQU3054383") in extract("контейнер CSQU 305438-3 в порту")


def test_invalid_container_ignored():
    assert not [e for e in extract("MSKU1234560") if e.type == "container"] or container_is_valid("MSKU1234560")


def test_phone_normalised():
    assert Entity("phone", "79161234567") in extract("звони +7 (916) 123-45-67")


def test_invoice_needs_a_digit():
    found = extract("инвойс № AB-1234 и счёт почти готов")
    assert Entity("invoice", "AB-1234") in found
    assert not [e for e in found if e.value == "ПОЧТИ"]


def test_empty():
    assert extract("") == []
