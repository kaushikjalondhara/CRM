"""
CRM PDF Generation Service
Creates professional PDF documents for Invoices and Reports using ReportLab.
"""

import io
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from backend.services.invoice_service import get_invoice
from backend.services.settings_service import get_settings_by_category


def generate_invoice_pdf(invoice_id: int) -> tuple[io.BytesIO | None, str, str | None]:
    """
    Generate professional PDF bytes for an invoice.
    Returns: (buffer, filename, error)
    """
    invoice, err = get_invoice(invoice_id)
    if err or not invoice:
        return None, "", err or "Invoice not found"

    # Fetch company settings
    company_settings, _ = get_settings_by_category("company")
    inv_settings, _ = get_settings_by_category("invoice")

    comp_name = company_settings.get("company_name", "Apex CRM Enterprise")
    comp_email = company_settings.get("company_email", "billing@apexcrm.local")
    comp_phone = company_settings.get("company_phone", "+91 98765 43210")
    comp_addr = company_settings.get("company_address", "Business Bay, Tech Park, Suite 400")

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#1e3a8a')
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#475569')
    )
    section_heading = ParagraphStyle(
        'SecHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#0f172a')
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1e293b')
    )
    bold_body = ParagraphStyle(
        'BoldBody',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0f172a')
    )
    badge_style = ParagraphStyle(
        'Badge',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        alignment=2,
        textColor=colors.HexColor('#16a34a' if invoice['status'] == 'paid' else ('#ea580c' if invoice['status'] in ('sent', 'partially_paid') else '#64748b'))
    )

    story = []

    # 1. Header Section: Company info (Left) vs Invoice Title & Status (Right)
    comp_info = [
        Paragraph(f"<b>{comp_name}</b>", title_style),
        Spacer(1, 4),
        Paragraph(f"{comp_addr}", subtitle_style),
        Paragraph(f"Email: {comp_email} | Phone: {comp_phone}", subtitle_style),
    ]

    inv_meta = [
        Paragraph("INVOICE", ParagraphStyle('RightTitle', parent=title_style, alignment=2)),
        Paragraph(f"<b>Invoice #:</b> {invoice['invoice_number']}", ParagraphStyle('RightMeta', parent=subtitle_style, alignment=2)),
        Paragraph(f"<b>Date:</b> {invoice['invoice_date'] or 'N/A'}", ParagraphStyle('RightMeta', parent=subtitle_style, alignment=2)),
        Paragraph(f"<b>Due Date:</b> {invoice['due_date'] or 'N/A'}", ParagraphStyle('RightMeta', parent=subtitle_style, alignment=2)),
        Paragraph(f"Status: <b>{invoice['status'].upper()}</b>", badge_style),
    ]

    header_table = Table([[comp_info, inv_meta]], colWidths=[3.5 * inch, 3.5 * inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=14))

    # 2. Bill To & Payment Info
    cust_name = invoice.get('customer_name') or 'Valued Customer'
    comp_client = invoice.get('company_name') or ''
    cust_email = invoice.get('customer_email') or 'N/A'
    cust_phone = invoice.get('customer_phone') or 'N/A'

    bill_to = [
        Paragraph("<b>BILL TO:</b>", section_heading),
        Spacer(1, 3),
        Paragraph(f"<b>{cust_name}</b>", bold_body),
        Paragraph(f"{comp_client}", subtitle_style) if comp_client else Spacer(1, 0),
        Paragraph(f"Email: {cust_email}", subtitle_style),
        Paragraph(f"Phone: {cust_phone}", subtitle_style),
    ]

    payment_info = [
        Paragraph("<b>PAYMENT SUMMARY:</b>", section_heading),
        Spacer(1, 3),
        Paragraph(f"Total Amount: <b>₹{invoice['total_amount']:,.2f}</b>", body_style),
        Paragraph(f"Paid Amount: <font color='#16a34a'><b>₹{invoice['paid_amount']:,.2f}</b></font>", body_style),
        Paragraph(f"Balance Due: <font color='#dc2626'><b>₹{invoice['remaining_amount']:,.2f}</b></font>", bold_body),
    ]

    meta_table = Table([[bill_to, payment_info]], colWidths=[3.5 * inch, 3.5 * inch])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 18))

    # 3. Items Table
    item_header = [
        Paragraph("<b>#</b>", bold_body),
        Paragraph("<b>Item & Description</b>", bold_body),
        Paragraph("<b>Qty</b>", bold_body),
        Paragraph("<b>Unit Price</b>", bold_body),
        Paragraph("<b>Tax %</b>", bold_body),
        Paragraph("<b>Disc %</b>", bold_body),
        Paragraph("<b>Line Total</b>", bold_body)
    ]
    table_data = [item_header]

    for idx, itm in enumerate(invoice.get("items", []), start=1):
        name = itm.get("product_name") or "Item"
        desc = itm.get("description")
        item_text = f"<b>{name}</b>"
        if desc:
            item_text += f"<br/><font color='#64748b' size='7'>{desc}</font>"

        table_data.append([
            Paragraph(str(idx), body_style),
            Paragraph(item_text, body_style),
            Paragraph(str(itm.get("quantity", 1)), body_style),
            Paragraph(f"₹{float(itm.get('unit_price', 0)):,.2f}", body_style),
            Paragraph(f"{float(itm.get('tax_percentage', 0)):.1f}%", body_style),
            Paragraph(f"{float(itm.get('discount_percentage', 0)):.1f}%", body_style),
            Paragraph(f"₹{float(itm.get('total', 0)):,.2f}", bold_body),
        ])

    items_table = Table(table_data, colWidths=[0.3 * inch, 2.7 * inch, 0.6 * inch, 0.9 * inch, 0.7 * inch, 0.7 * inch, 1.1 * inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 14))

    # 4. Totals Breakdown (Right-aligned)
    totals_data = [
        ["Subtotal:", f"₹{invoice['subtotal']:,.2f}"],
        ["Tax Amount:", f"+ ₹{invoice['tax_amount']:,.2f}"],
        ["Discount Amount:", f"- ₹{invoice['discount_amount']:,.2f}"],
        ["Total Amount:", f"₹{invoice['total_amount']:,.2f}"],
        ["Paid to Date:", f"₹{invoice['paid_amount']:,.2f}"],
        ["Remaining Balance Due:", f"₹{invoice['remaining_amount']:,.2f}"]
    ]
    formatted_totals = []
    for row in totals_data:
        is_grand = "Total Amount" in row[0] or "Remaining Balance" in row[0]
        style_to_use = bold_body if is_grand else body_style
        formatted_totals.append([
            Paragraph(f"<b>{row[0]}</b>" if is_grand else row[0], style_to_use),
            Paragraph(f"<b>{row[1]}</b>" if is_grand else row[1], style_to_use)
        ])

    totals_table = Table(formatted_totals, colWidths=[2.2 * inch, 1.3 * inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 2), (-1, 2), 0.5, colors.HexColor('#cbd5e1')),
        ('LINEBELOW', (0, 4), (-1, 4), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor('#fee2e2' if invoice['remaining_amount'] > 0 else '#dcfce7')),
    ]))

    # Place Totals to the right
    wrapper_table = Table([["", totals_table]], colWidths=[3.5 * inch, 3.5 * inch])
    wrapper_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(wrapper_table)
    story.append(Spacer(1, 20))

    # 5. Terms / Notes Section
    terms_text = inv_settings.get("invoice_terms") or "Payment is due within the stipulated due date. Thank you for your business!"
    notes_text = invoice.get("notes") or ""

    if notes_text:
        story.append(Paragraph(f"<b>Notes:</b> {notes_text}", subtitle_style))
        story.append(Spacer(1, 6))

    story.append(Paragraph(f"<b>Terms & Conditions:</b> {terms_text}", subtitle_style))
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=8))
    story.append(Paragraph(f"Generated by {comp_name} on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ParagraphStyle('Footer', parent=subtitle_style, alignment=1, fontSize=8)))

    doc.build(story)
    pdf_buffer.seek(0)
    filename = f"Invoice_{invoice['invoice_number']}.pdf"
    return pdf_buffer, filename, None
