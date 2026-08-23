from django.utils.html import format_html
from django import template

from core.view_helpers import build_querydict, sort_indicator_html

register = template.Library()

PAGE_INFO = {
    '/': ('Dashboard', 'dashboard'),
    '/dashboard/': ('Dashboard', 'dashboard'),
    '/kpi/': ('KPI', 'monitoring'),
    '/hisobot/': ('Hisobot', 'description'),
    '/yoshlar/': ('Yoshlar ro\'yxati', 'group'),
    '/yoshlar/maktab-oquvchilar/': ('Maktab o\'quvchilari', 'school'),
    '/yoshlar/maktab-aniqlanmagan/': ('Aniqlanmaganlar', 'person_search'),
    '/users/': ('Foydalanuvchilar', 'manage_accounts'),
    '/ishsiz_yoshlar/': ('Ishsiz Yoshlar', 'work'),
    '/ishsiz_yoshlar/svod/': ('Ishsizlar Svod', 'summarize'),
    '/ishsiz_yoshlar/list/': ('Ishsizlar Ro\'yxati', 'list'),
    '/otaliq/': ('Otaliqdagi Yoshlar', 'verified_user'),
    '/otaliq/svod/': ('Otaliq Svod', 'summarize'),
    '/otaliq/list/': ('Otaliq Ro\'yxati', 'list'),
    '/migratsiya/': ('Migratsiyadagi Yoshlar', 'flight'),
    '/migratsiya/list/': ('Migratsiya Ro\'yxati', 'list'),
    '/beshtashabbus/': ('Besh tashabbus', 'emoji_events'),
    '/beshtashabbus/list/': ('Besh tashabbus Ro\'yxati', 'list'),
    '/beshtashabbus/applications/': ('Arizalar', 'description'),
    '/reyd/': ('Reyd tadbirlari', 'shield'),
    '/reyd/list/': ('Reyd tadbirlari', 'shield'),
    '/profilaktika/': ('Ijtimoiy profilaktika', 'shield'),
    '/kredit-yonaltirish/': ('Kredit yo\'naltirish', 'paid'),
    '/kredit-yonaltirish/list/': ('Kredit Ro\'yxati', 'list'),
    '/kredit-yonaltirish/svod/': ('Kredit Svod', 'summarize'),
    '/ekin-yerlari/': ('Ekin yerlari', 'park'),
    '/ekin-yerlari/list/': ('Ekin Ro\'yxati', 'list'),
    '/ekin-yerlari/map/': ('Ekin Xarita', 'map'),
    '/intizom-jazo/': ('Intizomiy jazolar', 'gavel'),
    '/intizom-jazo/list/': ('Jazo Ro\'yxati', 'list'),
    '/mega-loyihalar/': ('Mega loyihalar', 'rocket_launch'),
    '/mega-loyihalar/mutolaa/': ('Mutolaa', 'menu_book'),
    '/mega-loyihalar/ustoz-ai/': ('Ustoz AI', 'psychology'),
    '/mega-loyihalar/uzchess/': ('UzChess', 'casino'),
    '/mega-loyihalar/qizlar-akademiyasi/': ('Qizlar akademiyasi', 'school'),
    '/sorovnoma/': ('So\'rovnomalar', 'assignment'),
    '/sorovnoma/list/': ('So\'rovnomalar Ro\'yxati', 'list'),
    '/bilim-sinovi/': ('Bilim Sinovi', 'quiz'),
    '/bilim-sinovi/manage/': ('Bilim Sinovi Boshqaruvi', 'admin_panel_settings'),
    '/bilim-sinovi/manage/packages/': ('Savol paketlari', 'inventory_2'),
    '/bilim-sinovi/manage/results/': ('Natijalar', 'assessment'),
    '/eco-energiya/': ('Eco Energiya', 'eco'),
    '/eco-energiya/list/': ('Eco Energiya Ro\'yxati', 'solar_power'),
    '/yoqlama/': ('Yo\'qlama', 'fact_check'),
    '/yoqlama/list/': ('Yo\'qlama Ro\'yxati', 'list'),
}

# Sort by key length (longest first) for correct prefix matching
_PAGE_INFO_SORTED = sorted(PAGE_INFO.items(), key=lambda x: len(x[0]), reverse=True)


class PageInfoNode(template.Node):
    def __init__(self, title_var, icon_var):
        self.title_var = title_var
        self.icon_var = icon_var

    def render(self, context):
        request = context.get('request')
        title, icon = 'Yoshlar Admin', 'dashboard'
        if request:
            path = request.path
            for prefix, (t, i) in _PAGE_INFO_SORTED:
                if path == prefix or path.startswith(prefix):
                    title, icon = t, i
                    break
        context[self.title_var] = title
        context[self.icon_var] = icon
        return ''


@register.tag
def page_info(parser, token):
    bits = token.split_contents()
    if len(bits) == 4 and bits[1] == 'as':
        return PageInfoNode(bits[2], bits[3])
    raise template.TemplateSyntaxError(
        "'page_info' syntax: {% page_info as title_var icon_var %}"
    )

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
