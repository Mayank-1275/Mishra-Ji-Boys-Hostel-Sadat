import io
import csv

import streamlit as st
import pandas as pd

from utils.database import get_cursor
from utils.images import decode_image
from utils.helpers import today_ist, format_money, format_date
from utils.pdf import member_profile_pdf, append_rules_pdf
from modules.edit_member import edit_member_form


def _search_members(term, by):
    """Search members by name, mobile, or room number. Returns rows."""
    conn, cursor = get_cursor()

    if by == "Name":
        cursor.execute(
            "SELECT id, name, father_name, whatsapp FROM members "
            "WHERE name LIKE %s ORDER BY name",
            (f"%{term}%",),
        )
    elif by == "Mobile":
        cursor.execute(
            "SELECT id, name, father_name, whatsapp FROM members "
            "WHERE whatsapp LIKE %s OR father_mobile LIKE %s OR mother_mobile LIKE %s "
            "ORDER BY name",
            (f"%{term}%", f"%{term}%", f"%{term}%"),
        )
    else:  # Room number
        cursor.execute(
            """
            SELECT m.id, m.name, m.father_name, m.whatsapp
            FROM members m
            JOIN occupancy o ON o.member_id = m.id AND o.is_active = 1
            WHERE o.room_no = %s
            ORDER BY m.name
            """,
            (term,),
        )
    return cursor.fetchall()


def _member_full(member_id):
    """Fetch one member's full record."""
    conn, cursor = get_cursor()
    cursor.execute("SELECT * FROM members WHERE id = %s", (member_id,))
    return cursor.fetchone()


def _current_occupancy(member_id):
    """Active room/bed for a member, or None."""
    conn, cursor = get_cursor()
    cursor.execute(
        "SELECT room_no, bed, start_date, daily_rent FROM occupancy "
        "WHERE member_id = %s AND is_active = 1 LIMIT 1",
        (member_id,),
    )
    return cursor.fetchone()


def _rent_history(member_id):
    """All rent payments for a member, newest first."""
    conn, cursor = get_cursor()
    cursor.execute(
        "SELECT txn_date, amount_received, paid_days, receiver_name "
        "FROM rent_history WHERE member_id = %s ORDER BY txn_date DESC, id DESC",
        (member_id,),
    )
    return cursor.fetchall()


def _paid_days_total(member_id):
    conn, cursor = get_cursor()
    cursor.execute(
        "SELECT COALESCE(SUM(paid_days),0) AS t FROM rent_history WHERE member_id = %s",
        (member_id,),
    )
    return float(cursor.fetchone()["t"])


def _deposit_status(member_id):
    conn, cursor = get_cursor()
    cursor.execute(
        "SELECT COALESCE(SUM(deposit_amount),0) AS dep, "
        "COALESCE(SUM(refunded_amount),0) AS ref "
        "FROM deposits WHERE member_id = %s",
        (member_id,),
    )
    row = cursor.fetchone()
    return float(row["dep"]), float(row["ref"])


def _pill(text, color, bg):
    return (f"<span style='background:{bg};color:{color};padding:3px 10px;"
            f"border-radius:999px;font-weight:700;font-size:0.85rem;'>{text}</span>")


def search_member_screen():
    st.markdown(
        "<h1 style='margin-bottom:0;'>Search Member</h1>"
        "<div style='color:#64748b;font-size:0.9rem;margin-bottom:0.6rem;'>"
        "Find a member by name, mobile, or room</div>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1, 2])
    with col1:
        by = st.selectbox("Search by", ["Name", "Mobile", "Room number"])
    with col2:
        term = st.text_input(f"Enter {by.lower()}", placeholder="Type to search…")

    if not term.strip():
        st.info("Type something above to search.")
        return

    results = _search_members(term.strip(), by)
    if not results:
        st.warning("No members found.")
        return

    # Show results table.
    st.caption(f"{len(results)} result(s) found.")
    table = [
        {"ID": r["id"], "Name": r["name"],
         "Father's Name": r["father_name"], "Mobile": r["whatsapp"]}
        for r in results
    ]
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

    # Pick one member to view.
    label_map = {f"{r['name']} (#{r['id']})": r["id"] for r in results}
    chosen = st.selectbox("Select a member to view", list(label_map.keys()))
    member_id = label_map[chosen]

    st.divider()
    _show_member_profile(member_id)


def _show_member_profile(member_id):
    member = _member_full(member_id)
    if not member:
        st.error("Member not found.")
        return

    # ---- Edit mode toggle ----
    if st.session_state.get("editing_member_id") == member_id:
        edit_member_form(member)
        return  # show only the edit form while editing

    # Edit button (opens the edit form for this member).
    if st.button("✏️ Edit this member", key=f"edit_btn_{member_id}",
                 use_container_width=True):
        st.session_state["editing_member_id"] = member_id
        st.rerun()

    occ = _current_occupancy(member_id)
    is_active = member.get("is_active", 1) == 1

    # ---- Header row: photo + key info ----
    col_photo, col_info = st.columns([1, 3])
    with col_photo:
        img = decode_image(member.get("photo"))
        if img:
            st.image(img, use_container_width=True)
        else:
            st.markdown(
                "<div style='background:#f1f5f9;border:1px dashed #cbd5e1;"
                "border-radius:12px;height:110px;display:flex;align-items:center;"
                "justify-content:center;color:#94a3b8;font-size:0.8rem;'>No photo</div>",
                unsafe_allow_html=True,
            )

    with col_info:
        st.markdown(f"<div style='font-size:1.3rem;font-weight:800;'>"
                    f"{member['name']}</div>", unsafe_allow_html=True)
        if occ:
            st.markdown(
                _pill(f"Room {occ['room_no']} · Bed {occ['bed']}", "#047857", "#ecfdf5"),
                unsafe_allow_html=True,
            )
            st.caption(f"Since {format_date(occ['start_date'])} · "
                       f"{format_money(occ['daily_rent'])}/day")
        elif not is_active:
            st.markdown(_pill("Left / Inactive", "#b91c1c", "#fef2f2"),
                        unsafe_allow_html=True)
        else:
            st.markdown(_pill("Not in a room", "#b45309", "#fffbeb"),
                        unsafe_allow_html=True)

        # Unpaid days (force 0 if not active or not in a room).
        st.write("")
        if occ and is_active:
            elapsed = (today_ist() - occ["start_date"]).days + 1
            unpaid = elapsed - _paid_days_total(member_id)
            unpaid = max(unpaid, 0)
            if unpaid > 0:
                st.markdown(
                    _pill(f"Unpaid: {unpaid:.0f} days "
                          f"({format_money(unpaid * float(occ['daily_rent']))})",
                          "#b91c1c", "#fef2f2"),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(_pill("Unpaid Days: 0", "#047857", "#ecfdf5"),
                            unsafe_allow_html=True)
        else:
            st.markdown(_pill("Unpaid Days: 0", "#475569", "#f1f5f9"),
                        unsafe_allow_html=True)

    # ---- Details ----
    st.markdown("##### 📋 Details")
    d1, d2 = st.columns(2)
    with d1:
        st.write(f"**Date of Birth:** {format_date(member.get('dob'))}")
        st.write(f"**Father's Name:** {member.get('father_name') or '-'}")
        st.write(f"**Father's Mobile:** {member.get('father_mobile') or '-'}")
        st.write(f"**WhatsApp:** {member.get('whatsapp') or '-'}")
    with d2:
        st.write(f"**Mother's Name:** {member.get('mother_name') or '-'}")
        st.write(f"**Mother's Mobile:** {member.get('mother_mobile') or '-'}")
        st.write(f"**Address:** {member.get('address') or '-'}")

    # ---- Deposit status ----
    dep, ref = _deposit_status(member_id)
    if dep > 0:
        st.markdown("##### 💵 Security Deposit")
        st.write(f"Collected: {format_money(dep)} · Refunded: {format_money(ref)} · "
                 f"Held: {format_money(dep - ref)}")

    # ---- Other document images ----
    imgs = [
        ("Father's Pic", member.get("father_pic")),
        ("ID Front", member.get("id_front")),
        ("ID Back", member.get("id_back")),
    ]
    if any(b for _, b in imgs):
        st.markdown("##### 🖼️ Documents")
        dcols = st.columns(3)
        for (label, b64), c in zip(imgs, dcols):
            img = decode_image(b64)
            with c:
                if img:
                    st.image(img, caption=label, use_container_width=True)
                else:
                    st.caption(f"{label}: not provided")

    # ---- Rent history ----
    st.markdown("##### 🧾 Rent History")
    history = _rent_history(member_id)
    if not history:
        st.info("No rent payments recorded yet.")
    else:
        hist_table = [
            {"Date": format_date(h["txn_date"]),
             "Amount": format_money(h["amount_received"]),
             "Days Paid": f"{float(h['paid_days']):.2f}",
             "Received By": h["receiver_name"]}
            for h in history
        ]
        st.dataframe(pd.DataFrame(hist_table), use_container_width=True,
                     hide_index=True)

        # CSV export of the rent history.
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(
            csv_buffer, fieldnames=["Date", "Amount", "Days Paid", "Received By"])
        writer.writeheader()
        writer.writerows(hist_table)
        st.download_button(
            "⬇️ Export rent history (CSV)",
            data=csv_buffer.getvalue(),
            file_name=f"{member['name']}_rent_history.csv",
            mime="text/csv",
        )

    # ---- Regenerate profile PDF ----
    st.markdown("##### 📄 Profile Card")
    if st.button("📄 Regenerate ID PDF", use_container_width=True):
        pdf_bytes = append_rules_pdf(member_profile_pdf(member))
        st.download_button(
            "Download Profile Card PDF",
            data=pdf_bytes,
            file_name=f"{member['name']}_profile.pdf",
            mime="application/pdf",
            use_container_width=True,
        )