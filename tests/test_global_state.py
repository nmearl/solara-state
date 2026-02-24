import pytest
import solara
from solara_state import get_state, BaseState, StateField


class GlobalTestState(BaseState):
    counter: int = StateField(default=0)


class TestGlobalState:
    
    def test_global_get_state(self, clear_state_manager):
        """Test global get_state function"""
        state = get_state(GlobalTestState)
        
        assert isinstance(state, GlobalTestState)
        assert state._field_values['counter'] == 0
    
    def test_global_state_persistence(self, clear_state_manager):
        """Test that global state persists across calls"""
        state1 = get_state(GlobalTestState)
        state1.update(counter=42)
        
        state2 = get_state(GlobalTestState)
        
        assert state1 is state2
        assert state2._field_values['counter'] == 42
    
    def test_reactive_refs_work_globally(self, clear_state_manager):
        """Test that reactive refs work with global state"""
        state = get_state(GlobalTestState)
        counter_ref = state.counter
        
        assert isinstance(counter_ref, solara.Reactive)
        
        counter_ref.value = 100
        assert state._field_values['counter'] == 100