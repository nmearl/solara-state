import pytest
from typing import Optional
from pydantic import ValidationError, field_validator
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

class NormalizingState(BaseState):
    count: int = StateField(default=0)
    email: str = StateField(default="")

    @field_validator('email')
    @classmethod
    def lowercase_email(cls, v):
        return v.lower()


class TestAttributeAssignmentCoercion:

    def test_attribute_assignment_coerces_type(self):
        """Test that direct assignment stores the coerced value, not the raw input"""
        state = NormalizingState()

        state.count = "5"

        assert state._field_values['count'] == 5
        assert state.count.value == 5
        assert state.to_dict()['count'] == 5

    def test_attribute_assignment_applies_validator_transform(self):
        """Test that direct assignment stores the validator's transformed value"""
        state = NormalizingState()

        state.email = "User@Example.COM"

        assert state._field_values['email'] == "user@example.com"
        assert state.email.value == "user@example.com"

    def test_update_applies_coercion(self):
        """Test that update() stores coerced and transformed values"""
        state = NormalizingState()

        state.update(count="7", email="A@B.COM")

        assert state.to_dict() == {'count': 7, 'email': "a@b.com"}

    def test_attribute_and_ref_assignment_agree(self):
        """Test that both write paths produce identical stored values"""
        via_attr = NormalizingState()
        via_ref = NormalizingState()

        via_attr.email = "MiXeD@Case.com"
        via_ref.email.value = "MiXeD@Case.com"

        assert via_attr.to_dict() == via_ref.to_dict()
