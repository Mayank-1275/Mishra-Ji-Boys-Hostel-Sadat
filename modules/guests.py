import json

import streamlit as st
import pandas as pd

from utils.database import get_cursor
from utils.images import compress_image, decode_image
from utils.helpers import today_ist, format_money, format_date
from utils.pdf import guest_receipt_pdf, guest_profile_pdf, append_rules_pdf


def _fetch_rooms():
    conn, cursor = get_cursor()
    cursor.execute("SELECT room_no FROM rooms ORDER BY room_no")
    return [r["room_no"] for r in cursor.fetchall()]


def _valid_mobile(number):
    return number.isdigit() and len(number) == 10


def _section(title):
    st.markdown(
        f"<div style='font-size:1.05rem;font-weight:700;color:#0f766e;"
        f"margin:12px 0 6px 0;border-left:3px solid #0d9488;padding-left:8px;'>"
        f"{title}</div>",
        unsafe_allow_html=True,
    )


def _image_input(label, key_prefix):
    """
    Small Upload/Camera toggle; only the chosen input appears.
    Returns whichever file is provided (or None).
    """
    st.markdown(f"<div style='font-weight:700;margin:8px 0 2px 0;'>{label}</div>",
                unsafe_allow_html=True)
    mode = st.radio(
        f"{label} input mode",
        ["Upload", "Camera"],
        horizontal=True,
        key=f"{key_prefix}_mode",
        label_visibility="collapsed",
    )
    if mode == "Upload":
        return st.file_uploader(
            "Choose an image",
            type=["jpg", "jpeg", "png"],
            key=f"{key_prefix}_upload",
            label_visibility="collapsed",
        )
    else:
        return st.camera_input(
            "Take a photo",
            key=f"{key_prefix}_camera",
            label_visibility="collapsed",
        )


def guests_screen():
    st.markdown(
        "<h1 style='margin-bottom:0;'>Temp Guests</h1>"
        "<div style='color:#64748b;font-size:0.9rem;margin-bottom:0.6rem;'>"
        "Short-stay guests · Do not count toward the 3-member limit</div>",
        unsafe_allow_html=True,
    )

    tab_add, tab_active = st.tabs(["➕ Add Guest", "📋 Active Guests"])

    with tab_add:
        _add_guest_form()

    with tab_active:
        _active_guests()


def _add_guest_form():
    rooms = _fetch_rooms()

    # ---- Details (inside a form) ----
    with st.form("add_guest_form"):
        _section("👤 Guest details")
        name = st.text_input("Full Name *", placeholder="Guest's full name")
        whatsapp = st.text_input("WhatsApp / Mobile (10 digits)",
                                 placeholder="10-digit number")
        purpose = st.text_input("Purpose of stay",
                                placeholder="e.g. Wedding visit, exam, work")

        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start date", value=today_ist())
        with col2:
            leaving_date = st.date_input("Leaving date", value=today_ist())

        col3, col4 = st.columns(2)
        with col3:
            total_rent = st.number_input("Total rent for whole stay (₹)",
                                         min_value=0.0, step=100.0, value=0.0)
        with col4:
            advance = st.number_input("Advance given (₹)",
                                      min_value=0.0, step=100.0, value=0.0)

        room_no = st.selectbox("Room number", rooms)

        st.caption("Fill photos below (optional), then press Save Guest.")
        # Placeholder submit inside form (disabled) — real Save is below.
        st.form_submit_button("Continue", use_container_width=True,
                              disabled=True, help="Add photos below, then Save")

    # ---- Photos & ID (OUTSIDE the form, so the toggle switches live) ----
    _section("📷 Photos & ID (optional)")
    photo_file = _image_input("Guest Photo", "guest_photo")
    id_front_file = _image_input("ID Front", "guest_id_front")
    id_back_file = _image_input("ID Back", "guest_id_back")

    st.write("")
    submitted = st.button("💾 Save Guest", use_container_width=True,
                          key="save_guest_btn")

    if submitted:
        # Validation.
        errors = []
        if not name.strip():
            errors.append("Full Name is required.")
        if whatsapp and not _valid_mobile(whatsapp):
            errors.append("Mobile must be exactly 10 digits.")
        if leaving_date < start_date:
            errors.append("Leaving date cannot be before the start date.")
        if errors:
            for e in errors:
                st.error(e)
            return

        conn = None
        try:
            conn, cursor = get_cursor()
            with st.spinner("Saving guest..."):
                photo = compress_image(photo_file)
                id_front = compress_image(id_front_file)
                id_back = compress_image(id_back_file)

                cursor.execute(
                    """
                    INSERT INTO guests
                        (name, whatsapp, purpose, start_date, leaving_date,
                         total_rent, advance_given, room_no,
                         photo, id_front, id_back, status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active')
                    """,
                    (name.strip(), whatsapp, purpose.strip(), start_date, leaving_date,
                     total_rent, advance, room_no, photo, id_front, id_back),
                )
                guest_id = cursor.lastrowid

                cursor.execute(
                    "INSERT INTO audit_log (actor, action, entity, entity_id, details_json) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (st.session_state.get("username", "unknown"),
                     "add_guest", "guests", guest_id,
                     json.dumps({"name": name.strip(), "room": room_no})),
                )
                conn.commit()

            st.success(f"Guest '{name.strip()}' saved. 🎉")
            st.toast("Guest added.")

            # Build a guest profile card PDF (with photos) + rules page.
            guest_data = {
                "name": name.strip(),
                "whatsapp": whatsapp,
                "purpose": purpose.strip(),
                "room_no": room_no,
                "start_date": format_date(start_date),
                "leaving_date": format_date(leaving_date),
                "total_rent": format_money(total_rent),
                "advance": format_money(advance),
                "photo": photo,
                "id_front": id_front,
                "id_back": id_back,
            }
            profile_bytes = guest_profile_pdf(guest_data)
            st.session_state["guest_add_pdf"] = append_rules_pdf(profile_bytes)
            safe_name = name.strip().replace(" ", "_")
            st.session_state["guest_add_pdf_name"] = (
                f"{safe_name}_{start_date}_{room_no}_{leaving_date}.pdf"
            )
        except ValueError as ve:
            st.error(str(ve))
        except Exception:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            st.error("Could not save the guest. Please try again.")

    # Offer the guest profile card PDF after a successful add.
    if st.session_state.get("guest_add_pdf"):
        st.download_button(
            "📄 Download Guest Profile Card PDF",
            data=st.session_state["guest_add_pdf"],
            file_name=st.session_state.get("guest_add_pdf_name", "guest.pdf"),
            mime="application/pdf",
            use_container_width=True,
        )


def _active_guests():
    conn, cursor = get_cursor()
    cursor.execute(
        "SELECT * FROM guests WHERE status = 'active' "
        "ORDER BY leaving_date ASC, id DESC"
    )
    guests = cursor.fetchall()

    if not guests:
        st.info("No active guests right now.")
        return

    # Highlight anyone leaving today.
    today = today_ist()
    leaving_today = [g for g in guests if g["leaving_date"] == today]
    if leaving_today:
        names = ", ".join(g["name"] for g in leaving_today)
        st.markdown(
            f"<div style='background:#fffbeb;border:1px solid #f59e0b;"
            f"border-left:5px solid #f59e0b;border-radius:12px;padding:10px 14px;"
            f"margin-bottom:10px;color:#b45309;font-weight:600;'>"
            f"🧳 Leaving today: {names}</div>",
            unsafe_allow_html=True,
        )

    # Summary table.
    table = [
        {"ID": g["id"], "Name": g["name"], "Room": g["room_no"],
         "From": format_date(g["start_date"]), "To": format_date(g["leaving_date"]),
         "Total": format_money(g["total_rent"]),
         "Advance": format_money(g["advance_given"])}
        for g in guests
    ]
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("🚪 Exit a guest")

    label_map = {f"{g['name']} (#{g['id']}) — Room {g['room_no']}": g for g in guests}
    chosen = st.selectbox("Select guest to exit", list(label_map.keys()))
    guest = label_map[chosen]

    balance = float(guest["total_rent"]) - float(guest["advance_given"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Total rent", format_money(guest["total_rent"]))
    c2.metric("Advance given", format_money(guest["advance_given"]))
    if balance > 0:
        c3.metric("Balance to collect", format_money(balance))
    elif balance < 0:
        c3.metric("To refund", format_money(abs(balance)))
    else:
        c3.metric("Balance", "Settled")

    if st.button("Exit guest & mark inactive", use_container_width=True):
        _exit_guest(guest, balance)

    # Show receipt if just generated.
    if st.session_state.get("guest_receipt_pdf"):
        st.download_button(
            "📄 Download Guest Receipt",
            data=st.session_state["guest_receipt_pdf"],
            file_name=st.session_state.get("guest_receipt_name", "guest_receipt.pdf"),
            mime="application/pdf",
            use_container_width=True,
        )


def _exit_guest(guest, balance):
    conn = None
    try:
        conn, cursor = get_cursor()
        cursor.execute(
            "UPDATE guests SET status = 'inactive' WHERE id = %s",
            (guest["id"],),
        )
        cursor.execute(
            "INSERT INTO audit_log (actor, action, entity, entity_id, details_json) "
            "VALUES (%s,%s,%s,%s,%s)",
            (st.session_state.get("username", "unknown"),
             "exit_guest", "guests", guest["id"],
             json.dumps({"name": guest["name"], "balance": balance})),
        )
        conn.commit()

        if balance > 0:
            balance_text = f"Rs. {balance:,.0f} collected at exit"
        elif balance < 0:
            balance_text = f"Rs. {abs(balance):,.0f} refunded"
        else:
            balance_text = "Fully settled"

        receipt = guest_receipt_pdf({
            "receipt_no": guest["id"],
            "date": format_date(today_ist()),
            "guest_name": guest["name"],
            "purpose": guest["purpose"],
            "room_no": guest["room_no"],
            "stay_period": f"{format_date(guest['start_date'])} to "
                           f"{format_date(guest['leaving_date'])}",
            "total_rent": format_money(guest["total_rent"]),
            "advance": format_money(guest["advance_given"]),
            "balance": balance_text,
        })
        st.session_state["guest_receipt_pdf"] = receipt
        st.session_state["guest_receipt_name"] = f"{guest['name']}_receipt.pdf"

        st.success(f"Guest '{guest['name']}' exited and marked inactive.")
        st.toast("Guest exited.")
        st.rerun()
    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        st.error("Could not exit the guest. Please try again.")