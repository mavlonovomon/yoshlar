from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Prefetch
from .models import Survey, SurveyStatus, Question, Choice, Response, Answer, QuestionType
import openpyxl


def _group_questions_by_section(questions):
    grouped = []
    section_map = {}
    for question in questions:
        section_title = (question.section or "").strip() or "Asosiy savollar"
        section = section_map.get(section_title)
        if section is None:
            section = {"title": section_title, "questions": []}
            section_map[section_title] = section
            grouped.append(section)
        section["questions"].append(question)
    return grouped

@login_required
def survey_list(request):
    """Dashboard to see all surveys in tabs."""
    q = (request.GET.get("q") or "").strip()
    qs = Survey.objects.all().order_by("-created_at")
    if q:
        qs = qs.filter(title__icontains=q)

    active_surveys = list(qs.filter(status=SurveyStatus.ACTIVE))
    paused_surveys = list(qs.filter(status=SurveyStatus.PAUSED))
    completed_surveys = list(qs.filter(status=SurveyStatus.COMPLETED))
    
    # Pre-calculate which surveys this user has already filled
    user_responses_qs = Response.objects.filter(user=request.user).order_by('id')
    user_responses_dict = {}  # survey_id -> first response id
    user_responses_count = {}  # survey_id -> count of responses
    for r in user_responses_qs:
        if r.survey_id not in user_responses_dict:
            user_responses_dict[r.survey_id] = r.id
        user_responses_count[r.survey_id] = user_responses_count.get(r.survey_id, 0) + 1

    for s in active_surveys + paused_surveys + completed_surveys:
        s.user_response_id = user_responses_dict.get(s.id)
        s.user_response_count = user_responses_count.get(s.id, 0)

    context = {
        'active_surveys': active_surveys,
        'paused_surveys': paused_surveys,
        'completed_surveys': completed_surveys,
        'is_site_admin': getattr(request.user, 'is_site_admin', request.user.is_superuser),
        'q': q,
    }
    return render(request, 'sorovnoma/survey_list.html', context)

@login_required
def survey_response_list(request, pk):
    """View responses for a specific survey."""
    survey = get_object_or_404(Survey, pk=pk)
    is_admin = getattr(request.user, 'is_site_admin', request.user.is_superuser)
    
    if is_admin:
        responses = survey.responses.all().select_related('user').prefetch_related('answers')
    else:
        # Regular users can only see their own responses
        responses = survey.responses.filter(user=request.user).prefetch_related('answers')

    list_questions = list(survey.questions.filter(show_in_list=True).order_by('order', 'id'))

    # Add custom answers as columns
    for resp in responses:
        ans_dict = {ans.question_id: ans for ans in resp.answers.all()}
        resp.custom_cols = []
        for q in list_questions:
            ans = ans_dict.get(q.id)
            if ans:
                if q.question_type in ['file', 'image'] and ans.file_body:
                    resp.custom_cols.append({'type': 'file', 'url': ans.file_body.url})
                else:
                    resp.custom_cols.append({'type': 'text', 'value': ans.body or '-'})
            else:
                resp.custom_cols.append({'type': 'text', 'value': '-'})
    
    question_sections = _group_questions_by_section(list(survey.questions.all().order_by('order', 'id')))

    context = {
        'survey': survey,
        'responses': responses,
        'list_questions': list_questions,
        'question_sections': question_sections,
        'is_admin': is_admin,
    }
    return render(request, 'sorovnoma/survey_response_list.html', context)

@login_required
def survey_response_detail(request, pk):
    """View a specific filled survey (Response detail)."""
    response_obj = get_object_or_404(
        Response.objects.select_related('survey', 'user').prefetch_related(
            Prefetch('answers', queryset=Answer.objects.select_related('question').order_by('question__order', 'question__id'))
        ),
        pk=pk,
    )
    
    # Only Admin, Rahbar or the owner of the response can see it
    is_admin = getattr(request.user, 'is_site_admin', request.user.is_superuser)
    if not is_admin and response_obj.user != request.user:
        messages.error(request, "Siz faqat o'zingiz to'ldirgan natijalarni ko'ra olasiz.")
        return redirect('sorovnoma:survey_list')

    context = {
        'response_obj': response_obj,
        'survey': response_obj.survey,
        'is_admin_view': is_admin and response_obj.user != request.user,
    }
    return render(request, 'sorovnoma/survey_response_detail.html', context)

@login_required
def export_survey_responses(request, pk):
    """Export responses to an Excel file."""
    if not getattr(request.user, 'is_site_admin', request.user.is_superuser):
        messages.error(request, "Bu funksiya faqat rahbar va administratorlar uchun.")
        return redirect('sorovnoma:survey_list')

    survey = get_object_or_404(Survey, pk=pk)
    responses = survey.responses.all().select_related('user').prefetch_related('answers__question')
    questions = survey.questions.all()

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Javoblar"

    # Header row
    header = ["ID", "Foydalanuvchi", "Sana"]
    for q in questions:
        header.append(q.text)
    sheet.append(header)

    # Data rows
    for response in responses:
        row = [
            response.id, 
            response.user.username if response.user else "Anonim", 
            response.created_at.strftime("%Y-%m-%d %H:%M")
        ]
        
        # Mapping question_id to answer body
        answers_dict = {}
        for ans in response.answers.all():
            if ans.file_body:
                answers_dict[ans.question_id] = ans.file_body.url
            else:
                answers_dict[ans.question_id] = ans.body or ""
        
        for q in questions:
            row.append(answers_dict.get(q.id, ""))
            
        sheet.append(row)

    response_file = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response_file['Content-Disposition'] = f'attachment; filename="survey_{survey.id}_responses.xlsx"'
    workbook.save(response_file)
    
    return response_file

@login_required
def survey_status_change(request, pk, status):
    """Change survey status (Admin/Rahbar only). POST only."""
    if request.method != "POST":
        return redirect('sorovnoma:survey_list')
    if not getattr(request.user, 'is_site_admin', request.user.is_superuser):
        messages.error(request, "Ruxsat yo'q.")
        return redirect('sorovnoma:survey_list')
    
    survey = get_object_or_404(Survey, pk=pk)
    if status in dict(SurveyStatus.choices):
        survey.status = status
        survey.save()
        messages.success(request, f"So'rovnoma holati '{survey.get_status_display()}' ga o'zgartirildi.")
    
    return redirect('sorovnoma:survey_list')

@login_required
def survey_fill(request, pk, response_id=None):
    """Form to fill out or edit a survey."""
    survey = get_object_or_404(Survey, pk=pk)
    existing_response = None
    
    if response_id:
        existing_response = get_object_or_404(Response.objects.prefetch_related('answers'), pk=response_id)
        # Check permission to edit
        is_admin = getattr(request.user, 'is_site_admin', request.user.is_superuser)
        if not is_admin:
            if existing_response.user != request.user:
                messages.error(request, "Siz boshqalarning javobini tahrirlay olmaysiz.")
                return redirect('sorovnoma:survey_list')
            if not survey.allow_edit:
                messages.error(request, "Ushbu so'rovnomani tahrirlashga ruxsat berilmagan.")
                return redirect('sorovnoma:survey_list')

    if survey.status != SurveyStatus.ACTIVE and not existing_response:
        messages.error(request, "Bu so'rovnoma faol emas.")
        return redirect('sorovnoma:survey_list')

    if request.method == 'POST':
        if existing_response:
            resp = existing_response
            # delete old answers (except files maybe?)
            resp.answers.all().delete()
        else:
            resp = Response.objects.create(survey=survey, user=request.user)
        
        for q in survey.questions.all():
            form_field_name = f'question_{q.id}'
            
            if q.question_type == QuestionType.FILE or q.question_type == QuestionType.IMAGE:
                file_val = request.FILES.get(form_field_name)
                if file_val:
                    Answer.objects.create(response=resp, question=q, file_body=file_val)
                # Keep old logic for file persistence during edit would go here if needed
            elif q.question_type == QuestionType.CHECKBOX:
                values = request.POST.getlist(form_field_name)
                if values:
                    Answer.objects.create(response=resp, question=q, body=", ".join(values))
            else:
                val = request.POST.get(form_field_name, '')
                if val:
                    Answer.objects.create(response=resp, question=q, body=val)
                    
        messages.success(request, "Sizning javoblaringiz saqlandi.")
        return redirect('sorovnoma:survey_list')

    # Pre-map answers for editing
    answers_map = {}
    if existing_response:
        for ans in existing_response.answers.all():
            if ans.question.question_type == QuestionType.CHECKBOX:
                # We need a list for checkbox selection in template
                answers_map[ans.question_id] = [x.strip() for x in (ans.body or "").split(',') if x.strip()]
            else:
                answers_map[ans.question_id] = ans.body or ""

    questions = list(survey.questions.all().order_by('order', 'id'))
    question_sections = _group_questions_by_section(questions)

    context = {
        'survey': survey,
        'existing_response': existing_response,
        'answers_map': answers_map,
        'question_sections': question_sections,
    }
    return render(request, 'sorovnoma/survey_fill.html', context)

@login_required
def survey_response_edit(request, pk):
    """Wrapper for editing a response."""
    response_obj = get_object_or_404(Response, pk=pk)
    # Check permissions (same check as survey_fill will perform)
    return survey_fill(request, response_obj.survey_id, response_id=pk)
