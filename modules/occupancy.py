import json
from datetime import date

import streamlit as st

from utils.database import get_cursor
from utils.images import decode_image
from utils.helpers import today_ist, format_money, format_date

BEDS = ["A", "B", "C"]


def _fetch_rooms():
    """Return the list of room numbers (already seeded: 19 rooms)."""
    conn, cursor = get_cursor()
    cursor.execute("SELECT room_no FROM rooms ORDER BY room_no")
    return [r["room_no"] for r in cursor.fetchall()]


def _fetch_active_members_not_in_room():
    """Members who are active and NOT currently assigned to any room."""
    conn, cursor = get_cursor()
    cursor.execute(
        """
        SELECT m.id, m.name, m.whatsapp, m.photo
        FROM members m
        WHERE m.is_active = 1
          AND m.id NOT IN (
              SELECT member_id FROM occupancy WHERE is_active = 1
          )
        ORDER BY m.name
        """
    )
    return cursor.fetchall()


def _fetch_room_occupants(room_no):
    """Active occupants of a room, with member name and bed."""
    conn, cursor = get_cursor()
    cursor.execute(
        """
        SELECT o.id AS occupancy_id, o.member_id, o.bed, o.start_date,
               o.daily_rent, m.name
        FROM occupancy o
        JOIN members m ON m.id = o.member_id
        WHERE o.room_no = %s AND o.is_active = 1
        ORDER BY o.bed
        """,
        (room_no,),
    )
    return cursor.fetchall()


def occupancy_screen():
    st.markdown(
        "<h1 style='margin-bottom:0;'>Room Occupancy</h1>"
        "<div style='color:#64748b;font-size:0.9rem;margin-bottom:0.6rem;'>"
        "Assign members to rooms and beds · Max 3 per room</div>",
        unsafe_allow_html=True,
    )

    rooms = _fetch_rooms()
    if not rooms:
        st.info("No rooms found yet.")
        return

    room_no = st.selectbox("Select a room", rooms)

    occupants = _fetch_room_occupants(room_no)
    taken_beds = [o["bed"] for o in occupants]
    free_beds = [b for b in BEDS if b not in taken_beds]
    occ_by_bed = {o["bed"]: o for o in occupants}

    # ---- Room summary pill ----
    filled = len(occupants)
    if filled == 0:
        pcol, pbg, ptxt = "#047857", "#ecfdf5", "Empty (0/3)"
    elif filled < 3:
        pcol, pbg, ptxt = "#b45309", "#fffbeb", f"{filled}/3 filled"
    else:
        pcol, pbg, ptxt = "#b91c1c", "#fef2f2", "Full (3/3)"
    st.markdown(
        f"<div style='margin:6px 0 10px 0;'><span style='background:{pbg};"
        f"color:{pcol};padding:4px 12px;border-radius:999px;font-weight:700;'>"
        f"Room {room_no} · {ptxt}</span></div>",
        unsafe_allow_html=True,
    )

    # ---- Show all three beds (occupied or empty) ----
    st.subheader("Beds")
    for bed in BEDS:
        o = occ_by_bed.get(bed)
        if o:
            col_info, col_btn = st.columns([4, 1])
            with col_info:
                st.markdown(
                    f"<div style='background:#ffffff;border:1px solid #e2e8f0;"
                    f"border-left:4px solid #0d9488;border-radius:12px;"
                    f"padding:10px 14px;margin-bottom:8px;'>"
                    f"<span style='font-weight:800;color:#0f766e;'>Bed {bed}</span>"
                    f" &nbsp; <span style='font-weight:700;'>{o['name']}</span><br>"
                    f"<span style='color:#64748b;font-size:0.85rem;'>"
                    f"From {format_date(o['start_date'])} · "
                    f"{format_money(o['daily_rent'])}/day</span></div>",
                    unsafe_allow_html=True,
                )
            with col_btn:
                st.write("")
                if st.button("Remove", key=f"remove_{o['occupancy_id']}",
                             use_container_width=True):
                    _remove_occupant(o, room_no)
        else:
            st.markdown(
                f"<div style='background:#f8fafc;border:1px dashed #cbd5e1;"
                f"border-radius:12px;padding:10px 14px;margin-bottom:8px;"
                f"color:#94a3b8;'>"
                f"<span style='font-weight:700;'>Bed {bed}</span> — empty</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # ---- Add a member to this room ----
    st.subheader("➕ Add a member to this room")

    if len(occupants) >= 3:
        st.warning("This room is full (3 members). Remove someone before adding.")
        return

    available_members = _fetch_active_members_not_in_room()
    if not available_members:
        st.info("No unassigned active members available. Add a member first.")
        return

    # ---- Search box (outside form, so it filters live) ----
    search = st.text_input("🔍 Search member by name",
                           placeholder="Type a name to filter…")
    if search.strip():
        term = search.strip().lower()
        filtered = [m for m in available_members if term in m["name"].lower()]
    else:
        filtered = available_members

    if not filtered:
        st.warning("No matching member found. Clear the search to see all.")
        return

    # Build a friendly label -> member map.
    member_map = {f"{m['name']} (#{m['id']})": m for m in filtered}
    chosen_label = st.selectbox("Select member", list(member_map.keys()))
    chosen_member = member_map[chosen_label]

    # ---- Small confirm preview (photo + name) ----
    col_pic, col_name = st.columns([1, 3])
    with col_pic:
        img = decode_image(chosen_member.get("photo"))
        if img:
            st.image(img, width=90)
        else:
            st.markdown(
                "<div style='background:#f1f5f9;border:1px dashed #cbd5e1;"
                "border-radius:10px;width:90px;height:90px;display:flex;"
                "align-items:center;justify-content:center;color:#94a3b8;"
                "font-size:0.7rem;'>No photo</div>",
                unsafe_allow_html=True,
            )
    with col_name:
        st.markdown(
            f"<div style='padding-top:8px;'>"
            f"<div style='color:#64748b;font-size:0.8rem;'>Assigning:</div>"
            f"<div style='font-size:1.2rem;font-weight:800;'>"
            f"{chosen_member['name']}</div></div>",
            unsafe_allow_html=True,
        )

    # ---- Assignment details (in a form) ----
    with st.form("add_occupancy_form"):
        col1, col2 = st.columns(2)
        with col1:
            bed = st.selectbox("Bed", free_beds)
        with col2:
            start_date = st.date_input("Start date", value=today_ist(),
                                       max_value=today_ist())
        monthly_rent = st.number_input("Monthly rent (₹)", min_value=0.0, step=100.0,
                                       value=1000.0)
        # Convert to a daily rate in the background (fixed 30-day month).
        daily_rent = round(monthly_rent / 30, 2)
        st.caption(f"Daily rate (auto): {format_money(daily_rent)}/day  "
                   f"(monthly ÷ 30)")

        submitted = st.form_submit_button(
            f"Assign {chosen_member['name']} to Room {room_no}",
            use_container_width=True)

    if submitted:
        _assign_member(
            member_id=chosen_member["id"],
            room_no=room_no,
            bed=bed,
            start_date=start_date,
            daily_rent=daily_rent,
        )


def _assign_member(member_id, room_no, bed, start_date, daily_rent):
    """Insert a new active occupancy row (with safety re-checks)."""
    conn = None
    try:
        conn, cursor = get_cursor()

        # Re-check: room not full and bed still free (avoid race/double submit).
        cursor.execute(
            "SELECT bed FROM occupancy WHERE room_no=%s AND is_active=1",
            (room_no,),
        )
        current = [r["bed"] for r in cursor.fetchall()]
        if len(current) >= 3:
            st.error("Room is already full.")
            return
        if bed in current:
            st.error(f"Bed {bed} is already taken. Please pick another bed.")
            return

        cursor.execute(
            """
            INSERT INTO occupancy
                (member_id, room_no, bed, start_date, daily_rent, is_active)
            VALUES (%s,%s,%s,%s,%s,1)
            """,
            (member_id, room_no, bed, start_date, daily_rent),
        )
        occupancy_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO audit_log (actor, action, entity, entity_id, details_json) "
            "VALUES (%s,%s,%s,%s,%s)",
            (
                st.session_state.get("username", "unknown"),
                "assign_room", "occupancy", occupancy_id,
                json.dumps({"member_id": member_id, "room": room_no, "bed": bed}),
            ),
        )
        conn.commit()
        st.success(f"Member assigned to Room {room_no}, Bed {bed}. 🎉")
        st.toast("Room updated.")
        st.rerun()

    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        st.error("Could not assign the member. Please try again.")


def _remove_occupant(occupant, room_no):
    """Soft-remove: mark the occupancy row inactive (keeps history)."""
    conn = None
    try:
        conn, cursor = get_cursor()
        cursor.execute(
            "UPDATE occupancy SET is_active=0 WHERE id=%s",
            (occupant["occupancy_id"],),
        )
        cursor.execute(
            "INSERT INTO audit_log (actor, action, entity, entity_id, details_json) "
            "VALUES (%s,%s,%s,%s,%s)",
            (
                st.session_state.get("username", "unknown"),
                "remove_from_room", "occupancy", occupant["occupancy_id"],
                json.dumps({"member": occupant["name"], "room": room_no,
                            "bed": occupant["bed"]}),
            ),
        )
        conn.commit()
        st.success(f"{occupant['name']} removed from Room {room_no}.")
        st.toast("Occupant removed.")
        st.rerun()
    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        st.error("Could not remove the occupant. Please try again.")