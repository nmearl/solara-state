import pytest
from typing import Optional
from pydantic import ValidationError
import solara
from solara_state import BaseState, StateField


class SampleState(BaseState):
    counter: int = StateField(default=0)
    message: str = StateField(default="hello")
    is_active: bool = StateField(default=True)
    optional_field: Optional[str] = StateField(default=None)


class TestBaseState:
    
    def test_state_creation(self):
        """Test basic state creation with defaults"""
        state = SampleState()
        
        assert hasattr(state, '_field_values')
        assert state._field_values['counter'] == 0
        assert state._field_values['message'] == "hello"
        assert state._field_values['is_active'] is True
        assert state._field_values['optional_field'] is None
    
    def test_state_creation_with_values(self):
        """Test state creation with initial values"""
        state = SampleState(counter=5, message="test", is_active=False)
        
        assert state._field_values['counter'] == 5
        assert state._field_values['message'] == "test"
        assert state._field_values['is_active'] is False
    
    def test_reactive_property_access(self):
        """Test that property access returns Reactive objects"""
        state = SampleState()
        
        counter_ref = state.counter
        message_ref = state.message
        
        assert isinstance(counter_ref, solara.Reactive)
        assert isinstance(message_ref, solara.Reactive)
        assert counter_ref.value == 0
        assert message_ref.value == "hello"
    
    def test_reactive_property_caching(self):
        """Test that reactive properties are cached per instance"""
        state = SampleState()
        
        ref1 = state.counter
        ref2 = state.counter
        
        assert ref1 is ref2
    
    def test_reactive_property_setting(self):
        """Test setting values through reactive properties"""
        state = SampleState()
        
        state.counter = 10
        assert state._field_values['counter'] == 10
        
        counter_ref = state.counter
        assert counter_ref.value == 10
    
    def test_bidirectional_sync(self):
        """Test bidirectional sync between ref and model"""
        state = SampleState()
        counter_ref = state.counter
        
        # Change through ref should update model
        counter_ref.value = 42
        assert state._field_values['counter'] == 42
        
        # Change through model setter should update ref
        state.counter = 99
        assert counter_ref.value == 99
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        state = SampleState(counter=5, message="test")
        
        data = state.to_dict()
        expected = {
            'counter': 5,
            'message': 'test', 
            'is_active': True,
            'optional_field': None
        }
        assert data == expected
    
    def test_update_method(self):
        """Test bulk update of state fields"""
        state = SampleState()
        
        state.update(counter=100, message="updated", is_active=False)
        
        assert state._field_values['counter'] == 100
        assert state._field_values['message'] == "updated"
        assert state._field_values['is_active'] is False
    
    def test_reset_method(self):
        """Test resetting state to defaults"""
        state = SampleState(counter=100, message="changed")
        
        state.reset()
        
        assert state._field_values['counter'] == 0
        assert state._field_values['message'] == "hello"
        assert state._field_values['is_active'] is True
    
    def test_pydantic_validation(self):
        """Test that Pydantic validation works"""
        with pytest.raises(ValidationError):
            SampleState(counter="invalid")