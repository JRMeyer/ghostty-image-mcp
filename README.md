# ghostty-image-mcp

An MCP server that displays images inline in [Ghostty](https://ghostty.org/) using the [Kitty graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/).

Built for use with [Claude Code](https://docs.anthropic.com/en/docs/claude-code), but works with any MCP client running in a Kitty-compatible terminal.

## Features

- Display images directly in the terminal (PNG, JPEG, SVG, and more)
- Automatic format conversion to PNG via `sips` (macOS) and `rsvg-convert` (SVG)
- Images fit to terminal width automatically
- No escape sequence leaks (`q=2` suppresses all protocol responses)
- Proper cursor advancement after image display

## Requirements

- macOS (uses `sips` for image conversion)
- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- A Kitty graphics protocol-compatible terminal ([Ghostty](https://ghostty.org/), [Kitty](https://sw.kovidgoyal.net/kitty/), etc.)
- `rsvg-convert` (optional, for SVG support — install via `brew install librsvg`)

## Setup

Add to your Claude Code MCP settings (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "ghostty-image": {
      "command": "uv",
      "args": ["run", "/path/to/ghostty-image-mcp/server.py"]
    }
  }
}
```

## Usage

From Claude Code, ask it to display an image:

```
show me this image: /path/to/image.jpg
```

The `show_image` tool accepts a `file_path` parameter and supports PNG, JPEG, SVG, and any other format that `sips` can convert to PNG.

## How it works

The server captures the controlling TTY at startup, then writes Kitty graphics protocol escape sequences directly using raw file descriptor I/O (`os.write`). Images are sent as chunked base64-encoded PNG data with `q=2` to suppress terminal acknowledgment responses, which prevents escape sequence text from leaking into TUI applications like Claude Code.
