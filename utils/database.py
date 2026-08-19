import streamlit as st
import mysql.connector
from mysql.connector import Error


@st.cache_resource
def _get_cached_connection():
    """Open one shared connection to the MySQL database (cached)."""
    conn = mysql.connector.connect(
        host=st.secrets["db"]["host"],
        port=st.secrets["db"]["port"],
        user=st.secrets["db"]["user"],
        password=st.secrets["db"]["password"],
        database=st.secrets["db"]["database"],
        autocommit=False,
    )
    return conn


def get_connection():
    """
    Return a live database connection.
    If the cached one has dropped, clear it and open a fresh one.
    """
    try:
        conn = _get_cached_connection()
        conn.ping(reconnect=True, attempts=3, delay=2)
        return conn
    except Exception:
        # Cached connection is stale/broken -> clear cache and retry once.
        try:
            _get_cached_connection.clear()
        except Exception:
            pass
        try:
            conn = _get_cached_connection()
            return conn
        except Error:
            st.error("Could not connect to the database. Please check your settings.")
            st.stop()


def get_cursor():
    """
    Give back a live connection plus a buffered cursor.
    buffered=True reads all rows immediately, preventing the
    'Unread result found' error.
    """
    conn = get_connection()
    return conn, conn.cursor(dictionary=True, buffered=True)