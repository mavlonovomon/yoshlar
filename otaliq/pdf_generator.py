import os
import io
import base64
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage,
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


def generate_otaliq_pdf(otaliq_obj):
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

    yosh = otaliq_obj.yosh
    leader = otaliq_obj.leader
    assistance = getattr(otaliq_obj, 'assistance', None)
    meetings = otaliq_obj.meetings.all().order_by('-meeting_date')[:5]

    elements = []

    # === SARLAVHA ===
    logo_img = _get_logo_image()

    if logo_img:
        header_table = Table(
            [[logo_img, Paragraph("OTALIQQA OLINGAN YOSHLAR ANKETASI", title_style)]],
            colWidths=[60, 420]
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
        ]))
        elements.append(header_table)
    else:
        elements.append(Paragraph("OTALIQQA OLINGAN YOSHLAR ANKETASI", title_style))

    elements.append(Paragraph(
        f"Toifa: {otaliq_obj.get_category_display()}",
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

    # === TOIFA ===
    elements.append(Paragraph("TOIFA MA'LUMOTI", section_style))
    elements.append(Spacer(1, 3*mm))

    cat_data = [
        [Paragraph("<b>Toifa</b>", label_style), Paragraph(otaliq_obj.get_category_display(), value_style)],
    ]
    cat_table = Table(cat_data, colWidths=[120, 350])
    cat_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
    ]))
    elements.append(cat_table)
    elements.append(Spacer(1, 5*mm))

    # === MAS'UL RAHBAR ===
    if leader:
        elements.append(Paragraph("MAS'UL RAHBAR", section_style))
        elements.append(Spacer(1, 3*mm))

        leader_data = [
            [Paragraph("<b>F.I.O.</b>", label_style), Paragraph(leader.full_name or "-", value_style)],
            [Paragraph("<b>Lavozim</b>", label_style), Paragraph(leader.position or "-", value_style)],
            [Paragraph("<b>Tashkilot turi</b>", label_style), Paragraph(leader.get_organization_type_display() if leader.organization_type else "-", value_style)],
            [Paragraph("<b>Tashkilot</b>", label_style), Paragraph(leader.organization_name or "-", value_style)],
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

        meeting_list = list(meetings[:4])
        for idx, meeting in enumerate(meeting_list, 1):
            meeting_photo = _get_photo_image(meeting.photo, max_width=280, max_height=200) if meeting.photo else None

            left_col = [
                [Paragraph(f"<b>#{idx}</b>  |  <b>Sana:</b> {_format_date(meeting.meeting_date)}", value_style)],
                [Spacer(1, 2*mm)],
                [Paragraph(meeting.description or "-", small_style)],
            ]
            left_table = Table(left_col, colWidths=[210])
            left_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))

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
            [Paragraph("<b>Tavsif</b>", label_style),
             Paragraph(assistance.description or "-", value_style)],
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
