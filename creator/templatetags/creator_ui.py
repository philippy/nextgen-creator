from django import template

register = template.Library()


@register.filter
def hours(minutes):
    whole, remainder = divmod(int(minutes), 60)
    if not whole and remainder:
        return f"{remainder} min"
    return f"{whole}h {remainder:02d}" if remainder else f"{whole}h"
