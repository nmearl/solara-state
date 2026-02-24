import pytest
from typing import List, Optional
from pydantic import field_validator
import solara
from solara_state import BaseState, StateField, get_state


class ComplexState(BaseState):
    items: List[str] = StateField(default_factory=list)
    count: int = StateField(default=0)
    metadata: Optional[dict] = StateField(default=None)
    
    @field_validator('count')
    @classmethod
    def count_must_be_positive(cls, v):
        if v < 0:
            raise ValueError('count must be non-negative')
        return v


class TestIntegration:
    
    def test_complex_state_with_validation(self, clear_state_manager):
        """Test state with complex types and validation"""
        state = ComplexState(items=["a", "b"], count=5)
        
        assert state._field_values['items'] == ["a", "b"]
        assert state._field_values['count'] == 5
        
        with pytest.raises(ValueError):
            state.update(count=-1)
    
    def test_state_field_factory(self, clear_state_manager):
        """Test StateField with default_factory"""
        state = ComplexState()
        
        assert state._field_values['items'] == []
        
        state2 = ComplexState()
        assert state._field_values['items'] is not state2._field_values['items']
    
    def test_reactive_complex_types(self, clear_state_manager):
        """Test reactive behavior with complex types"""
        state = ComplexState()
        
        items_ref = state.items
        count_ref = state.count
        
        assert isinstance(items_ref, solara.Reactive)
        assert isinstance(count_ref, solara.Reactive)
        assert items_ref.value == []
        assert count_ref.value == 0
    
    def test_end_to_end_workflow(self, clear_state_manager):
        """Test complete workflow from creation to updates"""
        state = get_state(ComplexState)
        
        items_ref = state.items
        count_ref = state.count
        
        # Update through state methods
        state.update(items=["item1"], count=1)
        
        assert state._field_values['items'] == ["item1"]
        assert state._field_values['count'] == 1
        assert items_ref.value == ["item1"]
        assert count_ref.value == 1
        
        # Update through reactive refs
        count_ref.value = 10
        assert state._field_values['count'] == 10
        
        # Reset
        state.reset()
        assert state._field_values['items'] == []
        assert state._field_values['count'] == 0
        assert items_ref.value == []
        assert count_ref.value == 0

    def test_nested_reactive_state(self, clear_state_manager):
        """Test nested BaseState objects are reactive"""

        class NestedItem(BaseState):
            name: str = StateField(default="item")
            value: int = StateField(default=0)

        class ParentState(BaseState):
            item: NestedItem = StateField(default_factory=NestedItem)
            items: List[NestedItem] = StateField(default_factory=list)

        state = ParentState()

        # Test nested object properties are reactive
        assert isinstance(state.item.value.name, solara.Reactive)
        assert isinstance(state.item.value.value, solara.Reactive)
        assert state.item.value.name.value == "item"
        assert state.item.value.value.value == 0

        # Test changes sync correctly
        state.item.value.name.value = "updated"
        assert state.item.value.name.value == "updated"
        assert state._field_values['item'].name.value == "updated"

        # Test nested list
        new_item = NestedItem(name="test", value=42)
        state.items.value = [new_item]

        assert len(state.items.value) == 1
        assert isinstance(state.items.value[0].name, solara.Reactive)
        assert state.items.value[0].name.value == "test"
        assert state.items.value[0].value.value == 42

    def test_json_serialization(self, clear_state_manager):
        """Test serializing and deserializing state to/from JSON including nested states"""
        import json

        # Define nested state classes
        class NestedItem(BaseState):
            name: str = StateField(default="item")
            value: int = StateField(default=0)

        class ComplexStateWithNested(BaseState):
            items: List[str] = StateField(default_factory=list)
            count: int = StateField(default=0)
            nested_item: NestedItem = StateField(default_factory=NestedItem)
            nested_items: List[NestedItem] = StateField(default_factory=list)

        # Create state with nested data
        state = ComplexStateWithNested(
            items=["item1", "item2"],
            count=5,
            nested_item=NestedItem(name="nested", value=100),
            nested_items=[
                NestedItem(name="first", value=1),
                NestedItem(name="second", value=2)
            ]
        )

        # Serialize to JSON
        state_dict = state.to_dict()
        json_data = json.dumps(state_dict)

        # Deserialize from JSON using from_dict method
        loaded_dict = json.loads(json_data)
        new_state = ComplexStateWithNested.from_dict(loaded_dict)

        # Verify basic data matches
        assert new_state._field_values['items'] == ["item1", "item2"]
        assert new_state._field_values['count'] == 5

        # Verify nested single object
        assert new_state.nested_item.value.name.value == "nested"
        assert new_state.nested_item.value.value.value == 100
        assert isinstance(new_state.nested_item.value.name, solara.Reactive)

        # Verify nested list
        assert len(new_state.nested_items.value) == 2
        assert new_state.nested_items.value[0].name.value == "first"
        assert new_state.nested_items.value[0].value.value == 1
        assert new_state.nested_items.value[1].name.value == "second"
        assert new_state.nested_items.value[1].value.value == 2

        # Verify reactivity still works on deserialized nested states
        new_state.nested_item.value.name.value = "updated"
        assert new_state.nested_item.value.name.value == "updated"

        new_state.nested_items.value[0].value.value = 999
        assert new_state.nested_items.value[0].value.value == 999