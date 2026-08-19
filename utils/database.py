import streamlit as st
import mysql.connector
from mysql.connector import Error


@st.cache_resource
def get_connection():
    """
    Open one shared connection to the MySQL database.
    Connection details are read from Streamlit secrets (never hardcoded).
    @st.cache_resource keeps a single connection alive instead of
    opening a new one on every click (faster and cheaper).
    """
    try:
        conn = mysql.connector.connect(
            host=st.secrets["db"]["host"],
            port=st.secrets["db"]["port"],
            user=st.secrets["db"]["user"],
            password=st.secrets["db"]["password"],
            database=st.secrets["db"]["database"],
            autocommit=False,
        )
        return conn
    except Error as e:
        st.error("Could not connect to the database. Please check your settings.")
        st.stop()


def get_cursor():
    """
    Give back a fresh cursor plus the connection.
    Uses a buffered cursor so results are fully read (prevents the
    'Unread result found' error). Reconnects if the connection dropped.
    """
    conn = get_connection()

    # Make sure the connection is still alive; reconnect if it dropped.
    try:
        conn.ping(reconnect=True, attempts=3, delay=2)
    except Exception:
        # If ping fails (stale/unread result), reset the cached connection.
        try:
            get_connection.clear()
        except Exception:
            pass
        conn = get_connection()

    # buffered=True reads all rows immediately, so nothing is left "unread".
    return conn, conn.cursor(dictionary=True, buffered=True)