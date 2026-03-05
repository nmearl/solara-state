# Solara State

A reactive state management framework for [Solara](https://solara.dev) apps that combines Pydantic validation with Solara's reactive system.

## Installation

```bash
pip install solara-state
```

**Requirements:** Python 3.13+, Pydantic 2.0+, Solara 1.51.1+

## Quick Start

```python
from solara_state import BaseState, StateField, get_state
import solara

class CounterState(BaseState):
    count: int = StateField(default=0)
    message: str = StateField(default="Hello")

@solara.component
def Counter():
    state = get_state(CounterState)

    with solara.Column():
        solara.Text(f"Count: {state.count.value}")
        solara.Text(f"Message: {state.message.value}")

        if solara.Button("Increment").clicked:
            state.count.value += 1

        if solara.Button("Reset").clicked:
            state.reset()
```

## Features

- **Reactive properties**: field access returns `solara.Reactive` objects that automatically trigger UI re-renders
- **Pydantic integration**: full validation, type coercion, and serialization; validators run on every write including writes through reactive refs
- **Bidirectional sync**: changes made via a reactive ref or via direct attribute assignment stay in sync
- **Global state**: thread-safe singleton management with `get_state()`
- **Local state**: instantiate `BaseState` directly for component-scoped state
- **Memory safe**: descriptor caches use `WeakKeyDictionary` so state instances are garbage collected normally

## API Reference

### `BaseState`

Base class for all state objects. Subclass it and declare fields with `StateField`.

```python
from typing import List
from pydantic import field_validator
from solara_state import BaseState, StateField

class AppState(BaseState):
    counter: int = StateField(default=0)
    items: List[str] = StateField(default_factory=list)

    @field_validator('counter')
    @classmethod
    def counter_non_negative(cls, v):
        if v < 0:
            raise ValueError('counter must be non-negative')
        return v
```

Field access returns a `solara.Reactive` object:

```python
state = AppState()

# Read
print(state.counter.value)   # 0

# Write via reactive ref — validation runs
state.counter.value = 10

# Write via attribute — validation runs
state.counter = 10

# Bulk update — warns on unknown field names
state.update(counter=5, items=["a", "b"])

# Reset all fields to their defaults
state.reset()
```

#### Methods

| Method | Description                                                                           |
|---|---------------------------------------------------------------------------------------|
| `update(**kwargs)` | Set multiple fields at once. Issues a `UserWarning` for any unrecognized field names. |
| `reset()` | Reset all fields to their declared defaults.                                          |
| `to_dict()` | Serialize state to a plain dictionary (delegates to `model_dump()`).                  |
| `from_dict(data)` | Class method. Deserialize state from a dictionary (delegates to `model_validate()`).  |

### `StateField`

Creates a Pydantic field that is automatically wrapped in a reactive descriptor.

```python
# With a scalar default
name: str = StateField(default="")

# With Pydantic constraints
age: int = StateField(default=0, ge=0, le=150)

# With a factory for mutable defaults (required for lists, dicts, etc.)
items: List[str] = StateField(default_factory=list)

# Required field — no default, must be supplied at construction
user_id: str = StateField()
```

All standard Pydantic `Field` keyword arguments are supported and forwarded.

### `StateManager`

Thread-safe singleton registry for global state instances.

```python
from solara_state import StateManager, get_state, reset_state, clear_all_states

# Module-level helpers use a shared global manager
state = get_state(AppState)       # Get or create singleton
reset_state(AppState)             # Reset to defaults (instance is kept)
clear_all_states()                # Remove all managed instances

# Or use your own manager for isolated scopes (e.g. testing)
manager = StateManager()
state = manager.get_state(AppState)
manager.reset_state(AppState)
manager.clear_all()
```

`StateManager` is safe to call from multiple threads simultaneously.

## Examples

### Custom validation and type coercion

Pydantic validators run on every write, whether through the reactive ref or direct assignment:

```python
class UserState(BaseState):
    email: str = StateField(default="")

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email address')
        return v.lower()  # Coercion is applied automatically

state = UserState()
state.email.value = "User@Example.COM"
print(state.email.value)  # "user@example.com"

state.email.value = "not-an-email"  # raises ValidationError
```

### Nested state

```python
class ProfileState(BaseState):
    display_name: str = StateField(default="")
    bio: str = StateField(default="")

class AppState(BaseState):
    profile: ProfileState = StateField(default_factory=ProfileState)
    is_logged_in: bool = StateField(default=False)

state = AppState()
state.profile.value.display_name.value = "Ada"
```

### Serialization

```python
state = get_state(AppState)
data = state.to_dict()          # {'counter': 0, 'items': []}
restored = AppState.from_dict(data)
```

### Local (component-scoped) state

Each component instance gets its own independent state when you instantiate directly instead of using `get_state`:

```python
@solara.component
def LocalCounter():
    state = CounterState(count=10)  # not a singleton

    with solara.Column():
        solara.Text(f"Local count: {state.count.value}")
        if solara.Button("Increment").clicked:
            state.count.value += 1
```

### Complete Todo example

```python
import solara
from typing import List
from pydantic import field_validator
from solara_state import BaseState, StateField, get_state


class TodoState(BaseState):
    items: List[dict] = StateField(default_factory=list)
    filter_status: str = StateField(default="all")
    new_item_text: str = StateField(default="")

    @field_validator('filter_status')
    @classmethod
    def validate_status(cls, v):
        if v not in ("all", "active", "completed"):
            raise ValueError("Invalid filter status")
        return v


@solara.component
def TodoApp():
    state = get_state(TodoState)
    items = state.items
    filter_status = state.filter_status
    new_item_text = state.new_item_text

    def add_item():
        text = new_item_text.value.strip()
        if text:
            items.value = items.value + [{'id': len(items.value), 'text': text, 'completed': False}]
            new_item_text.value = ""

    def toggle_item(item_id):
        items.value = [
            {**item, 'completed': not item['completed']} if item['id'] == item_id else item
            for item in items.value
        ]

    visible = [
        item for item in items.value
        if filter_status.value == "all"
        or (filter_status.value == "active" and not item['completed'])
        or (filter_status.value == "completed" and item['completed'])
    ]

    with solara.Column():
        with solara.Row():
            solara.InputText("New item...", value=new_item_text)
            solara.Button("Add", on_click=add_item, disabled=not new_item_text.value.strip())

        with solara.Row():
            for status in ("all", "active", "completed"):
                solara.Button(
                    status.title(),
                    color="primary" if filter_status.value == status else "secondary",
                    on_click=lambda s=status: setattr(filter_status, 'value', s),
                )

        for item in visible:
            with solara.Row():
                solara.Checkbox(value=item['completed'], on_value=lambda _, id=item['id']: toggle_item(id))
                solara.Text(item['text'])
```

## Known limitations

- `update()` applies fields sequentially, so subscribers may observe intermediate state if multiple fields are updated together. This will be addressed in a future release.
- Validators that transform values (e.g. normalising strings) are applied correctly, but the reactive ref is updated after the fact, meaning the raw value briefly passes through the ref before being replaced with the coerced value.

## License

MIT