from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from .models import OtaliqYouth, OtaliqLeader, OtaliqMeeting
from .forms import OtaliqYouthForm, OtaliqMeetingForm, OtaliqAssistanceForm, OtaliqLeaderForm
from core.models import Mahalla, Yosh
from core.view_helpers import apply_sorting, normalize_sort_params, is_management_user
from django.contrib import messages
import openpyxl
from openpyxl.styles import Alignment, Border, Side, Font, PatternFill
from django.http import HttpResponse
from datetime import datetime
import datetime as dt_module

class OtaliqListView(LoginRequiredMixin, ListView):
    model = OtaliqYouth
    template_name = 'otaliq/list.html'
    context_object_name = 'youth_list'
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        qs = OtaliqYouth.objects.select_related('yosh__mahalla', 'leader', 'assistance').all()
        if not getattr(user, 'is_site_admin', False) and user.mahalla:
            qs = qs.filter(yosh__mahalla=user.mahalla)
        
        search = self.request.GET.get('q')
        if search:
            qs = qs.filter(Q(yosh__fullname__icontains=search) | Q(yosh__passport_number__icontains=search))
            
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category=category)

        mahalla_id = self.request.GET.get('mahalla')
        if mahalla_id and mahalla_id.isdigit():
            qs = qs.filter(yosh__mahalla_id=mahalla_id)

        leader_id = self.request.GET.get('leader')
        if leader_id == 'none':
            qs = qs.filter(leader__isnull=True)
        elif leader_id and leader_id.isdigit():
            qs = qs.filter(leader_id=leader_id)


        sort_field, sort_direction = normalize_sort_params(
            self.request,
            {'fullname', 'mahalla', 'category', 'leader', 'status', 'assistance'},
            'fullname',
        )
        self.sort_field = sort_field
        self.sort_direction = sort_direction
        sort_map = {
            'fullname': 'yosh__fullname',
            'mahalla': 'yosh__mahalla__name',
            'category': 'category',
            'leader': 'leader__full_name',
            'status': 'assistance__provided',
            'assistance': 'assistance__provided',
        }
        return apply_sorting(qs, sort_field, sort_direction, sort_map, 'fullname')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        categories = context.get('categories', OtaliqYouth.CATEGORY_CHOICES)
        selected_category = request.GET.get('category') or ''
        selected_leader = request.GET.get('leader') or ''
        selected_mahalla = request.GET.get('mahalla') or ''

        leaders = list(OtaliqLeader.objects.all())
        leader_options = [
            {'value': '', 'label': 'Barcha rahbarlar', 'selected': not selected_leader},
            {'value': 'none', 'label': "Biriktirilmagan", 'selected': selected_leader == 'none'},
        ] + [
            {'value': l.pk, 'label': str(l), 'selected': selected_leader == str(l.pk)}
            for l in leaders
        ]

        filter_fields = [
            {
                'type': 'search',
                'name': 'q',
                'label': 'Qidirish',
                'placeholder': 'F.I.Sh yoki Pasport...',
                'value': request.GET.get('q') or '',
            },
            {
                'type': 'select',
                'name': 'leader',
                'label': "Mas'ul rahbar",
                'autosubmit': True,
                'options': leader_options,
            },
            {
                'type': 'select',
                'name': 'category',
                'label': 'Toifa',
                'autosubmit': True,
                'options': [{'value': '', 'label': 'Barcha toifalar', 'selected': not selected_category}]
                + [
                    {'value': val, 'label': label, 'selected': selected_category == val}
                    for val, label in categories
                ],
            },
        ]

        if is_management_user(request.user):
            mahallas = Mahalla.objects.all().order_by('name')
            filter_fields.insert(
                2,
                {
                    'type': 'select',
                    'name': 'mahalla',
                    'label': 'Mahalla',
                    'autosubmit': True,
                    'options': [{'value': '', 'label': 'Barcha mahallalar', 'selected': not selected_mahalla}]
                    + [
                        {'value': m.pk, 'label': m.name, 'selected': selected_mahalla == str(m.pk)}
                        for m in mahallas
                    ],
                },
            )
            context['mahallas'] = mahallas

        context['filter_fields'] = filter_fields
        context['clear_filter_url'] = reverse_lazy('otaliq:list')
        context['selected_leader'] = selected_leader
        context['selected_mahalla'] = selected_mahalla
        context['categories'] = categories
        context['sort_field'] = getattr(self, 'sort_field', 'fullname')
        context['sort_direction'] = getattr(self, 'sort_direction', 'asc')
        return context

class OtaliqDetailView(LoginRequiredMixin, DetailView):
    model = OtaliqYouth
    template_name = 'otaliq/detail.html'
    context_object_name = 'item'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['meeting_form'] = OtaliqMeetingForm()
        assistance_instance = getattr(self.object, 'assistance', None)
        context['assistance'] = assistance_instance
        context['assistance_form'] = OtaliqAssistanceForm(instance=assistance_instance)
        context['meetings'] = self.object.meetings.all()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if 'add_meeting' in request.POST:
            form = OtaliqMeetingForm(request.POST, request.FILES)
            if form.is_valid():
                meeting = form.save(commit=False)
                meeting.otaliq_youth = self.object
                meeting.save()
                messages.success(request, "Uchrashuv muvaffaqiyatli qo'shildi.")
            else:
                messages.error(request, "Xatolik! Ma'lumotlarni tekshiring.")
        
        elif 'save_assistance' in request.POST:
            assistance_instance = getattr(self.object, 'assistance', None)
            form = OtaliqAssistanceForm(request.POST, request.FILES, instance=assistance_instance)
            if form.is_valid():
                assistance = form.save(commit=False)
                assistance.otaliq_youth = self.object
                assistance.save()
                messages.success(request, "Yordam ma'lumotlari yangilandi.")
            else:
                if form.errors.get('document'):
                    messages.error(request, form.errors['document'][0])
                else:
                    messages.error(request, "Xatolik! Yordam ma'lumotlarini saqlashda xato.")
        
        return redirect('otaliq:detail', pk=self.object.pk)

class OtaliqCreateView(LoginRequiredMixin, CreateView):
    model = OtaliqYouth
    form_class = OtaliqYouthForm
    template_name = 'otaliq/form.html'
    success_url = reverse_lazy('otaliq:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Yosh otaliqqa muvaffaqiyatli olindi.")
        return super().form_valid(form)

class SvodView(LoginRequiredMixin, ListView):
    model = Mahalla
    template_name = 'otaliq/svod.html'
    context_object_name = 'statistics'

    def get_queryset(self):
        mahallas = Mahalla.objects.all()
        
        return mahallas.annotate(
            total_youth=Count('yoshlar__otaliq_profile'),
            with_meeting=Count('yoshlar__otaliq_profile__meetings', distinct=True),
            total_assisted=Count('yoshlar__otaliq_profile', filter=Q(yoshlar__otaliq_profile__assistance__provided=True)),
        ).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for s in context['statistics']:
            s.percent = round((s.total_assisted / s.total_youth * 100), 1) if s.total_youth > 0 else 0
        return context

class OtaliqLeaderListView(LoginRequiredMixin, ListView):
    model = OtaliqLeader
    template_name = 'otaliq/leader_list.html'
    context_object_name = 'leaders'

class OtaliqLeaderCreateView(LoginRequiredMixin, CreateView):
    model = OtaliqLeader
    form_class = OtaliqLeaderForm
    template_name = 'otaliq/leader_form.html'
    success_url = reverse_lazy('otaliq:leader_list')


class OtaliqYouthPDFView(LoginRequiredMixin, View):
    def get(self, request, pk):
        item = get_object_or_404(OtaliqYouth, pk=pk)
        user = request.user
        if not getattr(user, 'is_site_admin', False) and user.mahalla and item.yosh.mahalla != user.mahalla:
            return HttpResponse("Ruxsat yo'q", status=403)

        from .pdf_generator import generate_otaliq_pdf
        pdf_buffer = generate_otaliq_pdf(item)

        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        filename = f"anketa_{item.yosh.fullname.replace(' ', '_')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
