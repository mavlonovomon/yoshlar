import json
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.generic import ListView, TemplateView

from core.models import Yosh
from core.view_helpers import apply_sorting, build_querydict, normalize_sort_params

from .models import EkinYerEntry, EkinYerSnapshot

APOSTROPHE_TRANSLATION = str.maketrans(
    {
        "`": "'",
        "ʻ": "'",
        "ʼ": "'",
        "‘": "'",
        "’": "'",
        "ʹ": "'",
        "՚": "'",
    }
)


def _safe_text(value):
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        if "Р" in text or "вЂ" in text:
            decoded = text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore").strip()
            if decoded:
                text = decoded
    except Exception:
        pass
    return text


def _normalize_name(value):
    text = _safe_text(value).upper().translate(APOSTROPHE_TRANSLATION)
    text = (
        text.replace("O‘", "O'")
        .replace("G‘", "G'")
        .replace("Oʻ", "O'")
        .replace("Gʻ", "G'")
        .replace("Oʼ", "O'")
        .replace("Gʼ", "G'")
        .replace("O`", "O'")
        .replace("G`", "G'")
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_birth_date(value):
    text = str(value or "").strip()
    if not text:
        return None
    text = text[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _extract_first_name(normalized_name):
    parts = [part for part in re.split(r"\s+", normalized_name or "") if part]
    return parts[0] if parts else ""


def _is_youth_age(birth_date):
    if not birth_date:
        return False
    today = timezone.localdate()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return 14 <= age <= 30


def _candidate_to_meta(yosh):
    return {
        "id": yosh.id,
        "fullname": yosh.fullname,
        "birth_date": yosh.birth_date.isoformat() if yosh.birth_date else "",
        "mahalla": yosh.mahalla.name if yosh.mahalla_id else "",
        "jshshir": yosh.jshshir,
    }


def _build_yosh_index():
    by_name = defaultdict(list)
    by_name_birth = defaultdict(list)
    by_first_name_birth = defaultdict(list)
    qs = Yosh.objects.select_related("mahalla").all().only("id", "fullname", "birth_date", "jshshir", "mahalla__name")
    for yosh in qs:
        norm = _normalize_name(yosh.fullname)
        if not norm:
            continue
        by_name[norm].append(yosh)
        if yosh.birth_date:
            by_name_birth[(norm, yosh.birth_date)].append(yosh)
            first_name = _extract_first_name(norm)
            if first_name:
                by_first_name_birth[(first_name, yosh.birth_date)].append(yosh)
    return by_name, by_name_birth, by_first_name_birth


def import_ekin_yer_snapshot(*, source_path: Path, uploaded_by=None):
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    by_name, by_name_birth, by_first_name_birth = _build_yosh_index()
    meta = {
        "groups_total": len(raw),
        "rows_total": 0,
        "matched": 0,
        "ambiguous": 0,
        "not_found": 0,
        "youth_age_count": 0,
        "non_youth_age_count": 0,
    }

    with transaction.atomic():
        snapshot = EkinYerSnapshot.objects.create(
            source_file_name=source_path.name,
            uploaded_by=uploaded_by,
            raw_meta={},
        )
        entries = []
        for group in raw:
            group_neighborhood_id = group.get("neighborhood_id")
            for item in group.get("data", []):
                winner = item.get("winner") or {}
                land_address = item.get("address") or {}
                winner_address = winner.get("address") or {}
                winner_name = _safe_text(winner.get("fio"))
                winner_name_normalized = _normalize_name(winner_name)
                winner_birth_date = _parse_birth_date(winner.get("birth_date"))
                first_name = _extract_first_name(winner_name_normalized)
                candidates = []
                exact_candidates = []
                first_name_birth_candidates = []
                if winner_name_normalized:
                    candidates = by_name.get(winner_name_normalized, [])
                    if winner_birth_date:
                        exact_candidates = by_name_birth.get((winner_name_normalized, winner_birth_date), [])
                if first_name and winner_birth_date:
                    first_name_birth_candidates = by_first_name_birth.get((first_name, winner_birth_date), [])

                linked_yosh = None
                possible_matches = []
                match_note = ""
                if len(exact_candidates) == 1:
                    linked_yosh = exact_candidates[0]
                    match_status = EkinYerEntry.MATCHED
                    match_note = "F.I.Sh + tug'ilgan sana bo'yicha topildi."
                elif len(exact_candidates) > 1:
                    match_status = EkinYerEntry.AMBIGUOUS
                    possible_matches = [_candidate_to_meta(candidate) for candidate in exact_candidates[:10]]
                    match_note = "Bir xil F.I.Sh va tug'ilgan sana bilan bir nechta yosh topildi."
                elif len(candidates) == 1:
                    linked_yosh = candidates[0]
                    match_status = EkinYerEntry.MATCHED
                    match_note = "Faqat F.I.Sh bo'yicha topildi."
                elif len(candidates) > 1:
                    match_status = EkinYerEntry.AMBIGUOUS
                    possible_matches = [_candidate_to_meta(candidate) for candidate in candidates[:10]]
                    match_note = "Bir xil F.I.Sh bilan bir nechta yosh topildi."
                elif first_name_birth_candidates:
                    match_status = EkinYerEntry.AMBIGUOUS
                    possible_matches = [_candidate_to_meta(candidate) for candidate in first_name_birth_candidates[:10]]
                    match_note = "Ism + tug'ilgan sana bo'yicha ehtimoliy mosliklar topildi."
                else:
                    match_status = EkinYerEntry.NOT_FOUND
                    match_note = "Yoshlar ro'yxatidan topilmadi."

                is_youth_age = _is_youth_age(winner_birth_date)
                meta["rows_total"] += 1
                if match_status == EkinYerEntry.MATCHED:
                    meta["matched"] += 1
                elif match_status == EkinYerEntry.AMBIGUOUS:
                    meta["ambiguous"] += 1
                else:
                    meta["not_found"] += 1
                if is_youth_age:
                    meta["youth_age_count"] += 1
                else:
                    meta["non_youth_age_count"] += 1

                entries.append(
                    EkinYerEntry(
                        snapshot=snapshot,
                        source_entry_id=str(item.get("_id") or ""),
                        winner_external_id=str(winner.get("_id") or ""),
                        winner_name=winner_name,
                        winner_name_normalized=winner_name_normalized,
                        winner_birth_date=winner_birth_date,
                        winner_phone=_safe_text(winner.get("phone")),
                        winner_neighborhood_name=_safe_text(winner_address.get("neighborhood")),
                        land_neighborhood_id=land_address.get("neighborhood_id") or group_neighborhood_id,
                        land_neighborhood_name=_safe_text(land_address.get("neighborhood")),
                        area=Decimal(str(item.get("area"))) if item.get("area") is not None else None,
                        area_specialization=_safe_text(item.get("area_specialization")),
                        specialty_category=_safe_text(item.get("specialty_category")),
                        specialty_type=_safe_text(item.get("specialty_type")),
                        contour_numbers=item.get("contour_number") or [],
                        land_type=item.get("land_type") or [],
                        geometry=item.get("geometry") or {},
                        location=item.get("location") or {},
                        raw_json=item,
                        linked_yosh=linked_yosh,
                        match_status=match_status,
                        match_note=match_note,
                        possible_matches=possible_matches,
                        is_youth_age=is_youth_age,
                    )
                )

        EkinYerEntry.objects.bulk_create(entries, batch_size=500)
        snapshot.raw_meta = meta
        snapshot.save(update_fields=["raw_meta"])
        return snapshot


class EkinYerAccessMixin:
    def get_base_queryset(self):
        qs = EkinYerEntry.objects.select_related("linked_yosh", "linked_yosh__mahalla", "snapshot")
        user = self.request.user
        if not getattr(user, "is_site_admin", False) and getattr(user, "mahalla", None):
            qs = qs.filter(Q(linked_yosh__mahalla=user.mahalla) | Q(land_neighborhood_name=user.mahalla.name))
        return qs


def _build_map_payload(entries, mode="all"):
    include_geometry = mode in {"all", "polygons"}
    include_location = mode in {"all", "markers"}
    items = []
    for entry in entries:
        popup_lines = [
            f"<div class='fw-semibold'>{entry.winner_name}</div>",
            f"<div class='small text-muted'>{entry.winner_birth_date.strftime('%d.%m.%Y') if entry.winner_birth_date else '-'}</div>",
            f"<div class='small'><strong>Ekin:</strong> {entry.specialty_type or '-'}</div>",
            f"<div class='small'><strong>Kategoriya:</strong> {entry.specialty_category or '-'}</div>",
            f"<div class='small'><strong>Maydon:</strong> {entry.area or '-'}</div>",
            f"<div class='small'><strong>Yer mahallasi:</strong> {entry.land_neighborhood_name or '-'}</div>",
            f"<div class='small'><strong>Holat:</strong> {entry.get_match_status_display()}</div>",
        ]
        if entry.linked_yosh_id and entry.linked_yosh:
            popup_lines.append(
                f"<div class='small'><strong>Tizimdagi yosh:</strong> {entry.linked_yosh.fullname} ({entry.linked_yosh.mahalla.name})</div>"
            )

        items.append(
            {
                "id": entry.id,
                "name": entry.winner_name,
                "status": entry.match_status,
                "status_label": entry.get_match_status_display(),
                "mahalla": entry.land_neighborhood_name or "",
                "specialty": entry.specialty_type or "",
                "category": entry.specialty_category or "",
                "area": float(entry.area) if entry.area is not None else None,
                "location": (entry.location or {}) if include_location else {},
                "geometry": (entry.geometry or {}) if include_geometry else {},
                "popup_html": "".join(popup_lines),
            }
        )
    return items


def _resolve_map_snapshot(request):
    snapshot_id = (request.GET.get("snapshot") or "").strip()
    if snapshot_id.isdigit():
        snapshot = EkinYerSnapshot.objects.filter(pk=snapshot_id).first()
        if snapshot:
            return snapshot
    return EkinYerSnapshot.objects.order_by("-created_at").first()


def _filtered_map_queryset(request):
    snapshot = _resolve_map_snapshot(request)
    if not snapshot:
        return snapshot, EkinYerEntry.objects.none()

    qs = EkinYerEntry.objects.select_related("linked_yosh", "linked_yosh__mahalla", "snapshot").filter(snapshot=snapshot)
    user = request.user
    if not getattr(user, "is_site_admin", False) and getattr(user, "mahalla", None):
        qs = qs.filter(Q(linked_yosh__mahalla=user.mahalla) | Q(land_neighborhood_name=user.mahalla.name))

    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(match_status=status)
    mahalla = (request.GET.get("mahalla") or "").strip()
    if mahalla:
        qs = qs.filter(land_neighborhood_name=mahalla)
    specialty = (request.GET.get("specialty") or "").strip()
    if specialty:
        qs = qs.filter(specialty_type=specialty)
    return snapshot, qs


class EkinYerDashboardView(LoginRequiredMixin, EkinYerAccessMixin, TemplateView):
    template_name = "ekin_yerlari/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot = EkinYerSnapshot.objects.order_by("-created_at").first()
        context["snapshot"] = snapshot
        if not snapshot:
            context["land_rows"] = []
            context["system_rows"] = []
            context["summary"] = {}
            return context

        qs = self.get_base_queryset().filter(snapshot=snapshot)
        context["summary"] = qs.aggregate(
            total_rows=Count("id"),
            matched_count=Count("id", filter=Q(match_status=EkinYerEntry.MATCHED)),
            ambiguous_count=Count("id", filter=Q(match_status=EkinYerEntry.AMBIGUOUS)),
            not_found_count=Count("id", filter=Q(match_status=EkinYerEntry.NOT_FOUND)),
            total_area=Sum("area"),
            youth_age_count=Count("id", filter=Q(is_youth_age=True)),
        )
        context["land_rows"] = list(
            qs.values("land_neighborhood_name")
            .annotate(
                total=Count("id"),
                matched=Count("id", filter=Q(match_status=EkinYerEntry.MATCHED)),
                ambiguous=Count("id", filter=Q(match_status=EkinYerEntry.AMBIGUOUS)),
                not_found=Count("id", filter=Q(match_status=EkinYerEntry.NOT_FOUND)),
                total_area=Sum("area"),
            )
            .order_by("-total", "land_neighborhood_name")
        )
        context["system_rows"] = list(
            qs.filter(linked_yosh__mahalla__isnull=False)
            .values("linked_yosh__mahalla__name")
            .annotate(total=Count("id"), total_area=Sum("area"))
            .order_by("-total", "linked_yosh__mahalla__name")
        )
        return context


class EkinYerListView(LoginRequiredMixin, EkinYerAccessMixin, ListView):
    template_name = "ekin_yerlari/list.html"
    context_object_name = "entries"
    paginate_by = 25

    def get_queryset(self):
        snapshot_id = self.request.GET.get("snapshot")
        snapshot = (
            EkinYerSnapshot.objects.filter(pk=snapshot_id).first()
            if snapshot_id and snapshot_id.isdigit()
            else EkinYerSnapshot.objects.order_by("-created_at").first()
        )
        self.snapshot = snapshot
        if not snapshot:
            return EkinYerEntry.objects.none()

        qs = self.get_base_queryset().filter(snapshot=snapshot)
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(winner_name__icontains=q)
                | Q(winner_phone__icontains=q)
                | Q(linked_yosh__fullname__icontains=q)
                | Q(land_neighborhood_name__icontains=q)
                | Q(specialty_type__icontains=q)
            )

        status = (self.request.GET.get("status") or "").strip()
        if status:
            qs = qs.filter(match_status=status)

        unresolved = (self.request.GET.get("unresolved") or "").strip()
        if unresolved == "1":
            qs = qs.exclude(match_status=EkinYerEntry.MATCHED)

        mahalla = (self.request.GET.get("mahalla") or "").strip()
        if mahalla:
            qs = qs.filter(land_neighborhood_name=mahalla)

        allowed_sort_fields = {"winner_name", "winner_birth_date", "land_neighborhood_name", "area", "match_status"}
        sort_field, sort_direction = normalize_sort_params(self.request, allowed_sort_fields, "winner_name")
        self.sort_field = sort_field
        self.sort_direction = sort_direction
        return apply_sorting(
            qs,
            sort_field,
            sort_direction,
            {
                "winner_name": "winner_name",
                "winner_birth_date": "winner_birth_date",
                "land_neighborhood_name": "land_neighborhood_name",
                "area": "area",
                "match_status": "match_status",
            },
            "winner_name",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["snapshot"] = getattr(self, "snapshot", None)
        context["snapshots"] = EkinYerSnapshot.objects.order_by("-created_at")[:10]
        context["status_choices"] = EkinYerEntry.MATCH_STATUS_CHOICES
        context["selected_status"] = (self.request.GET.get("status") or "").strip()
        context["selected_mahalla"] = (self.request.GET.get("mahalla") or "").strip()
        context["unresolved_only"] = (self.request.GET.get("unresolved") or "").strip() == "1"
        context["sort_field"] = getattr(self, "sort_field", "winner_name")
        context["sort_direction"] = getattr(self, "sort_direction", "asc")
        if self.snapshot:
            context["land_mahallas"] = (
                EkinYerEntry.objects.filter(snapshot=self.snapshot)
                .exclude(land_neighborhood_name="")
                .values_list("land_neighborhood_name", flat=True)
                .distinct()
                .order_by("land_neighborhood_name")
            )
        else:
            context["land_mahallas"] = []
        return context


class EkinYerMapView(LoginRequiredMixin, EkinYerAccessMixin, TemplateView):
    template_name = "ekin_yerlari/map.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot, qs = _filtered_map_queryset(self.request)
        context["snapshot"] = snapshot
        context["snapshots"] = EkinYerSnapshot.objects.order_by("-created_at")[:10]
        context["status_choices"] = EkinYerEntry.MATCH_STATUS_CHOICES
        context["selected_status"] = (self.request.GET.get("status") or "").strip()
        context["selected_mahalla"] = (self.request.GET.get("mahalla") or "").strip()
        context["selected_specialty"] = (self.request.GET.get("specialty") or "").strip()
        context["show_mode"] = (self.request.GET.get("mode") or "all").strip()
        context["map_data_url"] = reverse("ekin_yerlari:map_data")

        if not snapshot:
            context["land_mahallas"] = []
            context["specialties"] = []
            return context

        context["land_mahallas"] = (
            EkinYerEntry.objects.filter(snapshot=snapshot)
            .exclude(land_neighborhood_name="")
            .values_list("land_neighborhood_name", flat=True)
            .distinct()
            .order_by("land_neighborhood_name")
        )
        context["specialties"] = (
            EkinYerEntry.objects.filter(snapshot=snapshot)
            .exclude(specialty_type="")
            .values_list("specialty_type", flat=True)
            .distinct()
            .order_by("specialty_type")
        )
        return context


@login_required
def ekin_yer_map_data(request):
    snapshot, qs = _filtered_map_queryset(request)
    if not snapshot:
        return JsonResponse({"success": True, "items": [], "count": 0})

    mode = (request.GET.get("mode") or "all").strip()
    entries = list(qs)
    items = _build_map_payload(entries, mode=mode)
    return JsonResponse({"success": True, "items": items, "count": len(items)})


class EkinYerResolveView(LoginRequiredMixin, EkinYerAccessMixin, TemplateView):
    template_name = "ekin_yerlari/resolve.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entry = get_object_or_404(self.get_base_queryset(), pk=self.kwargs["pk"])
        search = (self.request.GET.get("q") or "").strip()
        if not search:
            search = entry.winner_name

        yosh_qs = Yosh.objects.select_related("mahalla").all()
        tokens = [token for token in re.split(r"\s+", search) if token]
        for token in tokens[:5]:
            yosh_qs = yosh_qs.filter(fullname__icontains=token)

        if entry.winner_birth_date:
            exact_birth = list(yosh_qs.filter(birth_date=entry.winner_birth_date)[:20])
            if exact_birth:
                results = exact_birth
            else:
                results = list(yosh_qs[:20])
        else:
            results = list(yosh_qs[:20])

        context["entry"] = entry
        context["search_query"] = search
        context["results"] = results
        context["back_url"] = reverse("ekin_yerlari:list")
        return context


@login_required
def ekin_yer_assign_yosh(request, pk):
    if request.method != "POST":
        return redirect("ekin_yerlari:resolve", pk=pk)

    entry = get_object_or_404(EkinYerEntry.objects.select_related("snapshot"), pk=pk)
    if not getattr(request.user, "is_site_admin", False):
        messages.error(request, "Qo'lda moslash faqat administrator uchun ruxsat etilgan.")
        return redirect("ekin_yerlari:resolve", pk=pk)

    yosh_id = (request.POST.get("yosh_id") or "").strip()
    if not yosh_id:
        entry.linked_yosh = None
        entry.match_status = EkinYerEntry.NOT_FOUND
        entry.match_note = "Qo'lda bog'lash bekor qilindi."
        entry.save(update_fields=["linked_yosh", "match_status", "match_note"])
        messages.success(request, "Bog'lanish bekor qilindi.")
        return redirect("ekin_yerlari:resolve", pk=pk)

    yosh = get_object_or_404(Yosh.objects.select_related("mahalla"), pk=yosh_id)
    entry.linked_yosh = yosh
    entry.match_status = EkinYerEntry.MATCHED
    entry.match_note = "Qo'lda biriktirildi."
    entry.save(update_fields=["linked_yosh", "match_status", "match_note"])
    messages.success(request, f"{entry.winner_name} yozuvi {yosh.fullname} ga biriktirildi.")
    return redirect("ekin_yerlari:resolve", pk=pk)


@login_required
def ekin_yer_import_from_file(request):
    if request.method != "POST":
        return redirect("ekin_yerlari:index")
    if not getattr(request.user, "is_site_admin", False):
        messages.error(request, "Import faqat administrator uchun ruxsat etilgan.")
        return redirect("ekin_yerlari:index")

    source_path = Path(settings.BASE_DIR) / "fermer.json"
    if not source_path.exists():
        messages.error(request, f"{source_path.name} fayli topilmadi.")
        return redirect("ekin_yerlari:index")

    snapshot = import_ekin_yer_snapshot(source_path=source_path, uploaded_by=request.user)
    messages.success(
        request,
        f"Import yakunlandi: {snapshot.raw_meta.get('rows_total', 0)} ta yozuv, "
        f"{snapshot.raw_meta.get('matched', 0)} ta topildi, "
        f"{snapshot.raw_meta.get('ambiguous', 0)} ta noaniq, "
        f"{snapshot.raw_meta.get('not_found', 0)} ta topilmadi.",
    )
    return HttpResponseRedirect(reverse("ekin_yerlari:list") + "?" + build_querydict(request, snapshot=snapshot.id))
