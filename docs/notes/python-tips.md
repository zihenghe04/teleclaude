## List Comprehensions with Conditions

List comprehensions are one of Python's most powerful features. Use them to replace simple `for` loops with filter logic:

```python
# Instead of this
results = []
for item in data:
    if item.is_valid():
        results.append(item.name)

# Write this
results = [item.name for item in data if item.is_valid()]
```

For nested comprehensions, keep it readable — if it's hard to read, use a regular loop:

```python
# Flatten a 2D list
flat = [x for row in matrix for x in row]
```

## Context Managers

Always use context managers for resource management. You can create custom ones with `contextlib`:

```python
from contextlib import contextmanager

@contextmanager
def timer(label):
    import time
    start = time.perf_counter()
    yield
    elapsed = time.perf_counter() - start
    print(f"{label}: {elapsed:.3f}s")

with timer("data processing"):
    process_data()
```

## Dataclasses

Use `dataclasses` instead of plain classes for data containers:

```python
from dataclasses import dataclass, field

@dataclass
class Config:
    host: str = "localhost"
    port: int = 8080
    debug: bool = False
    tags: list[str] = field(default_factory=list)

config = Config(port=3000, debug=True)
print(config)  # Config(host='localhost', port=3000, debug=True, tags=[])
```

## F-Strings

F-strings support expressions and formatting:

```python
name = "World"
value = 3.14159

print(f"Hello, {name}!")
print(f"Pi is approximately {value:.2f}")
print(f"{'centered':^20}")  # '      centered      '
print(f"{1_000_000:,}")     # '1,000,000'
```

## Walrus Operator (:=)

The walrus operator assigns and returns a value in a single expression:

```python
# Read lines until empty
while (line := input("Enter text: ")) != "":
    process(line)

# Filter and use result
if (n := len(data)) > 10:
    print(f"Processing {n} items")
```

## `pathlib` for File Operations

Prefer `pathlib` over `os.path`:

```python
from pathlib import Path

# Path operations
config_dir = Path.home() / ".config" / "myapp"
config_dir.mkdir(parents=True, exist_ok=True)

# Read/write files
config_file = config_dir / "settings.json"
data = config_file.read_text(encoding="utf-8")
config_file.write_text('{"key": "value"}', encoding="utf-8")

# Glob patterns
for py_file in Path("src").rglob("*.py"):
    print(py_file)
```

## Dictionary Tricks

```python
# Merge dictionaries (Python 3.9+)
merged = defaults | overrides

# Dictionary comprehension with conditional
filtered = {k: v for k, v in data.items() if v is not None}

# defaultdict for grouping
from collections import defaultdict
groups = defaultdict(list)
for item in items:
    groups[item.category].append(item)

# Get with default
value = config.get("timeout", 30)
```

## Type Hints

Modern Python type hints make code self-documenting:

```python
from typing import Optional

def fetch_user(user_id: int) -> Optional[dict]:
    """Fetch user by ID, returns None if not found."""
    ...

def process_items(items: list[str], *, verbose: bool = False) -> int:
    """Process items, return count of processed items."""
    ...
```

## Error Handling Patterns

```python
# Specific exceptions, not bare except
try:
    result = api.fetch(url)
except ConnectionError:
    result = cached_value
except TimeoutError:
    logger.warning("Request timed out, retrying...")
    result = api.fetch(url, timeout=60)

# Use else for code that runs only on success
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    data = {}
else:
    validate(data)  # Only runs if parsing succeeded
finally:
    cleanup()       # Always runs
```
