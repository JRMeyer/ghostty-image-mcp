# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp"]
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


def to_png(file_path):
    """Convert image to PNG, returning the PNG file path."""
    if file_path.lower().endswith(".png"):
        return file_path

    tmp_png = "/tmp/_mcp_ghostty_image.png"
    if file_path.lower().endswith(".svg"):
        subprocess.run(
            ["rsvg-convert", "-w", "2000", file_path, "-o", tmp_png],
            capture_output=True
        )
    else:
        subprocess.run(
            ["sips", "-s", "format", "png", file_path, "--out", tmp_png],
            capture_output=True
        )
    return tmp_png


@mcp.tool()
async def show_image(file_path: str, scale: float = 0.75) -> str:
    """Display an image in the terminal using Kitty graphics protocol via Ghostty.

    Args:
        file_path: Path to the image file.
        scale: Fraction of terminal width to use (0.1–1.0). Default 0.75.
    """
    if not TTY_PATH:
        return "Error: No controlling TTY found"

    file_path = os.path.expanduser(file_path)
    if not os.path.exists(file_path):
        return f"Error: File not found: {file_path}"

    # Clamp scale to [0.1, 1.0]
    scale = max(0.1, min(1.0, scale))

    # Convert to PNG for protocol compatibility
    png_path = to_png(file_path)
    if not os.path.exists(png_path):
        return "Error: Failed to convert image to PNG"

    # Read PNG data and base64-encode
    with open(png_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode()

    term_cols = get_terminal_cols()
    display_cols = max(1, int(term_cols * scale))
    left_margin = (term_cols - display_cols) // 2

    # Render synchronously during tool execution (Claude Code shows spinner,
    # minimal TTY contention). Image overlays current cursor position.
    CHUNK = 4096
    tty_fd = os.open(TTY_PATH, os.O_WRONLY)
    try:
        if left_margin > 0:
            os.write(tty_fd, f"\x1b[{left_margin + 1}G".encode())
        for i in range(0, len(data), CHUNK):
            chunk = data[i:i + CHUNK]
            is_last = (i + CHUNK >= len(data))
            m = 0 if is_last else 1
            if i == 0:
                os.write(tty_fd, f"\x1b_Ga=T,f=100,t=d,c={display_cols},m={m},q=2;{chunk}\x1b\\".encode())
            else:
                os.write(tty_fd, f"\x1b_Gm={m};{chunk}\x1b\\".encode())
        os.write(tty_fd, b"\n\n\n\n")
    finally:
        os.close(tty_fd)

    return f"Displayed: {file_path} (scale={scale})"


if __name__ == "__main__":
    mcp.run(transport="stdio")
