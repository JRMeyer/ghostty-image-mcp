# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp", "pyobjc-framework-Quartz"]
# ///

from mcp.server.fastmcp import FastMCP
import base64
import fcntl
import os
import struct
import subprocess
import termios

mcp = FastMCP("ghostty-image")

# Capture controlling TTY at startup (before stdio takes over)
TTY_PATH = None
try:
    fd = os.open("/dev/tty", os.O_RDWR)
    TTY_PATH = os.ttyname(fd)
    os.close(fd)
except OSError:
    pass


def get_terminal_cols():
    """Get terminal width in columns via ioctl on the captured TTY."""
    try:
        fd = os.open(TTY_PATH, os.O_RDONLY)
        buf = fcntl.ioctl(fd, termios.TIOCGWINSZ, b'\x00' * 8)
        os.close(fd)
        _rows, cols, _xpx, _ypx = struct.unpack('HHHH', buf)
        return cols if cols > 0 else 80
    except Exception:
        return 80


def pdf_page_to_png(file_path, page=1):
    """Render a specific page of a PDF to PNG using CoreGraphics (macOS)."""
    import Quartz
    from CoreFoundation import CFURLCreateFromFileSystemRepresentation

    tmp_png = "/tmp/_mcp_ghostty_image.png"
    url = CFURLCreateFromFileSystemRepresentation(None, file_path.encode(), len(file_path.encode()), False)
    pdf_doc = Quartz.CGPDFDocumentCreateWithURL(url)
    if not pdf_doc:
        return None

    page_count = Quartz.CGPDFDocumentGetNumberOfPages(pdf_doc)
    if page < 1 or page > page_count:
        return None

    pdf_page = Quartz.CGPDFDocumentGetPage(pdf_doc, page)
    rect = Quartz.CGPDFPageGetBoxRect(pdf_page, Quartz.kCGPDFMediaBox)
    # Render at 2x for sharpness
    scale_factor = 2.0
    w = int(rect.size.width * scale_factor)
    h = int(rect.size.height * scale_factor)

    cs = Quartz.CGColorSpaceCreateDeviceRGB()
    ctx = Quartz.CGBitmapContextCreate(None, w, h, 8, 4 * w, cs, Quartz.kCGImageAlphaPremultipliedLast)
    Quartz.CGContextSetRGBFillColor(ctx, 1, 1, 1, 1)
    Quartz.CGContextFillRect(ctx, Quartz.CGRectMake(0, 0, w, h))
    Quartz.CGContextScaleCTM(ctx, scale_factor, scale_factor)
    Quartz.CGContextDrawPDFPage(ctx, pdf_page)

    image = Quartz.CGBitmapContextCreateImage(ctx)
    url_out = CFURLCreateFromFileSystemRepresentation(None, tmp_png.encode(), len(tmp_png.encode()), False)
    dest = Quartz.CGImageDestinationCreateWithURL(url_out, "public.png", 1, None)
    Quartz.CGImageDestinationAddImage(dest, image, None)
    Quartz.CGImageDestinationFinalize(dest)
    return tmp_png


def get_pdf_page_count(file_path):
    """Get the number of pages in a PDF."""
    import Quartz
    from CoreFoundation import CFURLCreateFromFileSystemRepresentation

    url = CFURLCreateFromFileSystemRepresentation(None, file_path.encode(), len(file_path.encode()), False)
    pdf_doc = Quartz.CGPDFDocumentCreateWithURL(url)
    if not pdf_doc:
        return 0
    return Quartz.CGPDFDocumentGetNumberOfPages(pdf_doc)


def to_png(file_path, page=None, max_width=800):
    """Convert image to PNG and resize, returning the PNG file path."""
    if file_path.lower().endswith(".pdf"):
        return pdf_page_to_png(file_path, page or 1)

    tmp_png = "/tmp/_mcp_ghostty_image.png"
    if file_path.lower().endswith(".svg"):
        subprocess.run(
            ["rsvg-convert", "-w", str(max_width), file_path, "-o", tmp_png],
            capture_output=True
        )
    else:
        subprocess.run(
            ["sips", "-s", "format", "png", "--resampleWidth", str(max_width),
             file_path, "--out", tmp_png],
            capture_output=True
        )
    return tmp_png


@mcp.tool()
async def show_image(file_path: str, scale: float = 0.75, page: int | None = None) -> str:
    """Display an image in the terminal using Kitty graphics protocol via Ghostty.

    Args:
        file_path: Path to the image file (PNG, JPEG, SVG, PDF, etc.).
        scale: Fraction of terminal width to use (0.1–1.0). Default 0.75.
        page: Page number for PDFs (1-indexed). Defaults to 1.
    """
    if not TTY_PATH:
        return "Error: No controlling TTY found"

    file_path = os.path.expanduser(file_path)
    if not os.path.exists(file_path):
        return f"Error: File not found: {file_path}"

    # Clamp scale to [0.1, 1.0]
    scale = max(0.1, min(1.0, scale))

    # For PDFs, validate page number
    if file_path.lower().endswith(".pdf"):
        page_count = get_pdf_page_count(file_path)
        page = page or 1
        if page < 1 or page > page_count:
            return f"Error: Page {page} out of range (1–{page_count})"

    # Convert to PNG for protocol compatibility
    png_path = to_png(file_path, page=page)
    if not png_path or not os.path.exists(png_path):
        return "Error: Failed to convert image to PNG"

    cols = get_terminal_cols()
    display_cols = max(1, int(cols * scale))
    left_margin = (cols - display_cols) // 2

    # Use file-based transfer (t=f) — terminal reads the file directly.
    # Single small escape sequence instead of hundreds of chunked writes.
    png_path_b64 = base64.standard_b64encode(png_path.encode()).decode()
    tty_fd = os.open(TTY_PATH, os.O_WRONLY)
    try:
        os.write(tty_fd, b"\n")
        if left_margin > 0:
            os.write(tty_fd, f"\x1b[{left_margin + 1}G".encode())
        os.write(tty_fd, f"\x1b_Ga=T,f=100,t=f,c={display_cols},q=2;{png_path_b64}\x1b\\".encode())
        os.write(tty_fd, b"\n" * 10)
    finally:
        os.close(tty_fd)

    page_info = f", page {page}/{get_pdf_page_count(file_path)}" if page else ""
    name = os.path.basename(file_path)
    return f"{name}{page_info}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
