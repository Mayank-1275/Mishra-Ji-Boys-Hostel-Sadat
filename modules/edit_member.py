import json
from datetime import date

import streamlit as st

from utils.database import get_cursor
from utils.images import compress_image, decode_image
from utils.helpers import today_ist


def _valid_mobile(number):
    """True only if exactly 10 digits (empty allowed for optional fields)."""
    return number.isdigit() and len(number) == 10


def _section(title):
    """A small styled section heading."""
    st.markdown(
        f"<div style='font-size:1.05rem;font-weight:700;color:#0f766e;"
        f"margin:14px 0 6px 0;border-left:3px solid #0d9488;padding-left:8px;'>"
        f"{title}</div>",
        unsafe_allow_html=True,
    )


def _edit_image_input(label, key_prefix, existing_b64):
    """
    Show current image (if any) + a simple Upload to replace it.
    (Phone's Upload already offers camera + gallery.)
    Returns: ('keep', None) to keep old, or ('new', <UploadedFile>) to replace.
    """
    st.markdown(f"<div style='font-weight:700;margin:6px 0 2px 0;'>{label}</div>",
                unsafe_allow_html=True)
    col_cur, col_up = st.columns([1, 2])

    with col_cur:
        img = decode_image(existing_b64)
        if img:
            st.image(img, caption="Current", width=110)
        else:
            st.markdown(
                "<div style='background:#f1f5f9;border:1px dashed #cbd5e1;"
                "border-radius:10px;height:90px;display:flex;align-items:center;"
                "justify-content:center;color:#94a3b8;font-size:0.75rem;'>"
                "No current image</div>",
                unsafe_allow_html=True,
            )

    with col_up:
        new_file = st.file_uploader("Replace (upload)", type=["jpg", "jpeg", "png"],
                                    key=f"edit_{key_prefix}_up",
                                    label_visibility="collapsed")

    if new_file is not None:
        return ("new", new_file)
    return ("keep", None)


def edit_member_form(member):
    """
    Show an edit form pre-filled with the member's current data.
    'member' is the full member row (dict). Saves changes on submit.
    """
    st.markdown(
        f"<div style='font-size:1.3rem;font-weight:800;color:#0f172a;'>"
        f"✏️ Edit Member</div>"
        f"<div style='color:#64748b;font-size:0.85rem;margin-bottom:0.4rem;'>"
        f"Editing: {member['name']} (#{member['id']})</div>",
        unsafe_allow_html=True,
    )

    _section("👤 Personal details")
    name = st.text_input("Full Name *", value=member.get("name") or "",
                         key="e_name")

    dob_value = member.get("dob") or date(2000, 1, 1)
    dob = st.date_input("Date of Birth", value=dob_value,
                        min_value=date(1950, 1, 1), max_value=today_ist(),
                        key="e_dob")
    address = st.text_area("Address", value=member.get("address") or "",
                           key="e_address")

    _section("👨‍👩‍👦 Family details")
    col1, col2 = st.columns(2)
    with col1:
        father_name = st.text_input("Father's Name",
                                    value=member.get("father_name") or "",
                                    key="e_father_name")
        father_mobile = st.text_input("Father's Mobile (10 digits)",
                                      value=member.get("father_mobile") or "",
                                      key="e_father_mobile")
    with col2:
        mother_name = st.text_input("Mother's Name",
                                    value=member.get("mother_name") or "",
                                    key="e_mother_name")
        mother_mobile = st.text_input("Mother's Mobile (10 digits)",
                                      value=member.get("mother_mobile") or "",
                                      key="e_mother_mobile")

    whatsapp = st.text_input("WhatsApp Number (10 digits) *",
                             value=member.get("whatsapp") or "",
                             key="e_whatsapp")

    _section("📷 Photos & ID")
    st.caption("Leave a photo unchanged to keep the current one; "
               "tap Upload to replace it (phone offers camera or gallery).")

    photo_action = _edit_image_input("Member Photo", "photo", member.get("photo"))
    father_action = _edit_image_input("Father's Pic", "father_pic",
                                      member.get("father_pic"))
    idf_action = _edit_image_input("ID Front", "id_front", member.get("id_front"))
    idb_action = _edit_image_input("ID Back", "id_back", member.get("id_back"))

    st.divider()

    col_save, col_cancel = st.columns(2)
    save = col_save.button("💾 Save Changes", use_container_width=True,
                           key="save_edit_member")
    cancel = col_cancel.button("Cancel", use_container_width=True,
                               key="cancel_edit_member")

    if cancel:
        st.session_state["editing_member_id"] = None
        st.rerun()

    if save:
        _save_member_edits(
            member_id=member["id"],
            fields={
                "name": name.strip(), "dob": dob, "address": address.strip(),
                "father_name": father_name.strip(), "father_mobile": father_mobile,
                "mother_name": mother_name.strip(), "mother_mobile": mother_mobile,
                "whatsapp": whatsapp,
            },
            image_actions={
                "photo": photo_action, "father_pic": father_action,
                "id_front": idf_action, "id_back": idb_action,
            },
            old_member=member,
        )


def _save_member_edits(member_id, fields, image_actions, old_member):
    # ---- Validate ----
    errors = []
    if not fields["name"]:
        errors.append("Full Name is required.")
    if not _valid_mobile(fields["whatsapp"]):
        errors.append("WhatsApp Number must be exactly 10 digits.")
    if fields["father_mobile"] and not _valid_mobile(fields["father_mobile"]):
        errors.append("Father's Mobile must be exactly 10 digits.")
    if fields["mother_mobile"] and not _valid_mobile(fields["mother_mobile"]):
        errors.append("Mother's Mobile must be exactly 10 digits.")
    if errors:
        for e in errors:
            st.error(e)
        return

    conn = None
    try:
        # Resolve images: keep old value, or compress the new upload.
        image_values = {}
        with st.spinner("Saving changes..."):
            for key, (action, new_file) in image_actions.items():
                if action == "new":
                    image_values[key] = compress_image(new_file)
                else:
                    image_values[key] = old_member.get(key)  # keep existing

            conn, cursor = get_cursor()
            cursor.execute(
                """
                UPDATE members SET
                    name=%s, dob=%s, address=%s,
                    father_name=%s, father_mobile=%s,
                    mother_name=%s, mother_mobile=%s, whatsapp=%s,
                    photo=%s, father_pic=%s, id_front=%s, id_back=%s
                WHERE id=%s
                """,
                (
                    fields["name"], fields["dob"], fields["address"],
                    fields["father_name"], fields["father_mobile"],
                    fields["mother_name"], fields["mother_mobile"], fields["whatsapp"],
                    image_values["photo"], image_values["father_pic"],
                    image_values["id_front"], image_values["id_back"],
                    member_id,
                ),
            )
            cursor.execute(
                "INSERT INTO audit_log (actor, action, entity, entity_id, details_json) "
                "VALUES (%s,%s,%s,%s,%s)",
                (st.session_state.get("username", "unknown"),
                 "edit_member", "members", member_id,
                 json.dumps({"name": fields["name"]})),
            )
            conn.commit()

        st.success("Member details updated successfully! 🎉")
        st.toast("Member updated.")
        st.session_state["editing_member_id"] = None
        st.rerun()

    except ValueError as ve:
        st.error(str(ve))  # image too big
    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        st.error("Could not save the changes. Please try again.")