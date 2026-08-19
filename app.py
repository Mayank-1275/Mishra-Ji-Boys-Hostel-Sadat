import streamlit as st
from modules.login import login_screen, logout
from modules.add_member import add_member_screen
from modules.occupancy import occupancy_screen
from modules.add_rent import add_rent_screen
from modules.search_member import search_member_screen
from modules.guests import guests_screen
from modules.expenses import expenses_screen
from modules.dashboard import dashboard_screen
from modules.reports import reports_screen


# ---- Page setup ----
st.set_page_config(
    page_title="Hostel Management",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Hostel name from secrets (falls back to a default if not set).
HOSTEL_NAME = st.secrets.get("hostel", {}).get("name", "Hostel Management")


# ---- Global styling (Blue/Teal, light, mobile-friendly) ----
def inject_css():
    st.markdown(
        """
        <style>
        /* ---- Base palette ---- */
        :root {
            --teal: #0d9488;
            --teal-dark: #0f766e;
            --teal-light: #ccfbf1;
            --ink: #0f172a;
            --muted: #64748b;
            --card-bg: #ffffff;
            --page-bg: #f8fafc;
        }

        /* App background */
        .stApp {
            background: linear-gradient(180deg, #f8fafc 0%, #f0fdfa 100%);
        }

        /* Tighten top padding so more fits on a phone screen */
        .block-container {
            padding-top: 1.2rem !important;
            padding-bottom: 3rem !important;
            max-width: 1100px;
        }

        /* ---- Headings ---- */
        h1, h2, h3 {
            color: var(--ink);
            font-weight: 700;
        }
        h1 { letter-spacing: -0.5px; }

        /* ---- Buttons ---- */
        .stButton > button, .stDownloadButton > button, .stLinkButton > a {
            border-radius: 12px !important;
            font-weight: 600 !important;
            padding: 0.55rem 1rem !important;
            border: 1px solid transparent !important;
            transition: all 0.15s ease-in-out !important;
            min-height: 44px;               /* comfortable tap target on phone */
        }
        /* Primary-style filled buttons */
        .stButton > button[kind="primary"],
        .stButton > button {
            background: var(--teal) !important;
            color: #ffffff !important;
            box-shadow: 0 2px 6px rgba(13,148,136,0.25) !important;
        }
        .stButton > button:hover {
            background: var(--teal-dark) !important;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(13,148,136,0.30) !important;
        }
        .stDownloadButton > button {
            background: #ffffff !important;
            color: var(--teal-dark) !important;
            border: 1.5px solid var(--teal) !important;
        }
        .stDownloadButton > button:hover {
            background: var(--teal-light) !important;
        }

        /* ---- Metric cards ---- */
        div[data-testid="stMetric"] {
            background: var(--card-bg);
            border: 1px solid #e2e8f0;
            border-left: 4px solid var(--teal);
            padding: 14px 16px;
            border-radius: 14px;
            box-shadow: 0 1px 3px rgba(15,23,42,0.06);
        }
        div[data-testid="stMetric"] label {
            color: var(--muted) !important;
            font-weight: 600 !important;
        }
        div[data-testid="stMetricValue"] {
            color: var(--ink) !important;
            font-weight: 700 !important;
        }

        /* ---- Inputs ---- */
        .stTextInput input, .stNumberInput input, .stDateInput input,
        .stTextArea textarea, div[data-baseweb="select"] > div {
            border-radius: 10px !important;
            border-color: #cbd5e1 !important;
        }
        .stTextInput input:focus, .stNumberInput input:focus {
            border-color: var(--teal) !important;
            box-shadow: 0 0 0 2px var(--teal-light) !important;
        }

        /* ---- Tabs ---- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 6px;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 10px 10px 0 0;
            padding: 8px 14px;
            font-weight: 600;
        }
        .stTabs [aria-selected="true"] {
            background: var(--teal-light);
            color: var(--teal-dark);
        }

        /* ---- Dataframes ---- */
        div[data-testid="stDataFrame"] {
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            overflow: hidden;
        }

        /* ---- Sidebar ---- */
        section[data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid #e2e8f0;
        }
        section[data-testid="stSidebar"] .stRadio label {
            padding: 6px 8px;
            border-radius: 8px;
            font-weight: 600;
        }

        /* Alerts a touch rounder */
        div[data-testid="stAlert"] {
            border-radius: 12px;
        }

        /* Hide the default Streamlit footer/menu for a cleaner app feel */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        /* ---- PHONE ONLY: smaller titles/headings on narrow screens ---- */
        @media (max-width: 640px) {
            .block-container h1 {
                font-size: 1.5rem !important;
                line-height: 1.25 !important;
            }
            .block-container h2 {
                font-size: 1.2rem !important;
            }
            .block-container h3 {
                font-size: 1.05rem !important;
            }
            /* tighten side padding so content uses full width on phone */
            .block-container {
                padding-left: 0.8rem !important;
                padding-right: 0.8rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# The menu items (unchanged).
MENU_ITEMS = [
    "🏠 Dashboard",
    "➕ Add Member",
    "🚪 Room Occupancy",
    "💰 Add Rent",
    "🔍 Search Member",
    "🧳 Temp Guests",
    "🧾 Expenses",
    "📈 Reports",
]


def render_page(choice):
    """Show the screen that matches the sidebar choice."""
    if choice == "🏠 Dashboard":
        dashboard_screen()
    elif choice == "➕ Add Member":
        add_member_screen()
    elif choice == "🚪 Room Occupancy":
        occupancy_screen()
    elif choice == "💰 Add Rent":
        add_rent_screen()
    elif choice == "🔍 Search Member":
        search_member_screen()
    elif choice == "🧳 Temp Guests":
        guests_screen()
    elif choice == "🧾 Expenses":
        expenses_screen()
    elif choice == "📈 Reports":
        reports_screen()


def main():
    """Main router: show login screen, or the app if logged in."""
    inject_css()

    # If not logged in, show the login screen and stop.
    if not st.session_state.get("logged_in", False):
        login_screen()
        return

    # ---- Logged in: build the sidebar menu ----
    with st.sidebar:
        st.markdown(
            f"<div style='font-size:1.35rem;font-weight:800;color:#0f766e;"
            f"line-height:1.25;margin-bottom:0.6rem;'>{HOSTEL_NAME}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='font-weight:700;font-size:1.05rem;'>"
            f"{st.session_state.get('username', 'User')}</div>"
            f"<div style='color:#64748b;font-size:0.85rem;margin-bottom:0.5rem;'>"
            f"Role: {st.session_state.get('role', '-')}</div>",
            unsafe_allow_html=True,
        )
        st.divider()

        choice = st.radio("Menu", MENU_ITEMS, label_visibility="collapsed")

        st.divider()
        if st.button("Log Out", use_container_width=True):
            logout()

    # ---- Show the chosen page in the main area ----
    render_page(choice)


if __name__ == "__main__":
    main()