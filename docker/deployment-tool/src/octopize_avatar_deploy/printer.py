#!/usr/bin/env python3
"""
Output printer abstraction for deployment tool.

Provides a pluggable interface for customizing output behavior
(console, file, GUI, etc.) without modifying core logic.
"""

from pathlib import Path
from typing import Protocol

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class Printer(Protocol):
    """Protocol for output printing."""

    def print(self, message: str = "") -> None:
        """Print a regular message."""
        ...

    def print_header(self, title: str, width: int = 60) -> None:
        """Print a section header."""
        ...

    def print_success(self, message: str) -> None:
        """Print a success message."""
        ...

    def print_error(self, message: str) -> None:
        """Print an error message."""
        ...

    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        ...

    def print_step(self, description: str, skipped: bool = False) -> None:
        """Print a step header."""
        ...


class ConsolePrinter:
    """Default console-based printer implementation."""

    def print(self, message: str = "") -> None:
        """Print a regular message to console."""
        print(message)

    def print_header(self, title: str, width: int = 60) -> None:
        """Print a formatted section header."""
        self.print("\n" + "=" * width)
        self.print(title)
        self.print("=" * width)

    def print_success(self, message: str) -> None:
        """Print a success message with checkmark."""
        self.print(f"✓ {message}")

    def print_error(self, message: str) -> None:
        """Print an error message with X symbol."""
        self.print(f"✗ {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message with warning symbol."""
        self.print(f"⚠ {message}")

    def print_step(self, description: str, skipped: bool = False) -> None:
        """Print a step header with optional skipped indicator."""
        if skipped:
            self.print(f"\n--- {description} [SKIPPED - already completed] ---")
        else:
            self.print(f"\n--- {description} ---")


class SilentPrinter:
    """Silent printer that suppresses all output."""

    def print(self, message: str = "") -> None:
        """Do nothing."""
        pass

    def print_header(self, title: str, width: int = 60) -> None:
        """Do nothing."""
        pass

    def print_success(self, message: str) -> None:
        """Do nothing."""
        pass

    def print_error(self, message: str) -> None:
        """Do nothing."""
        pass

    def print_warning(self, message: str) -> None:
        """Do nothing."""
        pass

    def print_step(self, description: str, skipped: bool = False) -> None:
        """Do nothing."""
        pass


class RichPrinter:
    """
    Rich-based printer with enhanced formatting and colors.

    Uses the 'rich' library to provide beautiful console output with:
    - Colors and styles
    - Panels and boxes
    - Better formatting
    """

    def __init__(self):
        """Initialize RichPrinter with a Console instance."""
        if not RICH_AVAILABLE:
            raise ImportError(
                "Rich library not available. Install with: pip install rich"
            )
        self.console = Console()

    def print(self, message: str = "") -> None:
        """Print a regular message to console."""
        self.console.print(message)

    def print_header(self, title: str, width: int = 60) -> None:
        """Print a formatted section header with panel."""
        if title:
            panel = Panel(
                Text(title, style="bold cyan", justify="center"),
                border_style="cyan",
                padding=(0, 2),
            )
            self.console.print()
            self.console.print(panel)
        else:
            self.console.print()

    def print_success(self, message: str) -> None:
        """Print a success message with green checkmark."""
        self.console.print(f"[green]✓[/green] {message}")

    def print_error(self, message: str) -> None:
        """Print an error message with red X symbol."""
        self.console.print(f"[red]✗[/red] {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message with yellow warning symbol."""
        self.console.print(f"[yellow]⚠[/yellow] {message}")

    def print_step(self, description: str, skipped: bool = False) -> None:
        """Print a step header with optional skipped indicator."""
        self.console.print()
        if skipped:
            self.console.print(
                f"[dim]--- {description} [SKIPPED - already completed] ---[/dim]"
            )
        else:
            self.console.print(f"[bold blue]--- {description} ---[/bold blue]")


class FilePrinter:
    """
    File-based printer that writes all output to a log file.

    Useful for test debugging - when tests fail, you can inspect
    the log file to see what happened.
    """

    def __init__(self, log_file: Path | str, append: bool = False):
        """
        Initialize FilePrinter.

        Args:
            log_file: Path to log file
            append: Whether to append to existing file (default: False, overwrite)
        """
        self.log_file = Path(log_file)
        self.mode = "a" if append else "w"

        # Create parent directory if needed
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Clear file if not appending
        if not append:
            self.log_file.write_text("")

    def _write(self, message: str) -> None:
        """Write message to log file."""
        with open(self.log_file, "a") as f:
            f.write(message + "\n")

    def print(self, message: str = "") -> None:
        """Print a regular message to file."""
        self._write(message)

    def print_header(self, title: str, width: int = 60) -> None:
        """Print a formatted section header to file."""
        self._write("\n" + "=" * width)
        self._write(title)
        self._write("=" * width)

    def print_success(self, message: str) -> None:
        """Print a success message to file."""
        self._write(f"✓ {message}")

    def print_error(self, message: str) -> None:
        """Print an error message to file."""
        self._write(f"✗ {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message to file."""
        self._write(f"⚠ {message}")

    def print_step(self, description: str, skipped: bool = False) -> None:
        """Print a step header to file."""
        if skipped:
            self._write(f"\n--- {description} [SKIPPED - already completed] ---")
        else:
            self._write(f"\n--- {description} ---")
