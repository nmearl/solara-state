import solara
from solara_state import BaseState, StateField, get_state
from typing import List
from pydantic import field_validator


class TodoItem(BaseState):
    text: str = StateField(default="")
    completed: bool = StateField(default=False)
    id: int = StateField(default=0)


class TodoState(BaseState):
    items: List[TodoItem] = StateField(default_factory=list)
    filter_status: str = StateField(default="all")
    new_item_text: str = StateField(default="")

    @field_validator('filter_status')
    @classmethod
    def validate_status(cls, v):
        if v not in ["all", "active", "completed"]:
            raise ValueError("Invalid filter status")
        return v


@solara.component
def Page():
    state = get_state(TodoState)

    # Reactive refs
    items = state.items
    filter_status = state.filter_status
    new_item_text = state.new_item_text

    # Add new item
    def add_item():
        if new_item_text.value.strip():
            new_todo = TodoItem(
                text=new_item_text.value.strip(),
                completed=False,
                id=len(items.value)
            )
            items.value = items.value + [new_todo]
            new_item_text.value = ""

    # Filter items
    filtered_items = [
        item for item in items.value
        if filter_status.value == "all" or
           (filter_status.value == "active" and not item.completed.value) or
           (filter_status.value == "completed" and item.completed.value)
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
                # Each item has its own reactive completed state
                def on_toggle(value, todo_item=item):
                    todo_item.completed.value = value

                solara.Checkbox(
                    label=item.text.value,
                    value=item.completed,
                    on_value=on_toggle
                )

                # Editable text
                solara.InputText(label=item.text.value, value=item.text, style="margin-left: 10px")

        # Stats
        total = len(items.value)
        completed_count = sum(1 for item in items.value if item.completed.value)
        solara.Text(f"Total: {total}, Completed: {completed_count}, Active: {total - completed_count}")

        # Clear completed
        def clear_completed():
            items.value = [item for item in items.value if not item.completed.value]

        solara.Button("Clear Completed", on_click=clear_completed, disabled=completed_count == 0)

    @solara.lab.computed
    def state_dict():

        return state.to_dict()

    with solara.Column():
        solara.Text(str(state_dict.value), style="margin-top: 20px; font-family: monospace; white-space: pre-wrap;")


# # Run the app
# if __name__ == "__main__":
#     TodoApp()