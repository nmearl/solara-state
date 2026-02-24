import pytest
import solara
from solara_state.state import ReactiveDescriptor, BaseState, StateField


class TestReactiveDescriptor:

    def test_descriptor_creation(self):
        """Test descriptor creation with default value"""
        descriptor = ReactiveDescriptor("test_field", 42)

        assert descriptor.field_name == "test_field"
        assert descriptor.default_value == 42
        assert descriptor._ref_cache == {}

    def test_descriptor_get_creates_ref(self):
        """Test that __get__ creates and caches Reactive objects"""

        class RealInstance(BaseState):
            test_field: int = StateField(default=0)

        instance = RealInstance(test_field=10)
        descriptor = RealInstance.__dict__["test_field"]

        ref = descriptor.__get__(instance, None)

        assert isinstance(ref, solara.Reactive)
        assert ref.value == 10
        assert instance in descriptor._ref_cache

    # tests/test_reactive_descriptor.py

    def test_descriptor_set_updates_field_values_and_ref(self):
        """Test that __set__ updates both field values and cached ref"""

        class RealInstance(BaseState):
            test_field: int = StateField(default=0)

        instance = RealInstance()
        descriptor = RealInstance.__dict__["test_field"]

        ref = instance.test_field  # populate cache

        instance.test_field = 99

        assert instance._field_values["test_field"] == 99
        assert ref.value == 99
