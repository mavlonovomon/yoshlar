import os
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage,
)
from reportlab.lib.enums import TA_CENTER
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


def _get_logo_image():
    logo_path = os.path.join(settings.MEDIA_ROOT, 'Yoshlar_ishlari_agentligi_logotipi.svg')
    if not os.path.exists(logo_path):
        return None
    try:
        import svglib.svglib as svglib
        drawing = svglib.svg2rlg(logo_path)
        if drawing is None:
            return None
        target_height = 24
        scale = target_height / drawing.height
        drawing.width = drawing.width * scale
        drawing.height = target_height
        drawing.scale(scale, scale)
        return drawing
    except Exception:
        return None


def _get_photo_image(photo_field, max_width=100, max_height=130):
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


def generate_migration_pdf(migration_obj):
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

    yosh = migration_obj.yosh
    meetings = migration_obj.meetings.all().order_by('-meeting_date')[:4]

    elements = []

    # === SARLAVHA ===
    logo_img = _get_logo_image()

    if logo_img:
        header_table = Table(
            [[logo_img, Paragraph("MIGRATSIYADAGI YOSH BILAN SUHBAT", title_style)]],
            colWidths=[60, 420]
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
        ]))
        elements.append(header_table)
    else:
        elements.append(Paragraph("MIGRATSIYADAGI YOSH BILAN SUHBAT", title_style))

    elements.append(Paragraph(
        f"Davlat: {migration_obj.destination_country} | Sabab: {migration_obj.get_reason_display()}",
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

    # === MIGRATSIYA MA'LUMOTI ===
    elements.append(Paragraph("MIGRATSIYA MA'LUMOTI", section_style))
    elements.append(Spacer(1, 3*mm))

    migration_data = [
        [Paragraph("<b>Sabab</b>", label_style), Paragraph(migration_obj.get_reason_display(), value_style)],
        [Paragraph("<b>Chiqib ketgan sana</b>", label_style), Paragraph(_format_date(migration_obj.departure_date), value_style)],
        [Paragraph("<b>Davlat</b>", label_style), Paragraph(migration_obj.destination_country or "-", value_style)],
        [Paragraph("<b>Provinsiya</b>", label_style), Paragraph(migration_obj.destination_province or "-", value_style)],
        [Paragraph("<b>Manzil</b>", label_style), Paragraph(migration_obj.destination_address or "-", value_style)],
    ]

    migration_table = Table(migration_data, colWidths=[120, 350])
    migration_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
    ]))
    elements.append(migration_table)
    elements.append(Spacer(1, 5*mm))

    # === SUHBATLAR ===
    if meetings.exists():
        elements.append(Paragraph("SUHBATLAR TARIXI", section_style))
        elements.append(Spacer(1, 3*mm))

        meeting_list = list(meetings)
        for idx, meeting in enumerate(meeting_list, 1):
            meeting_photo = _get_photo_image(meeting.photo, max_width=280, max_height=200) if meeting.photo else None

            # Chap ustun — matn
            left_rows = [
                [Paragraph(f"<b>#{idx}</b>  |  <b>Sana:</b> {_format_date(meeting.meeting_date)}", value_style)],
                [Spacer(1, 2*mm)],
            ]

            if meeting.return_date:
                left_rows.append([Paragraph(f"<b>Qaytish:</b> {_format_date(meeting.return_date)}", small_style)])
            if meeting.work_title:
                left_rows.append([Paragraph(f"<b>Ish:</b> {meeting.work_title}", small_style)])
            if meeting.work_income:
                left_rows.append([Paragraph(f"<b>Daromad:</b> ${meeting.work_income:,.0f}", small_style)])
            if meeting.work_conditions_rating:
                left_rows.append([Paragraph(f"<b>Ish sharoiti:</b> {meeting.work_conditions_rating}/10", small_style)])
            if meeting.education_institution:
                left_rows.append([Paragraph(f"<b>Dargoh:</b> {meeting.education_institution}", small_style)])
            if meeting.education_direction:
                left_rows.append([Paragraph(f"<b>Yo'nalish:</b> {meeting.education_direction}", small_style)])
            if meeting.education_course:
                left_rows.append([Paragraph(f"<b>Kurs:</b> {meeting.education_course}", small_style)])
            if meeting.description:
                left_rows.append([Spacer(1, 2*mm)])
                left_rows.append([Paragraph(meeting.description, small_style)])

            left_table = Table(left_rows, colWidths=[210])
            left_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))

            # O'ng ustun — rasm
            if meeting_photo:
                right_col = [[meeting_photo]]
            else:
                right_col = [[Paragraph("<i>Rasm yo'q</i>", small_style)]]
            right_table = Table(right_col, colWidths=[250])
            right_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))

            row_table = Table([[left_table, right_table]], colWidths=[220, 260])
            row_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
                ('LINEAFTER', (0, 0), (0, 0), 0.5, colors.HexColor('#e0e0e0')),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(row_table)
            elements.append(Spacer(1, 2*mm))

        elements.append(Spacer(1, 3*mm))

    # === YAKUNIY MA'LUMOT ===
    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph(
        f"Anketa yaratilgan sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        small_style
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer
