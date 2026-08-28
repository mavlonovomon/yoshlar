from builtins import abs as _builtin_abs

from django import template

register = template.Library()


@register.filter
def get_item(dict_obj, key):
    if not dict_obj:
        return 0
    item = dict_obj.get(key)
    if item is None:
        return 0
    return item.get("pct", 0)


@register.filter
def get_count(dict_obj, key):
    if not dict_obj:
        return 0
    item = dict_obj.get(key)
    if item is None:
        return 0
    return item.get("count", 0)


@register.filter
def module_meta(dict_obj, key):
    if not dict_obj:
        return "0/0"
    item = dict_obj.get(key)
    if item is None:
        return "0/0"
    return f"{item.get('count', 0)}/{item.get('total', 0)}"


@register.filter
def abs(value):
    try:
        return _builtin_abs(float(value))
    except (TypeError, ValueError):
        return value
