import io
import base64
from PIL import Image

# Reject any single upload bigger than this (before compression).
MAX_UPLOAD_MB = 5

# Shrink the longest side of the image down to this many pixels.
MAX_EDGE_PX = 800

# JPEG quality (0-100). ~70 keeps it clear but small.
JPEG_QUALITY = 70


def compress_image(uploaded_file):
    """
    Take an uploaded/captured image, shrink it, and return it as a
    Base64 text string ready to store in the database.
    Returns None if there is no file.
    Raises ValueError if the file is too big.
    """
    if uploaded_file is None:
        return None

    # Check the file size first (in megabytes).
    size_mb = uploaded_file.size / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise ValueError(
            f"Image is {size_mb:.1f} MB, larger than the {MAX_UPLOAD_MB} MB limit."
        )

    # Open the image.
    img = Image.open(uploaded_file)

    # Convert to RGB so it can always be saved as JPEG.
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Resize so the longest edge is at most MAX_EDGE_PX (keeps shape).
    img.thumbnail((MAX_EDGE_PX, MAX_EDGE_PX))

    # Save the smaller image into memory (not to disk).
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)

    # Turn those bytes into Base64 text.
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return encoded


def decode_image(base64_string):
    """
    Turn a stored Base64 text string back into image bytes,
    so it can be shown with st.image(...).
    Returns None if there is nothing stored.
    """
    if not base64_string:
        return None
    return base64.b64decode(base64_string)