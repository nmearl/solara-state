import pytest
import solara
from solara_state import BaseState, StateField


class EdgeCaseState(BaseState):
    public_field: int = StateField(default=0)
    _internal: str = "internal"


class TestEdgeCases:
    
    def test_private_fields_not_reactive(self):
        """Test that private fields (starting with _) are not made reactive"""
        state = EdgeCaseState()
        
        # Public field should be reactive
        assert isinstance(state.public_field, solara.Reactive)
        
        # Private field should remain normal
        assert state._internal == "internal"
        assert not isinstance(state._internal, solara.Reactive)
    
    def test_nonexistent_field_update(self):
        """Test updating nonexistent field doesn't crash"""
        state = EdgeCaseState()
        
        state.update(nonexistent_field="value")  # Should not raise
    
    def test_state_without_fields(self):
        """Test state class with no defined fields"""
        class EmptyState(BaseState):
            pass
        
        state = EmptyState()
        assert hasattr(state, '_field_values')
    
    def test_multiple_instances_separate_caches(self):
        """Test that different instances have separate reactive caches"""
        state1 = EdgeCaseState()
        state2 = EdgeCaseState()
        
        ref1 = state1.public_field
        ref2 = state2.public_field
        
        assert ref1 is not ref2
        
        # Changes to one shouldn't affect the other
        ref1.value = 100
        assert ref2.value == 0
    
    def test_reactive_subscription_cleanup(self):
        """Test that reactive subscriptions work correctly"""
        state = EdgeCaseState()
        ref = state.public_field
        
        # Change via ref should sync to field values
        ref.value = 50
        assert state._field_values['public_field'] == 50
        
        # Change via setter should sync to ref
        state.public_field = 75
        assert ref.value == 75