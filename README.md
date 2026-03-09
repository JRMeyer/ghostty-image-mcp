# ghostty-image-mcp

An MCP server that displays images inline in [Ghostty](https://ghostty.org/) using the [Kitty graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/).

Built for use with [Claude Code](https://docs.anthropic.com/en/docs/claude-code), but works with any MCP client running in a Kitty-compatible terminal.

## Features

- Display images directly in the terminal (PNG, JPEG, SVG, and more)
- Adjustable scale (10%–100% of terminal width)
- Automatic centering in the terminal
- Automatic format conversion to PNG via `sips` (macOS) and `rsvg-convert` (SVG)
- No escape sequence leaks (`q=2` suppresses all protocol responses)

## Requirements

- macOS (uses `sips` for image conversion)
- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- A Kitty graphics protocol-compatible terminal ([Ghostty](https://ghostty.org/), [Kitty](https://sw.kovidgoyal.net/kitty/), etc.)
- `rsvg-convert` (optional, for SVG support — install via `brew install librsvg`)

## Setup

1. Clone this repo:

```bash
git clone https://github.com/jrmeyer/ghostty-image-mcp.git
```

2. Add to your Claude Code config. Run:

```bash
claude mcp add ghostty-image -- uv run /path/to/ghostty-image-mcp/server.py
```

Or manually add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "ghostty-image": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "/path/to/ghostty-image-mcp/server.py"]
    }
  }
}
```

3. Restart Claude Code.

## Usage

From Claude Code, ask it to display an image:

```
show me ~/photos/cat.jpg
```

The `show_image` tool accepts:
- `file_path` — path to the image file (PNG, JPEG, SVG, or any format `sips` can convert)
- `scale` — fraction of terminal width to use (0.1–1.0, default 0.75)

## How it works

The server captures the controlling TTY at startup (before MCP stdio transport takes over), then writes Kitty graphics protocol escape sequences directly using raw file descriptor I/O (`os.write`). Images are sent as chunked base64-encoded PNG data with `q=2` to suppress terminal acknowledgment responses, which prevents escape sequence text from leaking into TUI applications like Claude Code.
