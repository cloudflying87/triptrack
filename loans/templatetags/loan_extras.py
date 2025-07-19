from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def sub(value, arg):
    """Subtract the arg from the value."""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """Divide the value by the arg."""
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def mul(value, arg):
    """Multiply the value by the arg."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def percentage_paid(loan):
    """Calculate the percentage of loan that has been paid."""
    try:
        if loan.principal_amount == 0:
            return 0
        paid_amount = loan.principal_amount - loan.current_balance
        return (paid_amount / loan.principal_amount) * 100
    except (AttributeError, ZeroDivisionError):
        return 0

@register.filter
def currency(value):
    """Format a number as currency."""
    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return "$0.00"

@register.filter
def sum_field(queryset, field_name):
    """Sum a specific field from a queryset or list of objects."""
    try:
        total = 0
        for obj in queryset:
            if hasattr(obj, field_name):
                field_value = getattr(obj, field_name)
                if field_value is not None:
                    total += float(field_value)
        return total
    except (ValueError, TypeError, AttributeError):
        return 0