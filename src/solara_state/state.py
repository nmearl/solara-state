from typing import Any, Dict, Optional, Type, TypeVar, Generic, get_type_hints
from pydantic import BaseModel, Field
import solara
import solara.lab
from solara import Reactive

T = TypeVar('T')


class ReactiveDescriptor(Generic[T]):
    """Descriptor that wraps field access in Solara Ref objects."""

    def __init__(self, field_name: str, default_value: T):
        self.field_name = field_name
        self.default_value = default_value
        self._ref_cache: Dict[int, Reactive[T]] = {}

    def __get__(self, instance, owner) -> Reactive[T]:
        if instance is None:
            return self

        instance_id = id(instance)

        # Return cached Ref if it exists
        if instance_id in self._ref_cache:
            return self._ref_cache[instance_id]

        # Get current value from field values
        current_value = instance._field_values.get(self.field_name, self.default_value)

        # Create new reactive and cache it
        ref = solara.reactive(current_value)

        # Set up bidirectional sync
        def sync_to_model(new_value):
            instance._field_values[self.field_name] = new_value
            # Update pydantic's __dict__ directly to avoid recursion
            instance.__dict__[self.field_name] = new_value

        # Watch for changes and sync to model
        ref.subscribe(sync_to_model)

        self._ref_cache[instance_id] = ref
        return ref

    def __set__(self, instance, value: T):
        # Update field values first
        instance._field_values[self.field_name] = value
        # Update pydantic's __dict__ directly to avoid recursion
        instance.__dict__[self.field_name] = value

        # Update cached ref if it exists, but avoid triggering sync callback
        instance_id = id(instance)
        if instance_id in self._ref_cache:
            ref = self._ref_cache[instance_id]
            # Use the reactive's internal method to avoid triggering subscribers
            ref._storage.set(value)


def StateField(default: T = ..., **kwargs) -> T:
    """Create a reactive state field with Pydantic validation."""
    # Only pass default if it's explicitly provided and default_factory isn't
    if default is not ... and 'default_factory' not in kwargs:
        return Field(default=default, **kwargs)
    elif 'default_factory' in kwargs:
        return Field(**kwargs)
    else:
        return Field(default=None, **kwargs)


class BaseStateMeta(type(BaseModel)):
    """Metaclass to create reactive descriptors for state fields."""

    def __new__(cls, name, bases, namespace):
        # Create the class first
        new_class = super().__new__(cls, name, bases, namespace)

        # Only process if this class has pydantic fields
        if hasattr(new_class, 'model_fields') and new_class.model_fields:
            # Get field information from pydantic
            for field_name, field_info in new_class.model_fields.items():
                if not field_name.startswith('_'):
                    # Get default value from field definition
                    default_value = field_info.default if field_info.default is not ... else None

                    # Create reactive descriptor
                    descriptor = ReactiveDescriptor(field_name, default_value)
                    setattr(new_class, field_name, descriptor)

        return new_class


class BaseState(BaseModel, metaclass=BaseStateMeta):
    """Base class for reactive state objects."""

    def __init__(self, **data):
        super().__init__(**data)
        # Initialize field values directly from pydantic's __dict__ to avoid descriptors
        self._field_values = {}
        for field_name in self.__class__.model_fields:
            # Get value directly from __dict__ which contains pydantic's stored values
            self._field_values[field_name] = self.__dict__.get(field_name)

    def __setattr__(self, name, value):
        # If it's a field with a descriptor, validate first then use the descriptor
        if hasattr(self.__class__, name) and isinstance(getattr(self.__class__, name), ReactiveDescriptor):
            # Run pydantic validation first
            if name in self.__class__.model_fields:
                # Create a temporary dict with the new value to validate, using actual values not reactive objects
                temp_dict = self._field_values.copy()
                temp_dict[name] = value
                # This will raise ValidationError if invalid
                self.__class__(**temp_dict)

            getattr(self.__class__, name).__set__(self, value)
        else:
            # Otherwise, use normal pydantic setattr
            super().__setattr__(name, value)

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create state from dictionary."""
        return cls.model_validate(data)

    def update(self, **kwargs):
        """Update multiple state fields at once."""
        for key, value in kwargs.items():
            if key in self.__class__.model_fields:
                setattr(self, key, value)

    def reset(self):
        """Reset state to default values."""
        for field_name, field_info in self.__class__.model_fields.items():
            if field_info.default_factory:
                default_value = field_info.default_factory()
            elif field_info.default is not ...:
                default_value = field_info.default
            else:
                default_value = None
            setattr(self, field_name, default_value)