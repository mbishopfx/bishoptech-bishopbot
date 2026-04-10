import os
import sys


NEON = "\033[38;5;118m"
STEEL = "\033[38;5;245m"
RESET = "\033[0m"

_BANNER_LINES = (
    "██████╗ ██╗███████╗██╗  ██╗ ██████╗ ██████╗ ",
    "██╔══██╗██║██╔════╝██║  ██║██╔═══██╗██╔══██╗",
    "██████╔╝██║███████╗███████║██║   ██║██████╔╝",
    "██╔══██╗██║╚════██║██╔══██║██║   ██║██╔═══╝ ",
    "██████╔╝██║███████║██║  ██║╚██████╔╝██║     ",
    "╚═════╝ ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ",
)


def _supports_color() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def print_bishop_banner(context: str | None = None, subtitle: str | None = None) -> None:
    if _supports_color():
        for line in _BANNER_LINES:
            print(f"{NEON}{line}{RESET}")
        meta = []
        if context:
            meta.append(context.upper())
        if subtitle:
            meta.append(subtitle)
        if meta:
            print(f"{STEEL}{' · '.join(meta)}{RESET}")
        return

    for line in _BANNER_LINES:
        print(line)
    meta = []
    if context:
        meta.append(context.upper())
    if subtitle:
        meta.append(subtitle)
    if meta:
        print(" · ".join(meta))
