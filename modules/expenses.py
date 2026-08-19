import json
from datetime import date

import streamlit as st
import pandas as pd

from utils.database import get_cursor
from utils.helpers import today_ist, format_money, format_date

CATEGORIES = ["Electricity", "Maintenance", "Salary", "Water", "Misc"]


def expenses_screen():
    st.markdown(
        "<h1 style='margin-bottom:0;'>Expense Tracker</h1>"
        "<div style='color:#64748b;font-size:0.9rem;margin-bottom:0.6rem;'>"
        "Record hostel expenses · Feeds into Net Profit</div>",
        unsafe_allow_html=True,
    )

    tab_add, tab_view = st.tabs(["➕ Add Expense", "📊 View Expenses"])

    with tab_add:
        _add_expense_form()

    with tab_view:
        _view_expenses()


def _add_expense_form():
    with st.form("add_expense_form"):
        col1, col2 = st.columns(2)
        with col1:
            exp_date = st.date_input("Date", value=today_ist(), max_value=today_ist())
            category = st.selectbox("Category", CATEGORIES)
        with col2:
            amount = st.number_input("Amount (₹)", min_value=0.0, step=50.0, value=0.0)
        notes = st.text_area("Notes (optional)",
                             placeholder="e.g. June electricity bill")

        submitted = st.form_submit_button("💾 Save Expense", use_container_width=True)

    if submitted:
        if amount <= 0:
            st.error("Enter an amount greater than zero.")
            return

        conn = None
        try:
            conn, cursor = get_cursor()
            cursor.execute(
                "INSERT INTO expenses (exp_date, category, amount, notes, created_by) "
                "VALUES (%s,%s,%s,%s,%s)",
                (exp_date, category, amount, notes.strip(),
                 st.session_state.get("username", "unknown")),
            )
            exp_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO audit_log (actor, action, entity, entity_id, details_json) "
                "VALUES (%s,%s,%s,%s,%s)",
                (st.session_state.get("username", "unknown"),
                 "add_expense", "expenses", exp_id,
                 json.dumps({"category": category, "amount": amount})),
            )
            conn.commit()
            st.success(f"Expense of {format_money(amount)} saved. 🎉")
            st.toast("Expense added.")
        except Exception:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            st.error("Could not save the expense. Please try again.")


def _view_expenses():
    conn, cursor = get_cursor()

    # Month filter.
    col1, col2 = st.columns(2)
    with col1:
        months = ["All time", "This month"]
        period = st.selectbox("Show", months)

    if period == "This month":
        first = today_ist().replace(day=1)
        cursor.execute(
            "SELECT * FROM expenses WHERE exp_date >= %s ORDER BY exp_date DESC, id DESC",
            (first,),
        )
    else:
        cursor.execute("SELECT * FROM expenses ORDER BY exp_date DESC, id DESC")

    rows = cursor.fetchall()

    if not rows:
        st.info("No expenses recorded yet.")
        return

    total = sum(float(r["amount"]) for r in rows)

    # Total card.
    st.markdown(
        f"<div style='background:#ffffff;border:1px solid #e2e8f0;"
        f"border-left:5px solid #0d9488;border-radius:12px;padding:14px 16px;"
        f"margin:6px 0 12px 0;'>"
        f"<div style='color:#64748b;font-weight:600;'>Total ({period})</div>"
        f"<div style='font-size:1.5rem;font-weight:800;color:#0f172a;'>"
        f"{format_money(total)}</div></div>",
        unsafe_allow_html=True,
    )

    # Category-wise summary.
    by_cat = {}
    for r in rows:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + float(r["amount"])
    st.markdown("##### 📊 By category")
    cat_df = pd.DataFrame(
        [{"Category": k, "Amount": v} for k, v in by_cat.items()]
    ).set_index("Category")
    st.bar_chart(cat_df, color="#0d9488")

    # Full table.
    st.markdown("##### 🧾 All entries")
    table = [
        {"Date": format_date(r["exp_date"]), "Category": r["category"],
         "Amount": format_money(r["amount"]), "Notes": r["notes"] or "-",
         "By": r["created_by"]}
        for r in rows
    ]
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)