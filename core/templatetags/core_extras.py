from django import template

register = template.Library()

@register.filter
def subtract(value, arg):
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key, "")
    except Exception:
        return ""
