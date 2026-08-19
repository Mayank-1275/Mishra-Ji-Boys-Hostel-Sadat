import streamlit as st
import bcrypt
import time


def check_password(entered_password):
    """
    Compare the typed password against the stored hash in secrets.
    Returns True if it matches, False otherwise.
    """
    stored_hash = st.secrets["auth"]["admin_password_hash"]
    return bcrypt.checkpw(
        entered_password.encode("utf-8"),
        stored_hash.encode("utf-8"),
    )


def _hostel_name():
    return st.secrets.get("hostel", {}).get("name", "Hostel Management")


def login_screen():
    """
    Show the centered login form.
    On success, save login state in st.session_state.
    """
    # Scoped styling for the login screen.
    st.markdown(
        """
        <style>
        /* Center the middle column's content and give it a card feel */
        .login-accent {
            width: 54px; height: 5px; border-radius: 999px;
            background: linear-gradient(90deg,#0d9488,#0f766e);
            margin: 5vh auto 16px auto;
        }
        .login-title {
            text-align:center; font-size:1.5rem; font-weight:800;
            color:#0f172a; line-height:1.25; margin-bottom:4px;
        }
        .login-sub {
            text-align:center; color:#64748b; font-size:0.9rem;
            margin-bottom:22px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    left, middle, right = st.columns([1, 2, 1])
    with middle:
        hostel = _hostel_name()

        # Header: accent line + hostel name + subtitle.
        st.markdown(
            f'<div class="login-accent"></div>'
            f'<div class="login-title">{hostel}</div>'
            f'<div class="login-sub">Management Portal — please log in</div>',
            unsafe_allow_html=True,
        )

        # Login fields (no HTML wrapper — avoids the empty white bar issue).
        role = st.selectbox("Login as", ["Admin", "Staff"])
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password",
                                 placeholder="Enter your password")

        st.write("")  # small spacing before the button

        if st.button("Log In", use_container_width=True):
            if not username:
                st.error("Please enter a username.")
            elif check_password(password):
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.session_state["role"] = role
                st.success("Login successful!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Incorrect password. Please try again.")


def logout():
    """Clear the session and return to the login screen."""
    for key in ["logged_in", "username", "role"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()