# Input and Output Abstractions

This deployment tool provides pluggable interfaces for input gathering and output printing, allowing you to customize the user experience without modifying core logic.

## Overview

The tool uses two main abstractions:

1. **Printer** - Controls how output is displayed
2. **InputGatherer** - Controls how user input is collected

Both follow the Protocol pattern, allowing dependency injection and easy testing.

## Available Implementations

### Printer Implementations

#### `ConsolePrinter` (Default)
Basic console output with simple formatting and symbols (✓, ✗, ⚠).

```python
from octopize_avatar_deploy.printer import ConsolePrinter

printer = ConsolePrinter()
printer.print_success("Configuration complete!")
# Output: ✓ Configuration complete!
```

#### `RichPrinter`
Enhanced output using the [Rich](https://rich.readthedocs.io/) library with:
- Colored output (green for success, red for errors, yellow for warnings)
- Styled headers with panels
- Better formatting and visual hierarchy

```python
from octopize_avatar_deploy.printer import RichPrinter

printer = RichPrinter()
printer.print_header("Deployment Configuration")
printer.print_success("All steps completed!")
```

#### `SilentPrinter`
No-op implementation that suppresses all output. Useful for testing.

```python
from octopize_avatar_deploy.printer import SilentPrinter

printer = SilentPrinter()  # All print calls are silently ignored
```

### InputGatherer Implementations

#### `ConsoleInputGatherer` (Default)
Standard Python `input()` based gatherer.

```python
from octopize_avatar_deploy.input_gatherer import ConsoleInputGatherer

gatherer = ConsoleInputGatherer()
name = gatherer.prompt("Enter your name", default="User")
confirmed = gatherer.prompt_yes_no("Continue?", default=True)
choice = gatherer.prompt_choice("Select env", ["dev", "prod"], default="dev")
```

#### `RichInputGatherer`
Enhanced prompts using Rich library with:
- Styled prompts with colors
- Better visual feedback
- Built-in validation

```python
from octopize_avatar_deploy.input_gatherer import RichInputGatherer

gatherer = RichInputGatherer()
# Prompts appear in cyan with better formatting
```

#### `MockInputGatherer`
Pre-configured responses for testing without manual input.

```python
from octopize_avatar_deploy.input_gatherer import MockInputGatherer

# Provide responses in sequence
gatherer = MockInputGatherer(["production", True, "2"])
env = gatherer.prompt("Environment")  # Returns "production"
confirm = gatherer.prompt_yes_no("Proceed?")  # Returns True
choice = gatherer.prompt_choice("Pick", ["a", "b", "c"])  # Returns "b" (choice 2)
```

## Usage Examples

### Using Rich UI in DeploymentRunner

```python
from pathlib import Path
from octopize_avatar_deploy.configure import DeploymentRunner
from octopize_avatar_deploy.printer import RichPrinter
from octopize_avatar_deploy.input_gatherer import RichInputGatherer

# Create deployment runner with Rich UI
runner = DeploymentRunner(
    output_dir=Path("./output"),
    printer=RichPrinter(),
    input_gatherer=RichInputGatherer(),
)

# Run configuration with beautiful output
runner.run(interactive=True)
```

### Testing with Mock Input

```python
from pathlib import Path
from octopize_avatar_deploy.configure import DeploymentConfigurator
from octopize_avatar_deploy.printer import SilentPrinter
from octopize_avatar_deploy.input_gatherer import MockInputGatherer

# Pre-configure all responses
mock_responses = [
    "https://avatar.example.com",  # Base URL
    "yes",  # Enable email
    "smtp",  # Email provider choice
    # ... more responses
]

configurator = DeploymentConfigurator(
    templates_dir=Path("./templates"),
    output_dir=Path("./output"),
    printer=SilentPrinter(),  # No output during tests
    input_gatherer=MockInputGatherer(mock_responses),
)

configurator.run(interactive=True)  # Runs without manual input
```

### Custom Printer Implementation

You can create your own printer by implementing the `Printer` protocol:

```python
from octopize_avatar_deploy.printer import Printer

class FilePrinter:
    """Printer that writes to a log file."""
    
    def __init__(self, log_file: Path):
        self.log_file = log_file
    
    def print(self, message: str = "") -> None:
        with open(self.log_file, "a") as f:
            f.write(message + "\n")
    
    def print_success(self, message: str) -> None:
        self.print(f"SUCCESS: {message}")
    
    # ... implement other methods
```

## Demo

Run the Rich UI demo to see the enhanced formatting:

```bash
cd examples/
python demo_rich_ui.py
```

## Installation

The basic tool works with just PyYAML and Jinja2. For Rich UI support:

```bash
pip install rich>=13.0.0
```

Or install with the package:

```bash
pip install octopize-avatar-deploy[rich]
```

## Protocol Benefits

Using Protocol pattern provides:

1. **Type Safety** - MyPy validates implementations match the interface
2. **Flexibility** - Easy to swap implementations without changing code
3. **Testability** - Mock implementations for automated testing
4. **Extensibility** - Create custom implementations (file logging, GUI, etc.)
5. **No Inheritance Required** - Duck typing with type checking
