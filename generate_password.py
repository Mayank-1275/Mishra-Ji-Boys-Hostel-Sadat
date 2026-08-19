"""
Helper to create a secure password hash for login.
Run:  python generate_password.py
Type the password you want, and it prints a hash to copy
into .streamlit/secrets.toml  ->  admin_password_hash
"""

import bcrypt
import getpass

# Ask for the password (getpass hides it as you type).
password = getpass.getpass("Enter the admin password you want to use: ")
confirm = getpass.getpass("Type it again to confirm: ")

if password != confirm:
    print("\nPasswords did not match. Please run the script again.")
else:
    # Turn the password into a secure hash.
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    print("\nYour password hash (copy the whole line below):\n")
    print(hashed.decode("utf-8"))
    print("\nPaste it into secrets.toml as admin_password_hash")