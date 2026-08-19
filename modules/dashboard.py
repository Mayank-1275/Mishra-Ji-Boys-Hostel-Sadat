import urllib.parse

import streamlit as st
import pandas as pd

from utils.database import get_cursor
from utils.helpers import (today_ist, format_money, build_reminder_message, whatsapp_link)

HOSTEL_NAME = st.secrets.get("hostel", {}).get("name", "My Hostel")

ALL_ROOMS = ["01", "02", "03", "04", "05", "06", "11", "12", "13", "14", "15",
             "21", "22", "23", "24", "31", "32", "33", "34"]
TOTAL_BEDS = len(ALL_ROOMS) * 3  # 19 rooms x 3 beds = 57


def _active_members_count():
    conn, cursor = get_cursor()
    cursor.execute("SELECT COUNT(*) AS c FROM members WHERE is_active = 1")
    return cursor.fetchone()["c"]


def _total_members_count():
    conn, cursor = get_cursor()
    cursor.execute("SELECT COUNT(*) AS c FROM members")
    return cursor.fetchone()["c"]


def _active_occupancies():
    """All active occupancies with the info needed for dues math."""
    conn, cursor = get_cursor()
    cursor.execute(
        """
        SELECT o.id AS occupancy_id, o.member_id, o.room_no, o.start_date,
               o.daily_rent, m.name, m.whatsapp
        FROM occupancy o
        JOIN members m ON m.id = o.member_id
        WHERE o.is_active = 1
        """
    )
    return cursor.fetchall()


def _paid_days_map():
    """member_id/occupancy_id -> total paid days."""
    conn, cursor = get_cursor()
    cursor.execute(
        "SELECT occupancy_id, COALESCE(SUM(paid_days),0) AS t "
        "FROM rent_history GROUP BY occupancy_id"
    )
    return {r["occupancy_id"]: float(r["t"]) for r in cursor.fetchall()}


def _total_rent_income():
    conn, cursor = get_cursor()
    cursor.execute("SELECT COALESCE(SUM(amount_received),0) AS t FROM rent_history")
    return float(cursor.fetchone()["t"])


def _total_guest_income():
    """Guest income = advance + any balance settled. Use total_rent as income."""
    conn, cursor = get_cursor()
    cursor.execute("SELECT COALESCE(SUM(total_rent),0) AS t FROM guests")
    return float(cursor.fetchone()["t"])


def _total_expenses():
    conn, cursor = get_cursor()
    cursor.execute("SELECT COALESCE(SUM(amount),0) AS t FROM expenses")
    return float(cursor.fetchone()["t"])


def _month_snapshot():
    """Income, expenses, profit for the current month."""
    first = today_ist().replace(day=1)
    conn, cursor = get_cursor()
    cursor.execute(
        "SELECT COALESCE(SUM(amount_received),0) AS t FROM rent_history "
        "WHERE txn_date >= %s", (first,))
    income = float(cursor.fetchone()["t"])
    cursor.execute(
        "SELECT COALESCE(SUM(amount),0) AS t FROM expenses WHERE exp_date >= %s",
        (first,))
    exp = float(cursor.fetchone()["t"])
    return income, exp, income - exp


def _render_room_map(occupancies):
    """Responsive HTML grid of rooms (auto-wraps on any screen)."""
    room_counts = {r: 0 for r in ALL_ROOMS}
    for o in occupancies:
        if o["room_no"] in room_counts:
            room_counts[o["room_no"]] += 1

    tiles = ""
    for room in ALL_ROOMS:
        count = room_counts[room]
        if count == 0:
            bg, border, txt, label = "#ecfdf5", "#10b981", "#047857", "Empty"
        elif count < 3:
            bg, border, txt, label = "#fffbeb", "#f59e0b", "#b45309", f"{count}/3"
        else:
            bg, border, txt, label = "#fef2f2", "#ef4444", "#b91c1c", "Full"
        tiles += (
            f"<div style='background:{bg};border:1px solid {border};"
            f"border-radius:12px;padding:8px 4px;text-align:center;'>"
            f"<div style='font-weight:800;font-size:1.05rem;color:{txt};'>{room}</div>"
            f"<div style='font-size:0.72rem;color:{txt};font-weight:600;'>{label}</div>"
            f"</div>"
        )

    html = (
        "<div style='display:grid;"
        "grid-template-columns:repeat(auto-fill,minmax(64px,1fr));"
        "gap:8px;margin-top:6px;'>" + tiles + "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def dashboard_screen():
    today = today_ist()

    # ---- Title with date ----
    st.markdown(
        f"<h1 style='margin-bottom:0;'>Dashboard</h1>"
        f"<div style='color:#64748b;font-size:0.9rem;margin-bottom:0.6rem;'>"
        f"Overview as of {today.strftime('%d %b %Y')}</div>",
        unsafe_allow_html=True,
    )

    # ---- Gather data ----
    occupancies = _active_occupancies()
    paid_map = _paid_days_map()

    # Compute per-member dues.
    overdue_rows = []
    total_pending = 0.0
    aging = {"0-15": 0, "16-30": 0, "31+": 0}
    occupied_rooms = set()

    for o in occupancies:
        occupied_rooms.add(o["room_no"])
        elapsed = (today - o["start_date"]).days + 1
        paid = paid_map.get(o["occupancy_id"], 0.0)
        unpaid_days = elapsed - paid
        if unpaid_days > 0:
            due = unpaid_days * float(o["daily_rent"])
            total_pending += due
            overdue_rows.append({
                "name": o["name"], "room": o["room_no"],
                "unpaid_days": unpaid_days, "due": due,
                "whatsapp": o["whatsapp"],
                "daily_rent": float(o["daily_rent"]),
            })
            if unpaid_days <= 15:
                aging["0-15"] += 1
            elif unpaid_days <= 30:
                aging["16-30"] += 1
            else:
                aging["31+"] += 1

    active_members = _active_members_count()
    total_members = _total_members_count()
    rent_income = _total_rent_income()
    guest_income = _total_guest_income()
    total_income = rent_income + guest_income
    total_expenses = _total_expenses()
    net_profit = total_income - total_expenses

    vacant_rooms = len(ALL_ROOMS) - len(occupied_rooms)
    occupied_beds = len(occupancies)
    occupancy_rate = (occupied_beds / TOTAL_BEDS * 100) if TOTAL_BEDS else 0

    # ---- Row 1: core metrics ----
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Members", active_members)
    c2.metric("Vacant Rooms", vacant_rooms)
    c3.metric("Total Income", format_money(total_income),
              help=f"Permanent: {format_money(rent_income)} · "
                   f"Guests: {format_money(guest_income)}")
    c4.metric("Total Pending", format_money(total_pending))

    # ---- Row 2: more metrics ----
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Total Members (all-time)", total_members)
    c6.metric("Net Profit", format_money(net_profit),
              help=f"Income {format_money(total_income)} − "
                   f"Expenses {format_money(total_expenses)}")
    c7.metric("Occupancy Rate", f"{occupancy_rate:.0f}%",
              help=f"{occupied_beds} of {TOTAL_BEDS} beds")
    c8.metric("Overdue Members", len(overdue_rows))

    st.divider()

    # ---- Action alerts ----
    st.subheader("🔔 Action Alerts")
    conn, cursor = get_cursor()
    cursor.execute("SELECT COUNT(*) AS c FROM guests "
                   "WHERE status='active' AND leaving_date = %s", (today,))
    leaving_today = cursor.fetchone()["c"]

    alerts = []
    if leaving_today:
        alerts.append(("🧳", f"{leaving_today} guest(s) leaving today.", "#f59e0b"))
    if aging["31+"]:
        alerts.append(("⚠️", f"{aging['31+']} member(s) overdue by 31+ days.", "#ef4444"))
    if vacant_rooms:
        alerts.append(("🚪", f"{vacant_rooms} room(s) have vacancies.", "#0d9488"))
    if not alerts:
        alerts.append(("✅", "All clear — nothing needs attention right now.", "#10b981"))

    for icon, text, color in alerts:
        st.markdown(
            f"<div style='background:#ffffff;border:1px solid #e2e8f0;"
            f"border-left:4px solid {color};border-radius:10px;padding:10px 14px;"
            f"margin-bottom:8px;font-weight:500;'>{icon}&nbsp; {text}</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ---- Aging buckets + This-month snapshot ----
    colA, colB = st.columns(2)
    with colA:
        st.subheader("📊 Pending Dues — Aging")
        aging_df = pd.DataFrame(
            [{"Bucket (days)": k, "Members": v} for k, v in aging.items()]
        )
        st.dataframe(aging_df, use_container_width=True, hide_index=True)

    with colB:
        st.subheader("📅 This Month")
        m_income, m_exp, m_profit = _month_snapshot()
        profit_color = "#047857" if m_profit >= 0 else "#b91c1c"
        st.markdown(
            f"<div style='background:#ffffff;border:1px solid #e2e8f0;"
            f"border-radius:14px;padding:16px 18px;'>"
            f"<div style='display:flex;justify-content:space-between;margin-bottom:6px;'>"
            f"<span style='color:#64748b;'>Income</span>"
            f"<span style='font-weight:700;'>{format_money(m_income)}</span></div>"
            f"<div style='display:flex;justify-content:space-between;margin-bottom:6px;'>"
            f"<span style='color:#64748b;'>Expenses</span>"
            f"<span style='font-weight:700;'>{format_money(m_exp)}</span></div>"
            f"<hr style='border:none;border-top:1px solid #e2e8f0;margin:8px 0;'>"
            f"<div style='display:flex;justify-content:space-between;'>"
            f"<span style='font-weight:700;'>Profit</span>"
            f"<span style='font-weight:800;color:{profit_color};'>"
            f"{format_money(m_profit)}</span></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ---- Room heatmap (bed occupancy) ----
    st.subheader("🗺️ Room Occupancy Map")
    _render_room_map(occupancies)
    st.caption("🟢 Empty   ·   🟡 Partly filled   ·   🔴 Full")

    st.divider()

    # ---- Bulk WhatsApp reminders (only 30+ days pending) ----
    upi_id = st.secrets.get("payment", {}).get("upi_id", "")
    payee_name = st.secrets.get("payment", {}).get("payee_name", HOSTEL_NAME)

    reminder_rows = [r for r in overdue_rows if r["unpaid_days"] >= 30]

    with st.expander(f"📱 Bulk WhatsApp Reminders ({len(reminder_rows)} members, 30+ days)"):
        if not reminder_rows:
            st.info("No members are 30+ days overdue. 🎉")
        else:
            st.caption("Reminders are sent only to members pending by 30 days or more.")
            for r in sorted(reminder_rows, key=lambda x: x["due"], reverse=True):
                col1, col2 = st.columns([3, 1])
                col1.write(f"**{r['name']}** (Room {r['room']}) — "
                           f"{r['unpaid_days']:.0f} days · {format_money(r['due'])}")
                message = build_reminder_message(
                    member_name=r["name"],
                    unpaid_days=r["unpaid_days"],
                    daily_rent=r["daily_rent"],
                    hostel_name=HOSTEL_NAME,
                    upi_id=upi_id,
                    payee_name=payee_name,
                )
                link = whatsapp_link(r["whatsapp"], message)
                if link:
                    col2.link_button("Remind", link)
                else:
                    col2.caption("No number")