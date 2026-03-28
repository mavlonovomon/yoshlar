from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe


def is_management_user(user):
    return bool(
        user
        and (user.is_superuser or user.is_staff or getattr(user, "role", None) in {"SUPER_ADMIN", "RAHBAR"})
    )


def is_active_school_class(value):
    text = str(value or "").strip()
    if not text:
        return False
    normalized = text.replace(" ", "").casefold()
    return normalized not in {"-", "—", "–", "none", "null", "nan"}


def normalize_sort_params(request, allowed_fields, default_field, default_direction="asc"):
    sort_field = (request.GET.get("sort") or default_field).strip()
    sort_direction = (request.GET.get("dir") or default_direction).strip().lower()

    if sort_field not in allowed_fields:
        sort_field = default_field
    if sort_direction not in {"asc", "desc"}:
        sort_direction = default_direction

    return sort_field, sort_direction


def apply_sorting(queryset, sort_field, sort_direction, field_map, default_field):
    mapped = field_map.get(sort_field, field_map[default_field])
    if isinstance(mapped, str):
        mapped_fields = (mapped,)
    else:
        mapped_fields = tuple(mapped)

    prefix = "-" if sort_direction == "desc" else ""
    order_by = [f"{prefix}{field}" for field in mapped_fields]
    return queryset.order_by(*order_by)


def sort_indicator_html(is_active, sort_direction):
    if not is_active:
        return mark_safe('<i class="bi bi-arrow-down-up ms-1 text-muted"></i>')
    icon = "bi-sort-down-alt" if sort_direction == "desc" else "bi-sort-up-alt"
    return format_html('<i class="bi {} ms-1 text-primary"></i>', icon)


def build_querydict(request, **changes):
    query = request.GET.copy()
    for key, value in changes.items():
        if value is None or value == "":
            query.pop(key, None)
        else:
            query[key] = str(value)
    return query.urlencode()
