import pytest
from solara_state import StateManager, BaseState, StateField
from solara_state.manager import GLOBAL_SCOPE


class AppState(BaseState):
    value: int = StateField(default=1)


class UserState(BaseState):
    name: str = StateField(default="anonymous")


class TestStateManager:
    
    def test_manager_creation(self):
        """Test state manager creation"""
        manager = StateManager()
        assert manager._states == {}
    
    def test_get_state_creates_instance(self):
        """Test that get_state creates new instance if not exists"""
        manager = StateManager()
        
        state = manager.get_state(AppState)
        
        assert isinstance(state, AppState)
        assert AppState in manager._states[GLOBAL_SCOPE]
        assert state._field_values['value'] == 1
    
    def test_get_state_returns_same_instance(self):
        """Test that get_state returns same instance on subsequent calls"""
        manager = StateManager()
        
        state1 = manager.get_state(AppState)
        state2 = manager.get_state(AppState)
        
        assert state1 is state2
    
    def test_multiple_state_types(self):
        """Test managing multiple different state types"""
        manager = StateManager()
        
        app_state = manager.get_state(AppState)
        user_state = manager.get_state(UserState)
        
        assert isinstance(app_state, AppState)
        assert isinstance(user_state, UserState)
        assert app_state is not user_state
    
    def test_reset_state(self):
        """Test resetting specific state type"""
        manager = StateManager()
        
        state = manager.get_state(AppState)
        state.update(value=99)
        
        manager.reset_state(AppState)
        
        assert state._field_values['value'] == 1
    
    def test_clear_all(self):
        """Test clearing all managed states"""
        manager = StateManager()
        
        manager.get_state(AppState)
        manager.get_state(UserState)
        
        assert len(manager._states[GLOBAL_SCOPE]) == 2
        
        manager.clear_all()
        
        assert len(manager._states) == 0