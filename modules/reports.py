import io
import csv
from datetime import timedelta

import streamlit as st
import pandas as pd

from utils.database import get_cursor
from utils.helpers import today_ist, format_money, format_date
from utils.pdf import report_pdf

REPORT_TYPES = ["Rent Income", "Expenses", "Temp Guest Income", "Comprehensive"]


def _csv_bytes(columns, rows):
    """Turn columns + rows into CSV text."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    writer.writerows(rows)
    return buf.getvalue()


def reports_screen():
    st.markdown(
        "<h1 style='margin-bottom:0;'>Reports & Export</h1>"
        "<div style='color:#64748b;font-size:0.9rem;margin-bottom:0.6rem;'>"
        "Pick a date range and type, then download as PDF or CSV</div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        start = st.date_input("Start date",
                              value=today_ist().replace(day=1))
    with col2:
        end = st.date_input("End date", value=today_ist())
    with col3:
        report_type = st.selectbox("Report type", REPORT_TYPES)

    if end < start:
        st.error("End date cannot be before start date.")
        return

    date_range = f"{format_date(start)} to {format_date(end)}"

    st.divider()

    if report_type == "Rent Income":
        _rent_report(start, end, date_range)
    elif report_type == "Expenses":
        _expense_report(start, end, date_range)
    elif report_type == "Temp Guest Income":
        _guest_report(start, end, date_range)
    else:
        _comprehensive_report(start, end, date_range)


def _download_buttons(title, date_range, columns, rows, total_label, total_value,
                      filename_stub):
    """Show PDF + CSV download buttons for a report."""
    if not rows:
        st.info("No records in this period.")
        return

    st.dataframe(pd.DataFrame(rows, columns=columns),
                 use_container_width=True, hide_index=True)

    # Total card.
    st.markdown(
        f"<div style='background:#ffffff;border:1px solid #e2e8f0;"
        f"border-left:5px solid #0d9488;border-radius:12px;padding:14px 16px;"
        f"margin:10px 0;display:flex;justify-content:space-between;align-items:center;'>"
        f"<span style='color:#64748b;font-weight:600;'>{total_label}</span>"
        f"<span style='font-size:1.35rem;font-weight:800;color:#0f172a;'>"
        f"{total_value}</span></div>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        pdf_bytes = report_pdf(title, date_range, columns, rows,
                               total_label, total_value)
        st.download_button("📄 Download PDF", data=pdf_bytes,
                           file_name=f"{filename_stub}.pdf",
                           mime="application/pdf", use_container_width=True)
    with col2:
        csv_data = _csv_bytes(columns, rows + [[total_label, total_value] +
                              [""] * (len(columns) - 2)])
        st.download_button("⬇️ Download CSV", data=csv_data,
                           file_name=f"{filename_stub}.csv",
                           mime="text/csv", use_container_width=True)


def _rent_report(start, end, date_range):
    conn, cursor = get_cursor()
    cursor.execute(
        """
        SELECT r.txn_date, m.name, r.amount_received, r.paid_days, r.receiver_name
        FROM rent_history r JOIN members m ON m.id = r.member_id
        WHERE r.txn_date BETWEEN %s AND %s
        ORDER BY r.txn_date
        """,
        (start, end),
    )
    data = cursor.fetchall()
    columns = ["Date", "Member", "Amount", "Days", "Received By"]
    rows = [[format_date(d["txn_date"]), d["name"],
             format_money(d["amount_received"]), f"{float(d['paid_days']):.2f}",
             d["receiver_name"]] for d in data]
    total = sum(float(d["amount_received"]) for d in data)
    _download_buttons("Rent Income Report", date_range, columns, rows,
                      "Total Rent Collected", format_money(total),
                      f"rent_report_{start}_{end}")


def _expense_report(start, end, date_range):
    conn, cursor = get_cursor()
    cursor.execute(
        "SELECT exp_date, category, amount, notes FROM expenses "
        "WHERE exp_date BETWEEN %s AND %s ORDER BY exp_date",
        (start, end),
    )
    data = cursor.fetchall()
    columns = ["Date", "Category", "Amount", "Notes"]
    rows = [[format_date(d["exp_date"]), d["category"],
             format_money(d["amount"]), d["notes"] or "-"] for d in data]
    total = sum(float(d["amount"]) for d in data)
    _download_buttons("Expenses Report", date_range, columns, rows,
                      "Total Expenses", format_money(total),
                      f"expenses_report_{start}_{end}")


def _guest_report(start, end, date_range):
    conn, cursor = get_cursor()
    cursor.execute(
        "SELECT name, room_no, start_date, leaving_date, total_rent, advance_given "
        "FROM guests WHERE start_date BETWEEN %s AND %s ORDER BY start_date",
        (start, end),
    )
    data = cursor.fetchall()
    columns = ["Guest", "Room", "From", "To", "Total Rent"]
    rows = [[d["name"], d["room_no"], format_date(d["start_date"]),
             format_date(d["leaving_date"]), format_money(d["total_rent"])]
            for d in data]
    total = sum(float(d["total_rent"]) for d in data)
    _download_buttons("Temp Guest Income Report", date_range, columns, rows,
                      "Total Guest Income", format_money(total),
                      f"guest_report_{start}_{end}")


def _comprehensive_report(start, end, date_range):
    """Nets income vs expenses for the period with profit at the bottom."""
    conn, cursor = get_cursor()

    cursor.execute("SELECT COALESCE(SUM(amount_received),0) AS t FROM rent_history "
                   "WHERE txn_date BETWEEN %s AND %s", (start, end))
    rent_income = float(cursor.fetchone()["t"])

    cursor.execute("SELECT COALESCE(SUM(total_rent),0) AS t FROM guests "
                   "WHERE start_date BETWEEN %s AND %s", (start, end))
    guest_income = float(cursor.fetchone()["t"])

    cursor.execute("SELECT COALESCE(SUM(amount),0) AS t FROM expenses "
                   "WHERE exp_date BETWEEN %s AND %s", (start, end))
    expenses = float(cursor.fetchone()["t"])

    total_income = rent_income + guest_income
    profit = total_income - expenses

    columns = ["Item", "Amount"]
    rows = [
        ["Rent Income (permanent)", format_money(rent_income)],
        ["Guest Income (temp)", format_money(guest_income)],
        ["Total Income", format_money(total_income)],
        ["Total Expenses", format_money(expenses)],
    ]
    _download_buttons("Comprehensive Report", date_range, columns, rows,
                      "Net Profit", format_money(profit),
                      f"comprehensive_report_{start}_{end}")