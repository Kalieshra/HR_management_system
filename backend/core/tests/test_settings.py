"""Guards on configuration that the rest of the project assumes."""

from django.conf import settings


def test_arabic_is_the_default_language():
    assert settings.LANGUAGE_CODE == "ar"
    assert [code for code, _ in settings.LANGUAGES] == ["ar", "en"]


def test_timezone_is_cairo():
    assert settings.TIME_ZONE == "Africa/Cairo"
    assert settings.USE_TZ is True


def test_reference_workbook_is_present():
    """The payroll engine is specified by this file; it must ship with the repo."""
    assert settings.REFERENCE_WORKBOOK.exists(), settings.REFERENCE_WORKBOOK
