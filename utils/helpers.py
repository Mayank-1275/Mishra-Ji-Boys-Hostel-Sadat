from datetime import datetime
import pytz
import urllib.parse

# India timezone
IST = pytz.timezone("Asia/Kolkata")


def now_ist():
    """Return the current date and time in India (IST)."""
    return datetime.now(IST)


def today_ist():
    """Return today's date in India (IST), with no time part."""
    return now_ist().date()


def format_date(d):
    """Turn a date into a clean readable string like 17-Aug-2026."""
    if d is None:
        return "-"
    return d.strftime("%d-%b-%Y")


def format_money(amount):
    """Turn a number into a rupee string like ₹1,500."""
    if amount is None:
        amount = 0
    return f"₹{amount:,.0f}"

def months_from_days(unpaid_days):
    """
    Convert unpaid days into WHOLE months (30 days = 1 month).
    66 days -> 2 months (remainder ignored for the reminder).
    Returns an integer count of whole months.
    """
    if unpaid_days <= 0:
        return 0
    return int(unpaid_days // 30)


def build_reminder_message(member_name, unpaid_days, daily_rent,
                           hostel_name, upi_id, payee_name):
    """
    Build the WhatsApp reminder text:
    - charges for WHOLE months only
    - shows the amount for those months
    - includes UPI ID and a request to share the payment screenshot
    Returns the plain message text (not yet URL-encoded).
    """
    months = months_from_days(unpaid_days)
    monthly_rent = daily_rent * 30
    amount_for_months = months * monthly_rent

    if months >= 1:
        body = (
            f"Dear {member_name}, this is a friendly reminder from {hostel_name}. "
            f"Your rent is pending for {months} month(s). "
            f"Kindly pay {format_money(amount_for_months)} "
            f"for these {months} month(s).\n\n"
            f"Pay via UPI: {upi_id} ({payee_name})\n\n"
            f"Please make the payment and share the screenshot here. Thank you."
        )
    else:
        # Less than a full month pending - remind gently without a month figure.
        due = unpaid_days * daily_rent
        body = (
            f"Dear {member_name}, a friendly reminder from {hostel_name}. "
            f"You have a pending balance of {format_money(due)} "
            f"({unpaid_days:.0f} day(s)).\n\n"
            f"Pay via UPI: {upi_id} ({payee_name})\n\n"
            f"Please pay and share the screenshot here. Thank you."
        )
    return body


def whatsapp_link(whatsapp_number, message_text):
    """Build a wa.me link (assumes India +91) from a message."""
    if not whatsapp_number:
        return None
    encoded = urllib.parse.quote(message_text)
    return f"https://wa.me/91{whatsapp_number}?text={encoded}"