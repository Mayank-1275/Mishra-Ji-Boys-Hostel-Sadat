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
    A 'cursor' is the tool we use to run SQL commands.
    dictionary=True means results come back as easy-to-read
    name:value pairs instead of plain tuples.
    """
    conn = get_connection()
    # Make sure the connection is still alive; reconnect if it dropped.
    conn.ping(reconnect=True, attempts=3, delay=2)
    return conn, conn.cursor(dictionary=True)