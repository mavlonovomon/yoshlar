from django.utils.html import format_html
from django import template

from core.view_helpers import build_querydict, sort_indicator_html

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


@register.simple_tag(takes_context=True)
def query_replace(context, **kwargs):
    request = context["request"]
    return build_querydict(request, **kwargs)


@register.simple_tag(takes_context=True)
def sort_link(context, field, label, current_sort=None, current_dir=None, title=None):
    request = context["request"]
    current_sort = current_sort or request.GET.get("sort") or ""
    current_dir = (current_dir or request.GET.get("dir") or "asc").strip().lower()
    is_active = current_sort == field
    next_dir = "desc" if is_active and current_dir == "asc" else "asc"
    url = build_querydict(request, sort=field, dir=next_dir, page=None)
    indicator = sort_indicator_html(is_active, current_dir)
    title_text = title or f"{label} bo'yicha saralash"
    return format_html(
        '<a href="?{}" class="sort-link{}" title="{}">{}</a>',
        url,
        " is-active" if is_active else "",
        title_text,
        format_html("{}{}", label, indicator),
    )
