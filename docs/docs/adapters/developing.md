# Developing Custom Adapters

Create a custom adapter by implementing the `ToolAdapter` abstract base class.

## Interface

```python
from tokenlens.adapters.base import ToolAdapter

class MyToolAdapter(ToolAdapter):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def version(self) -> str:
        return "1.0.0"

    def discover(self) -> bool:
        """Return True if this tool's logs are available."""
        ...

    def get_log_paths(self) -> list[Path]:
        """Return all log file paths to monitor."""
        ...

    def parse_file(self, path: Path) -> list[TokenEvent]:
        """Parse new entries from a log file."""
        ...

    def get_last_processed_position(self, path: Path) -> int:
        """Return the byte offset of last processed position."""
        ...
```

## Registration

Register via entry points in `pyproject.toml`:

```toml
[project.entry-points."tokenlens.adapters"]
my_tool = "my_package.adapter:MyToolAdapter"
```
