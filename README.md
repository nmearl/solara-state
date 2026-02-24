# Solara State

A reactive state management framework for Solara apps that combines Pydantic validation with Solara's reactive system.

## Installation

```bash
pip install solara-state
```

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

- **Reactive Properties**: Field access returns `Reactive` objects that automatically trigger UI updates
- **Pydantic Integration**: Full validation, type checking, and serialization support
- **Global State**: Singleton state management with `get_state()`
- **Local State**: Create component-scoped instances
- **Bidirectional Sync**: Changes sync between reactive refs and underlying data

## API Reference

### BaseState

Base class for reactive state objects.

```python
class AppState(BaseState):
    counter: int = StateField(default=0)
    items: List[str] = StateField(default_factory=list)
    
    @field_validator('counter')
    @classmethod
    def validate_counter(cls, v):
        if v < 0:
            raise ValueError('Counter must be non-negative')
        return v

# Usage
state = AppState()
state.counter = 10           # Triggers validation
state.update(counter=5)      # Bulk updates
state.reset()               # Reset to defaults
```

### StateField

Creates reactive state fields with validation.

```python
# Basic field
name: str = StateField(default="default")

# With validation
age: int = StateField(default=0, ge=0, le=150)

# With factory for mutable defaults
items: List[str] = StateField(default_factory=list)
```

### State Manager

```python
from solara_state import get_state, StateManager

# Global state (singleton)
state = get_state(AppState)

# Custom manager
manager = StateManager()
state = manager.get_state(AppState)
manager.reset_state(AppState)
```

## Complete Example

```python
import solara
from solara_state import BaseState, StateField, get_state
from typing import List, Optional
from pydantic import field_validator

class TodoState(BaseState):
    items: List[dict] = StateField(default_factory=list)
    filter_status: str = StateField(default="all")
    new_item_text: str = StateField(default="")
    
    @field_validator('filter_status')
    @classmethod
    def validate_status(cls, v):
        if v not in ["all", "active", "completed"]:
            raise ValueError("Invalid filter status")
        return v

@solara.component
def TodoApp():
    state = get_state(TodoState)
    
    # Reactive refs
    items = state.items
    filter_status = state.filter_status
    new_item_text = state.new_item_text
    
    # Add new item
    def add_item():
        if new_item_text.value.strip():
            items.value = items.value + [{
                'text': new_item_text.value.strip(),
                'completed': False,
                'id': len(items.value)
            }]
            new_item_text.value = ""
    
    # Toggle completion
    def toggle_item(item_id):
        updated_items = []
        for item in items.value:
            if item['id'] == item_id:
                item = {**item, 'completed': not item['completed']}
            updated_items.append(item)
        items.value = updated_items
    
    # Filter items
    filtered_items = [
        item for item in items.value
        if filter_status.value == "all" or 
           (filter_status.value == "active" and not item['completed']) or
           (filter_status.value == "completed" and item['completed'])
    ]
    
    with solara.Column():
        solara.Text("# Todo App", style="margin-bottom: 20px")
        
        # Add new item
        with solara.Row():
            solara.InputText("Add item...", value=new_item_text)
            solara.Button("Add", on_click=add_item, disabled=not new_item_text.value.strip())
        
        # Filter buttons
        with solara.Row():
            for status in ["all", "active", "completed"]:
                color = "primary" if filter_status.value == status else "secondary"
                solara.Button(
                    status.title(), 
                    color=color,
                    on_click=lambda s=status: setattr(filter_status, 'value', s)
                )
        
        # Todo items
        for item in filtered_items:
            with solara.Row():
                completed = solara.use_reactive(item['completed'])
                
                def on_change(value, item_id=item['id']):
                    toggle_item(item_id)
                
                solara.Checkbox(
                    label=item['text'], 
                    value=completed,
                    on_value=on_change
                )
        
        # Stats
        total = len(items.value)
        completed_count = sum(1 for item in items.value if item['completed'])
        solara.Text(f"Total: {total}, Completed: {completed_count}, Active: {total - completed_count}")
        
        # Clear completed
        def clear_completed():
            items.value = [item for item in items.value if not item['completed']]
        
        solara.Button("Clear Completed", on_click=clear_completed, disabled=completed_count == 0)

# Run the app
if __name__ == "__main__":
    TodoApp()
```

## Local State Example

For component-scoped state instead of global:

```python
@solara.component
def LocalCounter():
    # Each component instance gets its own state
    state = CounterState(count=10)  # Local instance
    
    with solara.Column():
        solara.Text(f"Local count: {state.count.value}")
        if solara.Button("Increment").clicked:
            state.count.value += 1
```

## Advanced Features

### Custom Validation

```python
class UserState(BaseState):
    email: str = StateField(default="")
    age: int = StateField(default=0)
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email')
        return v.lower()
```

### Nested State

```python
class ProfileState(BaseState):
    name: str = StateField(default="")
    settings: dict = StateField(default_factory=dict)

class AppState(BaseState):
    profile: ProfileState = StateField(default_factory=ProfileState)
    is_logged_in: bool = StateField(default=False)
```

### Serialization

```python
state = get_state(AppState)
data = state.to_dict()          # Export to dict
new_state = AppState(**data)    # Import from dict
```

## Requirements

- Python 3.8+
- Pydantic 2.0+
- Solara

## License

MIT License