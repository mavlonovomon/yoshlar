import os
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, KeepTogether, PageBreak,
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


def _get_photo_image(photo_field, max_width=350, max_height=170):
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


def generate_reyd_pdf(event_obj):
    buffer = io.BytesIO()
    page_width, page_height = landscape(A4)
    usable_width = page_width - 30*mm

    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
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
    label_style = ParagraphStyle(
        'Label', parent=styles['Normal'],
        fontName=BOLD_FONT,
        fontSize=10, textColor=colors.HexColor('#616161'),
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

    photos = list(event_obj.photos.all())
    elements = []

    # === SARLAVHA ===
    logo_img = _get_logo_image()

    if logo_img:
        header_table = Table(
            [[logo_img, Paragraph("IJTIMOIY PROFILAKTIKA TADBIRI MA'LUMOTI", title_style)]],
            colWidths=[60, usable_width - 60]
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
        ]))
        elements.append(header_table)
    else:
        elements.append(Paragraph("IJTIMOIY PROFILAKTIKA TADBIRI MA'LUMOTI", title_style))

    elements.append(Spacer(1, 5*mm))

    # === CHAP USTUN: MA'LUMOTLAR ===
    left_col_width = usable_width * 0.40
    right_col_width = usable_width * 0.60

    event_data = [
        [Paragraph("<b>Tadbir nomi:</b>", label_style), Paragraph(event_obj.title or "-", value_style)],
        [Paragraph("<b>Reyd turi:</b>", label_style), Paragraph(event_obj.get_event_type_display(), value_style)],
        [Paragraph("<b>Sana:</b>", label_style), Paragraph(event_obj.event_date.strftime("%d.%m.%Y") if event_obj.event_date else "-", value_style)],
        [Paragraph("<b>Mahalla:</b>", label_style), Paragraph(event_obj.mahalla.name if event_obj.mahalla else "-", value_style)],
    ]

    if event_obj.description:
        event_data.append([Paragraph("<b>Izoh:</b>", label_style), Paragraph(event_obj.description, value_style)])

    event_data.append([Paragraph("<b>Rasmlar soni:</b>", label_style), Paragraph(f"{len(photos)} ta", value_style)])

    left_table = Table(event_data, colWidths=[left_col_width * 0.35, left_col_width * 0.65])
    left_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdbdbd')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f5f5f5')),
    ]))

    # === BIRINCHI SAHIFA: 2 ustun (ma'lumotlar + 2 ta rasm) ===
    first_page_photos = photos[:2]
    remaining_photos = photos[2:]

    if first_page_photos:
        right_cells = []
        for photo in first_page_photos:
            photo_img = _get_photo_image(photo.image, max_width=right_col_width - 20, max_height=170)
            if photo_img:
                right_cells.append([photo_img])
            else:
                right_cells.append([Paragraph("<i>Rasm yuklanmadi</i>", small_style)])

        right_table = Table(right_cells, colWidths=[right_col_width])
        right_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdbdbd')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
    else:
        right_table = Table(
            [[Paragraph("<i>Rasm yuklanmagan</i>", small_style)]],
            colWidths=[right_col_width]
        )
        right_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdbdbd')),
        ]))

    main_table = Table([[left_table, right_table]], colWidths=[left_col_width, right_col_width])
    main_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(main_table)

    # === QOLGAN RASMLAR: har sahifada 2 tadan ===
    if remaining_photos:
        elements.append(PageBreak())

        for i in range(0, len(remaining_photos), 2):
            chunk = remaining_photos[i:i+2]
            chunk_cells = []
            for photo in chunk:
                photo_img = _get_photo_image(photo.image, max_width=(usable_width - 20) / 2, max_height=170)
                if photo_img:
                    chunk_cells.append(photo_img)
                else:
                    chunk_cells.append(Paragraph("<i>Rasm yuklanmadi</i>", small_style))

            row_table = Table([chunk_cells], colWidths=[(usable_width - 10) / 2] * len(chunk))
            row_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#bdbdbd')),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(KeepTogether([row_table, Spacer(1, 5*mm)]))

    # === YAKUNIY MA'LUMOT ===
    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph(
        f"Hujjat yaratilgan sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        small_style
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer
