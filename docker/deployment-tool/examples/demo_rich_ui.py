#!/usr/bin/env python3
"""
Demo script showing how to use Rich implementations for prettier CLI output.

This demonstrates how to use RichPrinter and RichInputGatherer for enhanced
user experience with colors, styled prompts, and better formatting.
"""

from pathlib import Path

from octopize_avatar_deploy.configure import DeploymentRunner
from octopize_avatar_deploy.input_gatherer import RichInputGatherer
from octopize_avatar_deploy.printer import RichPrinter


def main():
    """Run deployment configuration with Rich-based UI."""
    print("\n" + "=" * 60)
    print("Avatar Deployment - Rich UI Demo")
    print("=" * 60)
    print("\nThis demo shows the deployment tool with enhanced Rich formatting.")
    print("Compare this to the standard console output!\n")

    # Create Rich-based printer and input gatherer
    printer = RichPrinter()
    input_gatherer = RichInputGatherer()

    # Demonstrate printer capabilities
    printer.print_header("Rich Printer Demo")
    printer.print("This is a regular message")
    printer.print_success("This is a success message with green checkmark")
    printer.print_error("This is an error message with red X")
    printer.print_warning("This is a warning message with yellow symbol")
    printer.print_step("This is a step description")
    printer.print_step("This step was already completed", skipped=True)

    # Demonstrate input gatherer capabilities
    printer.print_header("Rich Input Gatherer Demo")

    # Example 1: Simple prompt with default
    name = input_gatherer.prompt(
        "What's your name?", default="Anonymous"
    )
    printer.print(f"Hello, {name}!")

    # Example 2: Yes/No confirmation
    proceed = input_gatherer.prompt_yes_no(
        "Do you want to see a choice demo?", default=True
    )

    if proceed:
        # Example 3: Choice selection
        choice = input_gatherer.prompt_choice(
            "Select your favorite deployment environment",
            choices=["Development", "Staging", "Production"],
            default="Staging",
        )
        printer.print_success(f"You selected: {choice}")

    # Show how to use with DeploymentRunner
    printer.print_header("Using Rich UI with DeploymentRunner")
    printer.print(
        "To use Rich UI with the deployment tool, pass the Rich implementations:"
    )
    printer.print()
    printer.print("  runner = DeploymentRunner(")
    printer.print("      output_dir=Path('./output'),")
    printer.print("      printer=RichPrinter(),")
    printer.print("      input_gatherer=RichInputGatherer(),")
    printer.print("  )")
    printer.print()
    printer.print_success("Demo complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDemo cancelled by user.")
    except ImportError as e:
        print(f"\nError: {e}")
        print("\nMake sure rich is installed: pip install rich")
