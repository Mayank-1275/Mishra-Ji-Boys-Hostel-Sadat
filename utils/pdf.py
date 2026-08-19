from fpdf import FPDF
import io
import base64
from PIL import Image
import streamlit as st
import os
from pypdf import PdfReader, PdfWriter

# Your hostel name shown at the top of every PDF.
# (Change this text to your real hostel name.)
HOSTEL_NAME = st.secrets.get("hostel", {}).get("name", "My Hostel")

# ---- Colour palette (R, G, B) ----
PRIMARY = (30, 58, 95)     # deep navy - header band & headings
ACCENT  = (201, 162, 39)   # gold - accent line
PANEL   = (245, 246, 248)  # light grey - photo panel background
MUTED   = (110, 120, 130)  # muted grey - labels & footer
DARK    = (33, 37, 41)     # near-black - values

def _pdf_text(value):
    """Make text safe for the built-in PDF font (which lacks the rupee sign)."""
    if value in (None, ""):
        return "-"
    return str(value).replace("₹", "Rs. ")


class HostelPDF(FPDF):
    """A base PDF with a styled header and footer for the whole app."""

    def header(self):
        # Navy band across the top (slightly taller to fit contact line).
        self.set_fill_color(*PRIMARY)
        self.rect(0, 0, 210, 30, "F")
        # Hostel name.
        self.set_y(6)
        self.set_font("Helvetica", "B", 19)
        self.set_text_color(255, 255, 255)
        self.cell(0, 9, HOSTEL_NAME, align="C", new_x="LMARGIN", new_y="NEXT")
        # Contact numbers under the name.
        self.set_font("Helvetica", "", 10)
        self.cell(0, 5, "Contact: 9415970296, 9453367832", align="C",
                  new_x="LMARGIN", new_y="NEXT")
        # Thin gold accent line under the band.
        self.set_fill_color(*ACCENT)
        self.rect(0, 30, 210, 1.5, "F")
        self.ln(12)
        self.set_text_color(*DARK)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 10, f"{HOSTEL_NAME}   |   Member Profile Card   |   Page {self.page_no()}",
                  align="C")


def _decode_pil(base64_string):
    """Turn stored Base64 text back into a Pillow image (or None)."""
    if not base64_string:
        return None
    try:
        raw = base64.b64decode(base64_string)
        return Image.open(io.BytesIO(raw))
    except Exception:
        return None


def member_profile_pdf(member):
    """
    Build a clean member profile card PDF and return it as bytes.
    Layout: member photo top-right with father's photo below it;
    details on the left; enlarged ID photos (Front | Back) side by side,
    on the same page if they fit else on page 2.
    """
    pdf = HostelPDF()
    pdf.add_page()

    # ---- Title ----
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*PRIMARY)
    pdf.set_xy(15, 34)
    pdf.cell(0, 10, "Member Profile Card", new_x="LMARGIN", new_y="NEXT")

    # ---- Right column: Member photo, Father's photo below ----
    panel_x, panel_w = 150, 45
    member_panel_y, member_panel_h = 44, 42
    father_panel_y, father_panel_h = member_panel_y + member_panel_h + 6, 42

    def _draw_photo_panel(x, y, w, h, img_b64, empty_label):
        pdf.set_fill_color(*PANEL)
        pdf.rect(x, y, w, h, "F")
        pil_img = _decode_pil(img_b64)
        if pil_img is not None:
            try:
                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")
                pad = 3
                max_w, max_h = w - 2 * pad, h - 2 * pad
                iw, ih = pil_img.size
                ratio = min(max_w / iw, max_h / ih)
                dw, dh = iw * ratio, ih * ratio
                ix = x + (w - dw) / 2
                iy = y + (h - dh) / 2
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=85)
                buf.seek(0)
                pdf.image(buf, x=ix, y=iy, w=dw, h=dh)
            except Exception:
                pass
        else:
            pdf.set_xy(x, y + h / 2 - 4)
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*MUTED)
            pdf.cell(w, 8, empty_label, align="C")

    # Member photo (top) + small caption.
    _draw_photo_panel(panel_x, member_panel_y, panel_w, member_panel_h,
                      member.get("photo"), "No photo")
    pdf.set_xy(panel_x, member_panel_y + member_panel_h + 1)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(panel_w, 4, "Member", align="C")

    # Father's photo (directly below) + caption.
    _draw_photo_panel(panel_x, father_panel_y + 3, panel_w, father_panel_h,
                      member.get("father_pic"), "No photo")
    pdf.set_xy(panel_x, father_panel_y + father_panel_h + 4)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(panel_w, 4, "Father", align="C")

    # ---- Details (left side) ----
    rows = [
        ("Name", member.get("name")),
        ("Date of Birth", member.get("dob")),
        ("Address", member.get("address")),
        ("Father's Name", member.get("father_name")),
        ("Father's Mobile", member.get("father_mobile")),
        ("Mother's Name", member.get("mother_name")),
        ("Mother's Mobile", member.get("mother_mobile")),
        ("WhatsApp", member.get("whatsapp")),
    ]

    label_x, value_x, value_w, row_gap = 15, 58, 78, 3
    pdf.set_xy(label_x, 48)
    for i, (label, value) in enumerate(rows):
        y = pdf.get_y()
        if i % 2 == 0:
            pdf.set_fill_color(250, 250, 251)
            pdf.rect(label_x - 2, y - 1, 125, 9, "F")
        pdf.set_xy(label_x, y)
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(value_x - label_x, 7, label)
        pdf.set_xy(value_x, y)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(value_w, 7, _pdf_text(value))
        pdf.set_y(pdf.get_y() + row_gap)

    # ---- ID photos: side by side, enlarged, same page if they fit ----
    # Figure out where content so far ends (max of details bottom and father panel).
    details_bottom = pdf.get_y()
    right_col_bottom = father_panel_y + father_panel_h + 10
    content_bottom = max(details_bottom, right_col_bottom)

    # A4 is 297mm tall; footer sits near the bottom. Leave margin.
    page_bottom_limit = 285
    heading_h = 14
    # Two ID panels side by side across the usable width (15..195 = 180mm).
    gap = 10
    id_panel_w = (180 - gap) / 2          # ~85mm each
    id_panel_h = id_panel_w * 0.66        # keep a card-like ratio, ~56mm

    needed = heading_h + id_panel_h + 12
    start_y = content_bottom + 8

    # If it won't fit on this page, start a fresh page and use bigger panels.
    if start_y + needed > page_bottom_limit:
        pdf.add_page()
        start_y = 40
        id_panel_h = id_panel_w * 0.75    # a bit taller on a dedicated page

    # Section heading.
    pdf.set_xy(15, start_y)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, 8, "ID Documents", new_x="LMARGIN", new_y="NEXT")
    pdf.set_fill_color(*ACCENT)
    pdf.rect(15, start_y + 9, 40, 0.8, "F")

    panels_y = start_y + 16
    id_docs = [("ID Front", member.get("id_front")),
               ("ID Back", member.get("id_back"))]
    x = 15
    for label, img_b64 in id_docs:
        _draw_photo_panel(x, panels_y, id_panel_w, id_panel_h, img_b64,
                          "Not provided")
        pdf.set_xy(x, panels_y + id_panel_h + 2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*MUTED)
        pdf.cell(id_panel_w, 6, label, align="C")
        x += id_panel_w + gap

    # Push signatures near the bottom of the page (A4 height ~297mm).
    natural_y = panels_y + id_panel_h + 18
    sig_y = max(natural_y, 262)  # sit near the page bottom, but never overlap IDs # a little below the ID photos

    # If there isn't enough room on this page, move signatures to a new page.
    if sig_y > 265:
        pdf.add_page()
        sig_y = 60

    line_w = 70
    left_x = 20
    right_x = 120

    pdf.set_draw_color(*MUTED)
    # Draw the two signature lines.
    pdf.line(left_x, sig_y, left_x + line_w, sig_y)
    pdf.line(right_x, sig_y, right_x + line_w, sig_y)

    # Labels under each line.
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*DARK)
    pdf.set_xy(left_x, sig_y + 2)
    pdf.cell(line_w, 6, "Authority Signature", align="C")
    pdf.set_xy(right_x, sig_y + 2)
    pdf.cell(line_w, 6, "Member Signature", align="C")

    # Date line under the authority signature.
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.set_xy(left_x, sig_y + 10)
    pdf.cell(line_w, 5, "Date: ____________________", align="C")

    return bytes(pdf.output())


def rent_receipt_pdf(data):
    """
    Build a rent receipt PDF and return it as bytes.
    'data' is a dictionary with the payment details.
    """
    pdf = HostelPDF()
    pdf.add_page()

    # ---- Title ----
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*PRIMARY)
    pdf.set_xy(15, 34)
    pdf.cell(0, 10, "Rent Receipt", new_x="LMARGIN", new_y="NEXT")

    # Receipt number + date on the right.
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.set_xy(120, 34)
    pdf.cell(75, 6, f"Receipt No: {data.get('receipt_no', '-')}", align="R",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(120, 40)
    pdf.cell(75, 6, f"Date: {data.get('date', '-')}", align="R")

    pdf.ln(14)

    # ---- Detail rows ----
    rows = [
        ("Member Name", data.get("member_name")),
        ("Room / Bed", data.get("room_bed")),
        ("Amount Received", data.get("amount")),
        ("Daily Rate", data.get("daily_rate")),
        ("Days Paid (this payment)", data.get("paid_days")),
        ("Received By", data.get("receiver")),
        ("New Balance", data.get("balance")),
    ]

    label_x, value_x = 20, 90
    for i, (label, value) in enumerate(rows):
        y = pdf.get_y()
        if i % 2 == 0:
            pdf.set_fill_color(250, 250, 251)
            pdf.rect(label_x - 3, y - 1, 172, 10, "F")

        pdf.set_xy(label_x, y)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*MUTED)
        pdf.cell(value_x - label_x, 8, label)

        pdf.set_xy(value_x, y)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(90, 8, _pdf_text(value))

        pdf.set_y(y + 10)

    # ---- Thank-you note ----
    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 6, "This is a system-generated receipt. Thank you.")

    return bytes(pdf.output())

def guest_receipt_pdf(data):
    """
    Build a temp-guest settlement receipt PDF and return it as bytes.
    'data' is a dictionary with the guest's stay details.
    """
    pdf = HostelPDF()
    pdf.add_page()

    # ---- Title ----
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*PRIMARY)
    pdf.set_xy(15, 34)
    pdf.cell(0, 10, "Guest Settlement Receipt", new_x="LMARGIN", new_y="NEXT")

    # Receipt number + date on the right.
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.set_xy(120, 34)
    pdf.cell(75, 6, f"Receipt No: G{data.get('receipt_no', '-')}", align="R",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(120, 40)
    pdf.cell(75, 6, f"Date: {data.get('date', '-')}", align="R")

    pdf.ln(14)

    # ---- Detail rows ----
    rows = [
        ("Guest Name", data.get("guest_name")),
        ("Purpose", data.get("purpose")),
        ("Room No", data.get("room_no")),
        ("Stay Period", data.get("stay_period")),
        ("Total Rent", data.get("total_rent")),
        ("Advance Given", data.get("advance")),
        ("Balance Settled", data.get("balance")),
    ]

    label_x, value_x = 20, 90
    for i, (label, value) in enumerate(rows):
        y = pdf.get_y()
        if i % 2 == 0:
            pdf.set_fill_color(250, 250, 251)
            pdf.rect(label_x - 3, y - 1, 172, 10, "F")

        pdf.set_xy(label_x, y)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*MUTED)
        pdf.cell(value_x - label_x, 8, label)

        pdf.set_xy(value_x, y)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(90, 8, _pdf_text(value))

        pdf.set_y(y + 10)

    # ---- Thank-you note ----
    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 6, "This is a system-generated receipt. Thank you for staying with us.")

    return bytes(pdf.output())

def guest_profile_pdf(guest):
    """Build a guest profile card PDF (with photos) and return it as bytes."""
    pdf = HostelPDF()
    pdf.add_page()

    # ---- Title ----
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*PRIMARY)
    pdf.set_xy(15, 34)
    pdf.cell(0, 10, "Guest Profile Card", new_x="LMARGIN", new_y="NEXT")

    # ---- Photo panel (top-right) ----
    panel_x, panel_y, panel_w, panel_h = 150, 44, 45, 55
    pdf.set_fill_color(*PANEL)
    pdf.rect(panel_x, panel_y, panel_w, panel_h, "F")

    pil_img = _decode_pil(guest.get("photo"))
    if pil_img is not None:
        try:
            if pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")
            pad = 3
            max_w, max_h = panel_w - 2 * pad, panel_h - 2 * pad
            iw, ih = pil_img.size
            ratio = min(max_w / iw, max_h / ih)
            draw_w, draw_h = iw * ratio, ih * ratio
            img_x = panel_x + (panel_w - draw_w) / 2
            img_y = panel_y + (panel_h - draw_h) / 2
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=85)
            buf.seek(0)
            pdf.image(buf, x=img_x, y=img_y, w=draw_w, h=draw_h)
        except Exception:
            pass
    else:
        pdf.set_xy(panel_x, panel_y + panel_h / 2 - 4)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*MUTED)
        pdf.cell(panel_w, 8, "No photo", align="C")

    # ---- Details (left side) ----
    rows = [
        ("Name", guest.get("name")),
        ("Mobile", guest.get("whatsapp")),
        ("Purpose", guest.get("purpose")),
        ("Room No", guest.get("room_no")),
        ("Start Date", guest.get("start_date")),
        ("Leaving Date", guest.get("leaving_date")),
        ("Total Rent", guest.get("total_rent")),
        ("Advance Given", guest.get("advance")),
    ]

    label_x, value_x, value_w, row_gap = 15, 58, 88, 3
    pdf.set_xy(label_x, 48)
    for i, (label, value) in enumerate(rows):
        y = pdf.get_y()
        if i % 2 == 0:
            pdf.set_fill_color(250, 250, 251)
            pdf.rect(label_x - 2, y - 1, 128, 9, "F")
        pdf.set_xy(label_x, y)
        pdf.set_font("Helvetica", "B", 10.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(value_x - label_x, 7, label)
        pdf.set_xy(value_x, y)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(value_w, 7, _pdf_text(value))
        pdf.set_y(pdf.get_y() + row_gap)

    # ---- Documents row: ID Front, ID Back ----
    docs = [
        ("ID Front", guest.get("id_front")),
        ("ID Back", guest.get("id_back")),
    ]
    start_y = max(pdf.get_y() + 6, 108)

    pdf.set_xy(15, start_y)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, 8, "Documents", new_x="LMARGIN", new_y="NEXT")
    pdf.set_fill_color(*ACCENT)
    pdf.rect(15, start_y + 9, 40, 0.8, "F")

    panels_y = start_y + 16
    panel_w2, panel_h2 = 58, 50
    gap = 6
    x = 15
    for label, img_b64 in docs:
        pdf.set_fill_color(*PANEL)
        pdf.rect(x, panels_y, panel_w2, panel_h2, "F")
        pil_img = _decode_pil(img_b64)
        if pil_img is not None:
            try:
                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")
                pad = 3
                max_w, max_h = panel_w2 - 2 * pad, panel_h2 - 2 * pad
                iw, ih = pil_img.size
                ratio = min(max_w / iw, max_h / ih)
                draw_w, draw_h = iw * ratio, ih * ratio
                img_x = x + (panel_w2 - draw_w) / 2
                img_y = panels_y + (panel_h2 - draw_h) / 2
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=85)
                buf.seek(0)
                pdf.image(buf, x=img_x, y=img_y, w=draw_w, h=draw_h)
            except Exception:
                pass
        else:
            pdf.set_xy(x, panels_y + panel_h2 / 2 - 4)
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*MUTED)
            pdf.cell(panel_w2, 8, "Not provided", align="C")
        pdf.set_xy(x, panels_y + panel_h2 + 2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*MUTED)
        pdf.cell(panel_w2, 6, label, align="C")
        x += panel_w2 + gap

    return bytes(pdf.output())

def report_pdf(title, date_range, columns, rows, total_label, total_value):
    """
    Build a generic report PDF (table + total at bottom) and return bytes.
    - title: report name (e.g. "Rent Income Report")
    - date_range: e.g. "01-Aug-2026 to 18-Aug-2026"
    - columns: list of column headers
    - rows: list of lists (each inner list = one row, same length as columns)
    - total_label / total_value: shown at the bottom
    """
    pdf = HostelPDF()
    pdf.add_page()

    # ---- Title + date range ----
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*PRIMARY)
    pdf.set_xy(15, 34)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.set_x(15)
    pdf.cell(0, 6, f"Period: {date_range}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ---- Table header ----
    usable_w = 180
    col_w = usable_w / len(columns)
    pdf.set_x(15)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(*PRIMARY)
    pdf.set_text_color(255, 255, 255)
    for col in columns:
        pdf.cell(col_w, 9, _pdf_text(col), border=0, align="C", fill=True)
    pdf.ln(9)

    # ---- Table rows ----
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*DARK)
    fill = False
    for row in rows:
        pdf.set_x(15)
        if fill:
            pdf.set_fill_color(245, 246, 248)
        else:
            pdf.set_fill_color(255, 255, 255)
        for item in row:
            pdf.cell(col_w, 8, _pdf_text(item), border="B", align="C", fill=True)
        pdf.ln(8)
        fill = not fill

    # ---- Total row ----
    pdf.ln(2)
    pdf.set_x(15)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(*ACCENT)
    pdf.set_text_color(*DARK)
    pdf.cell(usable_w - col_w, 10, _pdf_text(total_label), border=0, align="R",
             fill=True)
    pdf.cell(col_w, 10, _pdf_text(total_value), border=0, align="C", fill=True)
    pdf.ln(12)

    return bytes(pdf.output())



def append_rules_pdf(profile_pdf_bytes, rules_path=os.path.join("assets", "rules.pdf")):
    """
    Take a generated profile-card PDF (as bytes) and append the pages of
    assets/rules.pdf after it. Returns the merged PDF as bytes.
    If the rules file is missing or unreadable, returns the profile PDF unchanged.
    """
    if not os.path.exists(rules_path):
        return profile_pdf_bytes
    try:
        import io
        writer = PdfWriter()

        # 1. Add all pages of the profile card.
        profile_reader = PdfReader(io.BytesIO(profile_pdf_bytes))
        for page in profile_reader.pages:
            writer.add_page(page)

        # 2. Add all pages of the rules PDF.
        rules_reader = PdfReader(rules_path)
        for page in rules_reader.pages:
            writer.add_page(page)

        # 3. Write the merged result to bytes.
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
    except Exception:
        # If anything goes wrong, fall back to the profile card alone.
        return profile_pdf_bytes