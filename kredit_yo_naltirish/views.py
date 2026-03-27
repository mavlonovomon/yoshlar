from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import HttpResponseBadRequest, JsonResponse, HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from io import BytesIO
import pandas as pd

from .models import CreditCandidate, CreditMonitoringEntry, CreditMonitoringFile
from core.models import Yosh, Mahalla


def _can_manage_pipeline(user):
    return bool(
        user
        and user.is_authenticated
        and (getattr(user, "is_site_admin", False) or user.has_perm("kredit_yo_naltirish.manage_pipeline"))
    )


def _can_add_monitoring(user, candidate: CreditCandidate):
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_site_admin", False):
        return True
    if getattr(user, "role", None) == "YETAKCHI" and candidate.created_by_id == user.id:
        return True
    return False


def _can_add_candidate(user):
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_site_admin", False):
        return True
    return getattr(user, "role", None) == "YETAKCHI"


@login_required
def index(request):
    tab = (request.GET.get("tab") or "nomination").strip().lower()
    candidates_qs = (
        CreditCandidate.objects.select_related("yosh", "yosh__mahalla", "created_by")
        .prefetch_related("monitoring_entries", "monitoring_entries__files")
        .order_by("-updated_at")
    )
    if tab == "process":
        candidates_qs = candidates_qs.filter(stage="IN_PROCESS")
    elif tab == "credit":
        candidates_qs = candidates_qs.filter(stage__in=["APPROVED", "REJECTED"])
    elif tab == "monitoring":
        candidates_qs = candidates_qs.filter(stage__in=["APPROVED", "MONITORING"])
    else:
        tab = "nomination"
        candidates_qs = candidates_qs.filter(stage="NOMINATION")

    counts = CreditCandidate.objects.values("stage").annotate(total=models.Count("id"))
    count_map = {c["stage"]: c["total"] for c in counts}

    candidates = []
    for candidate in candidates_qs:
        candidate.can_add_monitoring = _can_add_monitoring(request.user, candidate)
        candidates.append(candidate)

    context = {
        "candidates": candidates,
        "tab": tab,
        "can_manage_pipeline": _can_manage_pipeline(request.user),
        "can_add_candidate": _can_add_candidate(request.user),
        "counts": count_map,
        "decision_basis_choices": CreditCandidate.DECISION_BASIS_CHOICES,
        "collateral_type_choices": CreditCandidate.COLLATERAL_TYPE_CHOICES,
        "business_type_choices": CreditCandidate.BUSINESS_TYPE_CHOICES,
    }
    return render(request, "kredit_yo_naltirish/index.html", context)


@login_required
def svod(request):
    qs = CreditCandidate.objects.select_related("yosh", "yosh__mahalla")
    summary = qs.aggregate(
        total=models.Count("id"),
        nomination=models.Count("id", filter=models.Q(stage="NOMINATION")),
        in_process=models.Count("id", filter=models.Q(stage="IN_PROCESS")),
        approved=models.Count("id", filter=models.Q(stage="APPROVED")),
        rejected=models.Count("id", filter=models.Q(stage="REJECTED")),
        monitoring=models.Count("id", filter=models.Q(stage="MONITORING")),
        requested_sum=models.Sum("requested_amount"),
        approved_sum=models.Sum("credit_amount", filter=models.Q(stage__in=["APPROVED", "MONITORING"])),
    )

    by_mahalla_raw = qs.values("yosh__mahalla__id", "yosh__mahalla__name").annotate(
        total=models.Count("id"),
        nomination=models.Count("id", filter=models.Q(stage="NOMINATION")),
        in_process=models.Count("id", filter=models.Q(stage="IN_PROCESS")),
        approved=models.Count("id", filter=models.Q(stage__in=["APPROVED", "MONITORING"])),
        rejected=models.Count("id", filter=models.Q(stage="REJECTED")),
        monitoring=models.Count("id", filter=models.Q(stage="MONITORING")),
        requested_sum=models.Sum("requested_amount"),
        approved_sum=models.Sum("credit_amount", filter=models.Q(stage__in=["APPROVED", "MONITORING"])),
    )
    raw_map = {row["yosh__mahalla__id"]: row for row in by_mahalla_raw}
    by_mahalla = []
    for m in Mahalla.objects.all().order_by("name"):
        row = raw_map.get(m.id, {})
        by_mahalla.append(
            {
                "mahalla_name": m.name,
                "total": row.get("total", 0) or 0,
                "nomination": row.get("nomination", 0) or 0,
                "in_process": row.get("in_process", 0) or 0,
                "approved": row.get("approved", 0) or 0,
                "rejected": row.get("rejected", 0) or 0,
                "monitoring": row.get("monitoring", 0) or 0,
                "requested_sum": row.get("requested_sum", 0) or 0,
                "approved_sum": row.get("approved_sum", 0) or 0,
            }
        )

    basis_counts = {row["decision_basis"]: row["total"] for row in qs.values("decision_basis").annotate(total=models.Count("id"))}
    collateral_counts = {row["collateral_type"]: row["total"] for row in qs.values("collateral_type").annotate(total=models.Count("id"))}

    basis_summary = [
        {"label": label, "count": basis_counts.get(value, 0)}
        for value, label in CreditCandidate.DECISION_BASIS_CHOICES
    ]
    collateral_summary = [
        {"label": label, "count": collateral_counts.get(value, 0)}
        for value, label in CreditCandidate.COLLATERAL_TYPE_CHOICES
    ]

    context = {
        "summary": summary,
        "by_mahalla": by_mahalla,
        "basis_summary": basis_summary,
        "collateral_summary": collateral_summary,
    }
    return render(request, "kredit_yo_naltirish/svod.html", context)


@login_required
def svod_export(request):
    qs = CreditCandidate.objects.select_related("yosh", "yosh__mahalla")
    by_mahalla_raw = qs.values("yosh__mahalla__id", "yosh__mahalla__name").annotate(
        total=models.Count("id"),
        nomination=models.Count("id", filter=models.Q(stage="NOMINATION")),
        in_process=models.Count("id", filter=models.Q(stage="IN_PROCESS")),
        approved=models.Count("id", filter=models.Q(stage__in=["APPROVED", "MONITORING"])),
        rejected=models.Count("id", filter=models.Q(stage="REJECTED")),
        monitoring=models.Count("id", filter=models.Q(stage="MONITORING")),
        requested_sum=models.Sum("requested_amount"),
        approved_sum=models.Sum("credit_amount", filter=models.Q(stage__in=["APPROVED", "MONITORING"])),
    )
    raw_map = {row["yosh__mahalla__id"]: row for row in by_mahalla_raw}
    rows = []
    for m in Mahalla.objects.all().order_by("name"):
        row = raw_map.get(m.id, {})
        rows.append(
            {
                "Mahalla": m.name,
                "Jami": row.get("total", 0) or 0,
                "Nomzod": row.get("nomination", 0) or 0,
                "Jarayonda": row.get("in_process", 0) or 0,
                "Ajratildi": row.get("approved", 0) or 0,
                "Rad etildi": row.get("rejected", 0) or 0,
                "Monitoring": row.get("monitoring", 0) or 0,
                "So'ralgan (mln)": row.get("requested_sum", 0) or 0,
                "Ajratilgan (mln)": row.get("approved_sum", 0) or 0,
            }
        )

    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Mahalla Svod")
    output.seek(0)
    filename = f"kredit_svod_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def add_candidate(request):
    if request.method != "POST":
        return HttpResponseBadRequest("Method noto'g'ri.")

    if not _can_add_candidate(request.user):
        return HttpResponseBadRequest("Ruxsat yo'q.")

    yosh_id = request.POST.get("yosh_id")
    if not yosh_id:
        return HttpResponseBadRequest("Yosh tanlanmadi.")

    yosh = get_object_or_404(Yosh, pk=yosh_id)
    existing = CreditCandidate.objects.filter(yosh=yosh).first()
    if existing:
        return HttpResponseBadRequest("Bu yosh allaqachon nomzod sifatida kiritilgan.")

    decision_basis = (request.POST.get("decision_basis") or "").strip()
    business_type = (request.POST.get("business_type") or "").strip()
    project_goal = (request.POST.get("project_goal") or "").strip()
    collateral_type = (request.POST.get("collateral_type") or "").strip()
    requested_amount_raw = (request.POST.get("requested_amount") or "").strip()
    requested_amount = None
    if requested_amount_raw:
        try:
            requested_amount = float(requested_amount_raw)
        except ValueError:
            return HttpResponseBadRequest("So'ralgan summa noto'g'ri.")

    CreditCandidate.objects.create(
        yosh=yosh,
        created_by=request.user,
        decision_basis=decision_basis,
        business_type=business_type,
        project_goal=project_goal,
        collateral_type=collateral_type,
        requested_amount=requested_amount,
    )
    return redirect("kredit_yo_naltirish:index")


@login_required
def search_yosh(request):
    if not _can_add_candidate(request.user):
        return JsonResponse({"success": False, "error": "Ruxsat yo'q."}, status=403)

    q = (request.GET.get("q") or "").strip()
    if not q:
        return JsonResponse({"success": True, "items": []})

    qs = Yosh.objects.select_related("mahalla").filter(
        models.Q(fullname__icontains=q)
        | models.Q(jshshir__icontains=q)
        | models.Q(passport_number__icontains=q)
        | models.Q(phone_number__icontains=q)
    )[:20]

    items = [
        {
            "id": y.id,
            "fullname": y.fullname,
            "jshshir": y.jshshir,
            "passport_number": y.passport_number or "",
            "phone_number": y.phone_number or "",
            "mahalla": y.mahalla.name if y.mahalla else "",
        }
        for y in qs
    ]
    return JsonResponse({"success": True, "items": items})


@login_required
def move_to_process(request, pk):
    if request.method != "POST":
        return HttpResponseBadRequest("Method noto'g'ri.")
    if not _can_manage_pipeline(request.user):
        return HttpResponseBadRequest("Ruxsat yo'q.")

    candidate = get_object_or_404(CreditCandidate, pk=pk)
    if candidate.stage != "NOMINATION":
        return HttpResponseBadRequest("Faqat nomzodlar jarayonga kiritiladi.")

    candidate.stage = "IN_PROCESS"
    candidate.processed_by = request.user
    candidate.save(update_fields=["stage", "processed_by", "updated_at"])
    return HttpResponseRedirect(f"{reverse('kredit_yo_naltirish:index')}?tab=process")


@login_required
def approve_candidate(request, pk):
    if request.method != "POST":
        return HttpResponseBadRequest("Method noto'g'ri.")
    if not _can_manage_pipeline(request.user):
        return HttpResponseBadRequest("Ruxsat yo'q.")

    candidate = get_object_or_404(CreditCandidate, pk=pk)
    if candidate.stage != "IN_PROCESS":
        return HttpResponseBadRequest("Faqat jarayondagi nomzod tasdiqlanadi.")

    amount_raw = (request.POST.get("credit_amount") or "").strip()
    if not amount_raw:
        return HttpResponseBadRequest("Kredit summasi majburiy.")

    try:
        amount = float(amount_raw)
    except ValueError:
        return HttpResponseBadRequest("Kredit summasi noto'g'ri.")

    candidate.credit_amount = amount
    candidate.reject_reason = ""
    candidate.stage = "APPROVED"
    candidate.processed_by = request.user
    candidate.decided_at = timezone.now()
    candidate.save(update_fields=["credit_amount", "reject_reason", "stage", "processed_by", "decided_at", "updated_at"])
    return HttpResponseRedirect(f"{reverse('kredit_yo_naltirish:index')}?tab=credit")


@login_required
def reject_candidate(request, pk):
    if request.method != "POST":
        return HttpResponseBadRequest("Method noto'g'ri.")
    if not _can_manage_pipeline(request.user):
        return HttpResponseBadRequest("Ruxsat yo'q.")

    candidate = get_object_or_404(CreditCandidate, pk=pk)
    if candidate.stage != "IN_PROCESS":
        return HttpResponseBadRequest("Faqat jarayondagi nomzod rad etiladi.")

    reason = (request.POST.get("reject_reason") or "").strip()
    if not reason:
        return HttpResponseBadRequest("Rad etish sababi majburiy.")

    candidate.reject_reason = reason
    candidate.credit_amount = None
    candidate.stage = "REJECTED"
    candidate.processed_by = request.user
    candidate.decided_at = timezone.now()
    candidate.save(update_fields=["reject_reason", "credit_amount", "stage", "processed_by", "decided_at", "updated_at"])
    return HttpResponseRedirect(f"{reverse('kredit_yo_naltirish:index')}?tab=credit")


@login_required
def enable_monitoring(request, pk):
    if request.method != "POST":
        return HttpResponseBadRequest("Method noto'g'ri.")

    if not _can_manage_pipeline(request.user):
        return HttpResponseBadRequest("Ruxsat yo'q.")

    candidate = get_object_or_404(CreditCandidate, pk=pk)
    if candidate.stage != "APPROVED":
        return HttpResponseBadRequest("Monitoring faqat kredit ajratilganda ochiladi.")

    candidate.monitoring_enabled = True
    candidate.save(update_fields=["monitoring_enabled", "updated_at"])
    return redirect("kredit_yo_naltirish:index")


@login_required
def add_monitoring(request, pk):
    if request.method != "POST":
        return HttpResponseBadRequest("Method noto'g'ri.")

    candidate = get_object_or_404(CreditCandidate, pk=pk)
    if candidate.stage not in {"APPROVED", "MONITORING"}:
        return HttpResponseBadRequest("Monitoring faqat kredit ajratilganda mumkin.")
    if not candidate.monitoring_enabled:
        return HttpResponseBadRequest("Monitoringga ruxsat berilmagan.")

    if not _can_add_monitoring(request.user, candidate):
        return HttpResponseBadRequest("Ruxsat yo'q.")

    monitoring_date_raw = (request.POST.get("monitoring_date") or "").strip()
    note = (request.POST.get("note") or "").strip()
    if not monitoring_date_raw:
        return HttpResponseBadRequest("Monitoring sanasi majburiy.")

    try:
        monitoring_date = timezone.datetime.strptime(monitoring_date_raw, "%Y-%m-%d").date()
    except ValueError:
        return HttpResponseBadRequest("Monitoring sanasi noto'g'ri.")

    images = request.FILES.getlist("images")
    documents = request.FILES.getlist("documents")

    for file_obj in images:
        name = (file_obj.name or "").lower()
        if not name.endswith((".jpg", ".jpeg", ".png")):
            return HttpResponseBadRequest("Rasm formati noto'g'ri.")

    for file_obj in documents:
        name = (file_obj.name or "").lower()
        if not name.endswith(".pdf"):
            return HttpResponseBadRequest("Hujjat formati noto'g'ri.")

    entry = CreditMonitoringEntry.objects.create(
        candidate=candidate,
        created_by=request.user,
        monitoring_date=monitoring_date,
        note=note,
    )

    if candidate.stage == "APPROVED":
        candidate.stage = "MONITORING"
        candidate.save(update_fields=["stage", "updated_at"])

    for file_obj in images:
        CreditMonitoringFile.objects.create(
            monitoring_entry=entry,
            file=file_obj,
            file_type="image",
        )

    for file_obj in documents:
        CreditMonitoringFile.objects.create(
            monitoring_entry=entry,
            file=file_obj,
            file_type="document",
        )

    return redirect("kredit_yo_naltirish:index")
