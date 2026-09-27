"""Serializer fields with project-wide money rules."""

from rest_framework import serializers

from payroll.services.engine import quantize_display


class MoneyField(serializers.DecimalField):
    """Money as a *string* in JSON — never a float, never a rounding surprise."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_digits", 20)
        kwargs.setdefault("decimal_places", 2)
        kwargs.setdefault("coerce_to_string", True)
        super().__init__(**kwargs)

    def to_representation(self, value):
        if value is None:
            return None
        return str(quantize_display(value))


class QuantityField(serializers.DecimalField):
    """Days and hours: two decimals, also sent as a string."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_digits", 10)
        kwargs.setdefault("decimal_places", 2)
        kwargs.setdefault("coerce_to_string", True)
        super().__init__(**kwargs)
