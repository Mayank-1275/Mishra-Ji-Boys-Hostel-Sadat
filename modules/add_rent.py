import json
import os
from datetime import date

import streamlit as st

from utils.database import get_cursor
from utils.helpers import (today_ist, format_money, format_date,
                           build_reminder_message, whatsapp_link)
from utils.pdf import rent_receipt_pdf

HOSTEL_NAME = st.secrets.get("hostel", {}).get("name", "My Hostel")


def _fetch_rooms_with_occupants():
    """Return room numbers that currently have active occupants."""
    conn, cursor = get_cursor()
    cursor.execute(
        """
        SELECT DISTINCT room_no FROM occupancy
        WHERE is_active = 1 ORDER BY room_no
        """
    )
    return [r["room_no"] for r in cursor.fetchall()]


def _fetch_occupants(room_no):
    """Active occupants of a room with details needed for rent math."""
    conn, cursor = get_cursor()
    cursor.execute(
        """
        SELECT o.id AS occupancy_id, o.member_id, o.bed, o.start_date,
               o.daily_rent, m.name, m.whatsapp
        FROM occupancy o
        JOIN members m ON m.id = o.member_id
        WHERE o.room_no = %s AND o.is_active = 1
        ORDER BY o.bed
        """,
        (room_no,),
    )
    return cursor.fetchall()


def _paid_days_so_far(occupancy_id):
    """Total days already paid for this occupancy (sum of rent_history.paid_days)."""
    conn, cursor = get_cursor()
    cursor.execute(
        "SELECT COALESCE(SUM(paid_days), 0) AS total FROM rent_history "
        "WHERE occupancy_id = %s",
        (occupancy_id,),
    )
    row = cursor.fetchone()
    return float(row["total"]) if row else 0.0


def _compute_balance(occupant):
    """
    Work out the day-based balance for one occupant.
    Returns a dict with elapsed_days, paid_days, unpaid_days, due_amount.
    Counting rule: start_date up to AND INCLUDING today.
    """
    start = occupant["start_date"]
    daily = float(occupant["daily_rent"])

    # Days elapsed, inclusive of today.
    elapsed_days = (today_ist() - start).days + 1
    if elapsed_days < 0:
        elapsed_days = 0

    paid_days = _paid_days_so_far(occupant["occupancy_id"])
    unpaid_days = elapsed_days - paid_days  # can be negative if in advance/credit
    due_amount = unpaid_days * daily

    return {
        "elapsed_days": elapsed_days,
        "paid_days": paid_days,
        "unpaid_days": unpaid_days,
        "due_amount": due_amount,
        "daily": daily,
    }


def _status_card(bal):
    """Show a color-coded dues/credit status card."""
    if bal["unpaid_days"] > 0:
        bg, border, txt = "#fef2f2", "#ef4444", "#b91c1c"
        heading = f"Unpaid: {bal['unpaid_days']:.0f} day(s)"
        sub = f"Dues: {format_money(bal['due_amount'])}"
    elif bal["unpaid_days"] < 0:
        credit_days = abs(bal["unpaid_days"])
        bg, border, txt = "#ecfdf5", "#10b981", "#047857"
        heading = f"In advance by {credit_days:.0f} day(s)"
        sub = f"{format_money(credit_days * bal['daily'])} credit · No dues"
    else:
        bg, border, txt = "#ecfdf5", "#10b981", "#047857"
        heading = "All paid up 🎉"
        sub = "No dues"

    st.markdown(
        f"<div style='background:{bg};border:1px solid {border};"
        f"border-left:5px solid {border};border-radius:12px;padding:14px 16px;'>"
        f"<div style='font-weight:800;font-size:1.1rem;color:{txt};'>{heading}</div>"
        f"<div style='color:{txt};font-weight:600;'>{sub}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def add_rent_screen():
    st.markdown(
        "<h1 style='margin-bottom:0;'>Add Rent</h1>"
        "<div style='color:#64748b;font-size:0.9rem;margin-bottom:0.6rem;'>"
        "Dues are calculated strictly by day (IST)</div>",
        unsafe_allow_html=True,
    )

    rooms = _fetch_rooms_with_occupants()
    if not rooms:
        st.info("No occupied rooms yet. Assign members to rooms first.")
        return

    col_r, col_o = st.columns(2)
    with col_r:
        room_no = st.selectbox("Select room", rooms)
    occupants = _fetch_occupants(room_no)
    if not occupants:
        st.info("No active occupants in this room.")
        return

    labels = {f"Bed {o['bed']} — {o['name']}": o for o in occupants}
    with col_o:
        chosen = st.selectbox("Select occupant", list(labels.keys()))
    occupant = labels[chosen]

    # ---- Compute and show the balance ----
    bal = _compute_balance(occupant)

    st.write("")
    c1, c2, c3 = st.columns(3)
    c1.metric("Daily rate", f"{format_money(bal['daily'])}/day")
    c2.metric("Days stayed", f"{bal['elapsed_days']}")
    c3.metric("Days paid", f"{bal['paid_days']:.0f}")

    st.write("")
    _status_card(bal)

    # ---- WhatsApp reminder (month-based) + payment QR ----
    if bal["unpaid_days"] > 0 and occupant["whatsapp"]:
        upi_id = st.secrets.get("payment", {}).get("upi_id", "")
        payee_name = st.secrets.get("payment", {}).get("payee_name", HOSTEL_NAME)

        message = build_reminder_message(
            member_name=occupant["name"],
            unpaid_days=bal["unpaid_days"],
            daily_rent=bal["daily"],
            hostel_name=HOSTEL_NAME,
            upi_id=upi_id,
            payee_name=payee_name,
        )
        wa = whatsapp_link(occupant["whatsapp"], message)

        st.write("")
        col_msg, col_qr = st.columns([2, 1])
        with col_msg:
            if wa:
                st.link_button("📱 Send WhatsApp reminder", wa,
                               use_container_width=True)
            st.caption("Message includes pending months, amount, and your UPI ID.")
        with col_qr:
            qr_path = os.path.join("assets", "payment_qr.png")
            if os.path.exists(qr_path):
                st.image(qr_path, caption="Payment QR", width=140)
            else:
                st.caption("No QR image found (add assets/payment_qr.png).")

    st.divider()

    # ---- Payment form ----
    st.subheader("💵 Record a payment")
    with st.form("add_rent_form"):
        amount = st.number_input("Amount received (₹)", min_value=0.0, step=50.0,
                                 value=0.0)
        receiver = st.text_input("Receiver name",
                                 value=st.session_state.get("username", ""))
        secret_code = st.text_input("Secret code", type="password",
                                    help="Required to register a payment.")
        submitted = st.form_submit_button("✅ Register payment",
                                          use_container_width=True)

    if submitted:
        _register_payment(occupant, room_no, amount, receiver, secret_code, bal)

    # ---- Receipt download (after a successful payment) ----
    if st.session_state.get("last_receipt_pdf"):
        st.download_button(
            "📄 Download Rent Receipt",
            data=st.session_state["last_receipt_pdf"],
            file_name=st.session_state.get("last_receipt_name", "receipt.pdf"),
            mime="application/pdf",
            use_container_width=True,
        )

    # ---- Manage the most recent payment for this occupant ----
    _manage_recent_payment(occupant)


def _register_payment(occupant, room_no, amount, receiver, secret_code, bal):
    # 1. Validate.
    if amount <= 0:
        st.error("Enter an amount greater than zero.")
        return
    if not receiver.strip():
        st.error("Receiver name is required.")
        return
    if secret_code != st.secrets["auth"]["rent_secret_code"]:
        st.error("Incorrect secret code. Payment not registered.")
        return

    daily = float(occupant["daily_rent"])
    paid_days = round(amount / daily, 2) if daily > 0 else 0.0

    conn = None
    try:
        conn, cursor = get_cursor()
        with st.spinner("Registering payment..."):
            cursor.execute(
                """
                INSERT INTO rent_history
                    (member_id, occupancy_id, amount_received, receiver_name,
                     paid_days, txn_date)
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (occupant["member_id"], occupant["occupancy_id"], amount,
                 receiver.strip(), paid_days, today_ist()),
            )
            rent_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO audit_log (actor, action, entity, entity_id, details_json) "
                "VALUES (%s,%s,%s,%s,%s)",
                (
                    st.session_state.get("username", "unknown"),
                    "add_rent", "rent_history", rent_id,
                    json.dumps({"member": occupant["name"], "amount": amount,
                                "paid_days": paid_days}),
                ),
            )
            conn.commit()

        # New balance after this payment.
        new_unpaid = bal["unpaid_days"] - paid_days
        if new_unpaid > 0:
            balance_text = f"Dues: {format_money(new_unpaid * daily)} ({new_unpaid:.0f} days)"
        elif new_unpaid < 0:
            balance_text = f"Advance: {format_money(abs(new_unpaid) * daily)} ({abs(new_unpaid):.0f} days)"
        else:
            balance_text = "Fully paid"

        # Build receipt PDF.
        receipt = rent_receipt_pdf({
            "receipt_no": rent_id,
            "date": format_date(today_ist()),
            "member_name": occupant["name"],
            "room_bed": f"Room {room_no} / Bed {occupant['bed']}",
            "amount": format_money(amount),
            "daily_rate": f"{format_money(daily)}/day",
            "paid_days": f"{paid_days:.2f}",
            "receiver": receiver.strip(),
            "balance": balance_text,
        })
        st.session_state["last_receipt_pdf"] = receipt
        st.session_state["last_receipt_name"] = f"{occupant['name']}_receipt_{rent_id}.pdf"

        st.success(f"Payment of {format_money(amount)} registered "
                   f"({paid_days:.2f} days). 🎉")
        st.toast("Rent recorded.")
        st.rerun()

    except Exception as e:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        st.error("Could not register the payment. Please try again.")


def _recent_payment(occupancy_id):
    """Fetch the single most recent rent payment for this occupancy."""
    conn, cursor = get_cursor()
    cursor.execute(
        "SELECT id, amount_received, paid_days, receiver_name, txn_date "
        "FROM rent_history WHERE occupancy_id = %s "
        "ORDER BY id DESC LIMIT 1",
        (occupancy_id,),
    )
    return cursor.fetchone()


def _manage_recent_payment(occupant):
    """Allow editing or deleting the most recent payment (secret-code protected)."""
    recent = _recent_payment(occupant["occupancy_id"])
    if not recent:
        return

    st.divider()
    with st.expander("✏️ Edit / Delete the most recent payment"):
        st.write(
            f"Most recent: {format_money(recent['amount_received'])} "
            f"on {format_date(recent['txn_date'])} "
            f"({float(recent['paid_days']):.2f} days, by {recent['receiver_name']})"
        )

        daily = float(occupant["daily_rent"])

        # ---- Edit ----
        st.markdown("**Edit amount**")
        new_amount = st.number_input(
            "New amount (₹)", min_value=0.0, step=50.0,
            value=float(recent["amount_received"]), key="edit_amount",
        )
        edit_code = st.text_input("Secret code (to edit)", type="password",
                                  key="edit_code")
        if st.button("Save edit", key="save_edit", use_container_width=True):
            if edit_code != st.secrets["auth"]["rent_secret_code"]:
                st.error("Incorrect secret code. Edit not saved.")
            elif new_amount <= 0:
                st.error("Amount must be greater than zero.")
            else:
                _edit_recent(recent, new_amount, daily, occupant)

        st.markdown("---")

        # ---- Delete ----
        st.markdown("**Delete this payment**")
        del_code = st.text_input("Secret code (to delete)", type="password",
                                 key="del_code")
        if st.button("🗑️ Delete most recent payment", key="del_btn",
                     use_container_width=True):
            if del_code != st.secrets["auth"]["rent_secret_code"]:
                st.error("Incorrect secret code. Nothing deleted.")
            else:
                _delete_recent(recent, occupant)


def _edit_recent(recent, new_amount, daily, occupant):
    new_paid_days = round(new_amount / daily, 2) if daily > 0 else 0.0
    conn = None
    try:
        conn, cursor = get_cursor()
        cursor.execute(
            "UPDATE rent_history SET amount_received=%s, paid_days=%s WHERE id=%s",
            (new_amount, new_paid_days, recent["id"]),
        )
        cursor.execute(
            "INSERT INTO audit_log (actor, action, entity, entity_id, details_json) "
            "VALUES (%s,%s,%s,%s,%s)",
            (st.session_state.get("username", "unknown"),
             "edit_rent", "rent_history", recent["id"],
             json.dumps({"old_amount": float(recent["amount_received"]),
                         "new_amount": new_amount})),
        )
        conn.commit()
        st.success(f"Payment updated to {format_money(new_amount)} "
                   f"({new_paid_days:.2f} days).")
        st.toast("Payment edited.")
        st.rerun()
    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        st.error("Could not edit the payment. Please try again.")


def _delete_recent(recent, occupant):
    conn = None
    try:
        conn, cursor = get_cursor()
        cursor.execute("DELETE FROM rent_history WHERE id=%s", (recent["id"],))
        cursor.execute(
            "INSERT INTO audit_log (actor, action, entity, entity_id, details_json) "
            "VALUES (%s,%s,%s,%s,%s)",
            (st.session_state.get("username", "unknown"),
             "delete_rent", "rent_history", recent["id"],
             json.dumps({"amount": float(recent["amount_received"]),
                         "member": occupant["name"]})),
        )
        conn.commit()
        st.success("Most recent payment deleted.")
        st.toast("Payment removed.")
        st.rerun()
    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        st.error("Could not delete the payment. Please try again.")