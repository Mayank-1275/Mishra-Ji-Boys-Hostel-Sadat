import json
from datetime import date

import streamlit as st

from utils.database import get_cursor
from utils.images import compress_image
from utils.pdf import member_profile_pdf, append_rules_pdf
from utils.helpers import today_ist


def _image_input(label, key_prefix):
    """Simple upload box (phone's Upload already offers camera + gallery)."""
    st.markdown(f"<div style='font-weight:700;margin:8px 0 2px 0;'>{label}</div>",
                unsafe_allow_html=True)
    return st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"],
                            key=f"{key_prefix}_up", label_visibility="collapsed")


def _valid_mobile(number):
    """True only if the number is exactly 10 digits."""
    return number.isdigit() and len(number) == 10


def _section(title):
    """A small styled section heading."""
    st.markdown(
        f"<div style='font-size:1.05rem;font-weight:700;color:#0f766e;"
        f"margin:14px 0 6px 0;border-left:3px solid #0d9488;padding-left:8px;'>"
        f"{title}</div>",
        unsafe_allow_html=True,
    )


def add_member_screen():
    st.markdown(
        "<h1 style='margin-bottom:0;'>Add Member</h1>"
        "<div style='color:#64748b;font-size:0.9rem;margin-bottom:0.6rem;'>"
        "Add a new permanent tenant</div>",
        unsafe_allow_html=True,
    )

    # ---- Details (widgets keep their values via keys) ----
    _section("👤 Personal details")
    name = st.text_input("Full Name *", placeholder="e.g. Ramesh Kumar", key="m_name")
    dob = st.date_input(
        "Date of Birth",
        value=date(2000, 1, 1),
        min_value=date(1950, 1, 1),
        max_value=today_ist(),
        key="m_dob",
    )
    address = st.text_area("Address", placeholder="Village / City, District",
                           key="m_address")

    _section("👨‍👩‍👦 Family details")
    col1, col2 = st.columns(2)
    with col1:
        father_name = st.text_input("Father's Name", key="m_father_name")
        father_mobile = st.text_input("Father's Mobile (10 digits)",
                                      key="m_father_mobile")
    with col2:
        mother_name = st.text_input("Mother's Name", key="m_mother_name")
        mother_mobile = st.text_input("Mother's Mobile (10 digits)",
                                      key="m_mother_mobile")

    whatsapp = st.text_input("WhatsApp Number (10 digits) *",
                             placeholder="10-digit number", key="m_whatsapp")

    _section("💵 Security deposit (optional)")
    deposit_amount = st.number_input(
        "Deposit collected (₹)", min_value=0.0, step=100.0, value=0.0,
        key="m_deposit"
    )

    _section("📷 Photos & ID")
    st.caption("Tap Upload — your phone will offer Camera or Gallery.")
    photo_file = _image_input("Member Photo", "photo")
    father_pic_file = _image_input("Father's Pic (optional)", "father_pic")
    id_front_file = _image_input("ID Front", "id_front")
    id_back_file = _image_input("ID Back", "id_back")

    allow_duplicate = st.checkbox("Add even if a similar member already exists",
                                  key="m_allow_dup")

    st.write("")
    submitted = st.button("💾 Save Member", use_container_width=True,
                          key="save_member_btn")

    # ---- Runs only after the Save button is clicked ----
    if submitted:
        # 1. Validate the inputs.
        errors = []
        if not name.strip():
            errors.append("Full Name is required.")
        if not _valid_mobile(whatsapp):
            errors.append("WhatsApp Number must be exactly 10 digits.")
        if father_mobile and not _valid_mobile(father_mobile):
            errors.append("Father's Mobile must be exactly 10 digits.")
        if mother_mobile and not _valid_mobile(mother_mobile):
            errors.append("Mother's Mobile must be exactly 10 digits.")

        if errors:
            for e in errors:
                st.error(e)
            return

        conn = None
        try:
            conn, cursor = get_cursor()

            # 2. Duplicate check (same name + WhatsApp).
            cursor.execute(
                "SELECT id FROM members WHERE name=%s AND whatsapp=%s AND is_active=1",
                (name.strip(), whatsapp),
            )
            existing = cursor.fetchall()  # drain all rows so nothing is left unread
            if existing and not allow_duplicate:
                st.warning(
                    "A member with the same name and WhatsApp number already exists. "
                    "Tick the 'Add even if a similar member exists' box and save again."
                )
                return

            with st.spinner("Compressing photos and saving..."):
                # 3. Compress each image (returns small Base64 text, or None).
                photo = compress_image(photo_file)
                father_pic = compress_image(father_pic_file)
                id_front = compress_image(id_front_file)
                id_back = compress_image(id_back_file)

                # 4. Insert the member (parameterized query - safe from injection).
                cursor.execute(
                    """
                    INSERT INTO members
                        (name, dob, address, father_name, father_mobile,
                         mother_name, mother_mobile, whatsapp,
                         photo, father_pic, id_front, id_back)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        name.strip(), dob, address.strip(),
                        father_name.strip(), father_mobile,
                        mother_name.strip(), mother_mobile, whatsapp,
                        photo, father_pic, id_front, id_back,
                    ),
                )
                member_id = cursor.lastrowid

                # 5. Optional security deposit.
                if deposit_amount and deposit_amount > 0:
                    cursor.execute(
                        "INSERT INTO deposits (member_id, deposit_amount, deposit_date) "
                        "VALUES (%s,%s,%s)",
                        (member_id, deposit_amount, today_ist()),
                    )

                # 6. Write an audit log entry.
                cursor.execute(
                    "INSERT INTO audit_log (actor, action, entity, entity_id, details_json) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (
                        st.session_state.get("username", "unknown"),
                        "add_member", "members", member_id,
                        json.dumps({"name": name.strip()}),
                    ),
                )

                conn.commit()

            # 7. Build the PDF profile card and keep it ready to download.
            member_data = {
                "name": name.strip(),
                "dob": dob,
                "address": address.strip(),
                "father_name": father_name.strip(),
                "father_mobile": father_mobile,
                "mother_name": mother_name.strip(),
                "mother_mobile": mother_mobile,
                "whatsapp": whatsapp,
                "photo": photo,
                "father_pic": father_pic,
                "id_front": id_front,
                "id_back": id_back,
            }
            profile_bytes = member_profile_pdf(member_data)
            st.session_state["new_member_pdf"] = append_rules_pdf(profile_bytes)
            st.session_state["new_member_name"] = name.strip()

            st.success(f"Member '{name.strip()}' saved successfully! 🎉")
            st.toast("Member added.")

        except ValueError as ve:
            st.error(str(ve))
        except Exception as e:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            st.error("Something went wrong while saving. Please try again.")

    # ---- Download button appears after a successful save ----
    if st.session_state.get("new_member_pdf"):
        st.download_button(
            "📄 Download Profile Card PDF",
            data=st.session_state["new_member_pdf"],
            file_name=f"{st.session_state.get('new_member_name', 'member')}_profile.pdf",
            mime="application/pdf",
            use_container_width=True,
        )