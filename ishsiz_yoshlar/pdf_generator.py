import os
import io
import base64
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage

from django.conf import settings


FONT_DIR = os.path.join(settings.STATIC_ROOT, 'fonts')
if not os.path.exists(FONT_DIR):
    FONT_DIR = os.path.join(settings.BASE_DIR, 'static', 'fonts')

try:
    pdfmetrics.registerFont(TTFont('NotoSans', os.path.join(FONT_DIR, 'NotoSans-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('NotoSans-Bold', os.path.join(FONT_DIR, 'NotoSans-Bold.ttf')))
    DEFAULT_FONT = 'NotoSans'
    BOLD_FONT = 'NotoSans-Bold'
except Exception:
    DEFAULT_FONT = 'Helvetica'
    BOLD_FONT = 'Helvetica-Bold'


def _get_photo_base64(photo_field):
    if not photo_field:
        return None
    try:
        photo_field.open('rb')
        data = photo_field.read()
        photo_field.close()
        b64 = base64.b64encode(data).decode('utf-8')
        ext = os.path.splitext(photo_field.name)[1].lower()
        mime = 'image/jpeg' if ext in ('.jpg', '.jpeg') else 'image/png'
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


def _get_photo_image(photo_field, max_width=120, max_height=150):
    if not photo_field:
        return None
    try:
        photo_field.open('rb')
        data = photo_field.read()
        photo_field.close()
        img = PILImage.open(io.BytesIO(data))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        ratio = min(max_width / img.width, max_height / img.height)
        new_w = int(img.width * ratio)
        new_h = int(img.height * ratio)
        img = img.resize((new_w, new_h), PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85)
        buf.seek(0)
        return RLImage(buf, width=new_w, height=new_h)
    except Exception:
        return None


def _format_date(dt):
    if not dt:
        return "-"
    if isinstance(dt, datetime):
        return dt.strftime("%d.%m.%Y %H:%M")
    return dt.strftime("%d.%m.%Y") if hasattr(dt, 'strftime') else str(dt)


def generate_youth_pdf(youth_obj):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Title'],
        fontName=BOLD_FONT,
        fontSize=16, spaceAfter=6, textColor=colors.HexColor('#1a237e'),
        alignment=TA_CENTER,
    )
    section_style = ParagraphStyle(
        'SectionHeader', parent=styles['Heading2'],
        fontName=BOLD_FONT,
        fontSize=12, spaceAfter=4, spaceBefore=8,
        textColor=colors.white, backColor=colors.HexColor('#1565c0'),
        leftIndent=4, rightIndent=4, borderPadding=(4, 4, 4, 4),
    )
    label_style = ParagraphStyle(
        'Label', parent=styles['Normal'],
        fontName=DEFAULT_FONT,
        fontSize=9, textColor=colors.HexColor('#616161'),
    )
    value_style = ParagraphStyle(
        'Value', parent=styles['Normal'],
        fontName=DEFAULT_FONT,
        fontSize=10, textColor=colors.HexColor('#212121'),
    )
    small_style = ParagraphStyle(
        'Small', parent=styles['Normal'],
        fontName=DEFAULT_FONT,
        fontSize=8, textColor=colors.HexColor('#757575'),
    )

    yosh = youth_obj.yosh
    leader = youth_obj.leader
    assistance = getattr(youth_obj, 'assistance', None)
    meetings = youth_obj.meetings.all().order_by('-meeting_date')[:5]

    elements = []

    # === SARLAVHA ===
    elements.append(Paragraph("ISHSIZ YOSHLAR ANKETASI", title_style))
    elements.append(Paragraph(
        f"Yil: {youth_obj.year} | Toifa: {youth_obj.get_category_display()}",
        ParagraphStyle('SubTitle', parent=styles['Normal'], fontName=DEFAULT_FONT, fontSize=10,
                       alignment=TA_CENTER, textColor=colors.HexColor('#424242'))
    ))
    elements.append(Spacer(1, 8*mm))

    # === RASM VA SHAXSIY MA'LUMOTLAR ===
    photo_img = _get_photo_image(yosh.photo, max_width=100, max_height=130)

    personal_data = [
        [Paragraph("<b>F.I.O.</b>", label_style), Paragraph(yosh.fullname or "-", value_style)],
        [Paragraph("<b>Tug'ilgan sana</b>", label_style), Paragraph(_format_date(yosh.birth_date), value_style)],
        [Paragraph("<b>JSHSHIR</b>", label_style), Paragraph(yosh.jshshir or "-", value_style)],
        [Paragraph("<b>Pasport</b>", label_style), Paragraph(yosh.passport_number or "-", value_style)],
        [Paragraph("<b>Guvohnoma</b>", label_style), Paragraph(yosh.guvohnoma_raqami or "-", value_style)],
        [Paragraph("<b>Manzil</b>", label_style), Paragraph(yosh.address or "-", value_style)],
        [Paragraph("<b>Telefon</b>", label_style), Paragraph(yosh.phone_number or "-", value_style)],
        [Paragraph("<b>Mahalla</b>", label_style), Paragraph(yosh.mahalla.name if yosh.mahalla else "-", value_style)],
    ]

    personal_table = Table(personal_data, colWidths=[90, 350])
    personal_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
    ]))

    if photo_img:
        layout_table = Table(
            [[photo_img, personal_table]],
            colWidths=[120, 370]
        )
        layout_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
        ]))
        elements.append(layout_table)
    else:
        elements.append(personal_table)

    elements.append(Spacer(1, 5*mm))

    # === TA'LIM MA'LUMOTLARI ===
    elements.append(Paragraph("TA'LIM MA'LUMOTLARI", section_style))
    elements.append(Spacer(1, 3*mm))

    edu_data = [
        [Paragraph("<b>Toifa</b>", label_style), Paragraph(youth_obj.get_category_display(), value_style)],
        [Paragraph("<b>Ta'lim tashkiloti</b>", label_style), Paragraph(youth_obj.otm_name or "-", value_style)],
        [Paragraph("<b>Yo'nalish</b>", label_style), Paragraph(youth_obj.direction or "-", value_style)],
    ]

    edu_table = Table(edu_data, colWidths=[120, 350])
    edu_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
    ]))
    elements.append(edu_table)
    elements.append(Spacer(1, 5*mm))

    # === MAS'UL RAHBAR ===
    if leader:
        elements.append(Paragraph("MAS'UL RAHBAR", section_style))
        elements.append(Spacer(1, 3*mm))

        leader_data = [
            [Paragraph("<b>F.I.O.</b>", label_style), Paragraph(leader.full_name or "-", value_style)],
            [Paragraph("<b>Lavozim</b>", label_style), Paragraph(leader.position or "-", value_style)],
            [Paragraph("<b>Tashkilot</b>", label_style), Paragraph(leader.organization or "-", value_style)],
            [Paragraph("<b>Telefon</b>", label_style), Paragraph(leader.phone_number or "-", value_style)],
            [Paragraph("<b>Daraja</b>", label_style), Paragraph(leader.get_level_display() if leader.level else "-", value_style)],
        ]

        leader_table = Table(leader_data, colWidths=[120, 350])
        leader_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
        ]))
        elements.append(leader_table)
        elements.append(Spacer(1, 5*mm))

    # === UCHRASHUVLAR ===
    if meetings.exists():
        elements.append(Paragraph("UCHRASHUVLAR TARIXI", section_style))
        elements.append(Spacer(1, 3*mm))

        for i, meeting in enumerate(meetings, 1):
            meeting_photo = _get_photo_image(meeting.photo, max_width=80, max_height=60) if meeting.photo else None

            meeting_data = [
                [Paragraph(f"<b>#{i}</b>", label_style),
                 Paragraph(f"<b>Sana:</b> {_format_date(meeting.meeting_date)}", value_style)],
                [Paragraph("", label_style),
                 Paragraph(meeting.description or "-", value_style)],
            ]

            if meeting_photo:
                meeting_data.append([
                    Paragraph("", label_style),
                    meeting_photo,
                ])

            meeting_table = Table(meeting_data, colWidths=[40, 430])
            meeting_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
            ]))
            elements.append(meeting_table)
            elements.append(Spacer(1, 2*mm))

        elements.append(Spacer(1, 3*mm))

    # === YORDAM MA'LUMOTI ===
    elements.append(Paragraph("YORDAM MA'LUMOTI", section_style))
    elements.append(Spacer(1, 3*mm))

    if assistance and assistance.provided:
        assist_data = [
            [Paragraph("<b>Yordam ko'rsatilgan</b>", label_style),
             Paragraph("Ha", ParagraphStyle('Green', parent=value_style, fontName=BOLD_FONT, textColor=colors.HexColor('#2e7d32')))],
            [Paragraph("<b>Yordam turi</b>", label_style),
             Paragraph(assistance.get_assistance_type_display() if assistance.assistance_type else "-", value_style)],
            [Paragraph("<b>Sana</b>", label_style),
             Paragraph(_format_date(assistance.date_provided), value_style)],
        ]
    else:
        assist_data = [
            [Paragraph("<b>Yordam ko'rsatilgan</b>", label_style),
             Paragraph("Yo'q", ParagraphStyle('Red', parent=value_style, fontName=BOLD_FONT, textColor=colors.HexColor('#c62828')))],
        ]

    assist_table = Table(assist_data, colWidths=[120, 350])
    assist_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
    ]))
    elements.append(assist_table)

    # === YAKUNIY MA'LUMOT ===
    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph(
        f"Anketa yaratilgan sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        small_style
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer
