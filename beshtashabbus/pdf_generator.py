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


def _get_photo_image(photo_field, max_width=220, max_height=160):
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


def generate_event_pdf(event_obj):
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

    photos = event_obj.photos.all()
    elements = []

    # === SARLAVHA ===
    logo_img = _get_logo_image()

    if logo_img:
        header_table = Table(
            [[logo_img, Paragraph("BESH TASHABBUS TADBIRI", title_style)]],
            colWidths=[60, 420]
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
        ]))
        elements.append(header_table)
    else:
        elements.append(Paragraph("BESH TASHABBUS TADBIRI", title_style))

    elements.append(Paragraph(
        event_obj.title or "-",
        ParagraphStyle('SubTitle', parent=styles['Normal'], fontName=BOLD_FONT, fontSize=12,
                       alignment=TA_CENTER, textColor=colors.HexColor('#424242'))
    ))
    elements.append(Spacer(1, 8*mm))

    # === ASOSIY MA'LUMOTLAR ===
    elements.append(Paragraph("TADBIR MA'LUMOTLARI", section_style))
    elements.append(Spacer(1, 3*mm))

    event_data = [
        [Paragraph("<b>Tadbir nomi</b>", label_style), Paragraph(event_obj.title or "-", value_style)],
        [Paragraph("<b>Yo'nalish</b>", label_style), Paragraph(event_obj.get_direction_display(), value_style)],
        [Paragraph("<b>Sana</b>", label_style), Paragraph(event_obj.event_date.strftime("%d.%m.%Y") if event_obj.event_date else "-", value_style)],
        [Paragraph("<b>Mahalla</b>", label_style), Paragraph(event_obj.mahalla.name if event_obj.mahalla else "-", value_style)],
        [Paragraph("<b>Qamrov</b>", label_style), Paragraph(f"{event_obj.coverage} kishi", value_style)],
    ]

    if event_obj.description:
        event_data.append([Paragraph("<b>Izoh</b>", label_style), Paragraph(event_obj.description, value_style)])

    event_table = Table(event_data, colWidths=[120, 350])
    event_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
    ]))
    elements.append(event_table)
    elements.append(Spacer(1, 5*mm))

    # === RASMLAR ===
    if photos.exists():
        elements.append(Paragraph("RASMLAR", section_style))
        elements.append(Spacer(1, 3*mm))

        photo_list = list(photos)
        for row_start in range(0, len(photo_list), 2):
            row_cells = []
            for offset in range(2):
                idx = row_start + offset
                if idx >= len(photo_list):
                    row_cells.append("")
                    continue
                photo = photo_list[idx]
                photo_img = _get_photo_image(photo.image, max_width=220, max_height=160)
                if photo_img:
                    row_cells.append(photo_img)
                else:
                    row_cells.append(Paragraph("<i>Rasm yuklanmadi</i>", small_style))

            row_table = Table([row_cells], colWidths=[235, 235])
            row_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('BOX', (0, 0), (0, 0), 0.5, colors.HexColor('#e0e0e0')),
                ('BOX', (1, 0), (1, 0), 0.5, colors.HexColor('#e0e0e0')),
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
