from typing import Any, Dict, TypeVar, Generic
from pydantic import BaseModel, Field
import solara
from solara import Reactive
import weakref
import warnings

T = TypeVar("T")


def current_kernel_context():
    """
    Return the active Solara virtual kernel context, or None. Context
    is preserved when using a server.
    """
    if not solara._using_solara_server():
        return None

    from solara.server import kernel_context

    if not kernel_context.has_current_context():
        return None
    return kernel_context.get_current_context()


class ReactiveDescriptor(Generic[T]):
    """Descriptor that wraps field access in Solara Ref objects."""

    def __init__(self, field_name: str, default_value: T):
        self.field_name = field_name
        self.default_value = default_value
        self._ref_cache: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

    def __get__(self, instance, owner) -> Reactive[T]:
        if instance is None:
            return self

        if instance in self._ref_cache:
            return self._ref_cache[instance]

        current_value = instance._field_values.get(self.field_name, self.default_value)
        ref = solara.reactive(current_value)

        # Weak reference avoids keeping the instance alive (fixes GC / memory leak)
        instance_ref = weakref.ref(instance)
        _syncing = [False]  # list so the nested function can mutate it

        def sync_to_model(new_value):
            if _syncing[0]:
                return
            inst = instance_ref()
            if inst is None:
                return

            # Validate via Pydantic; raises ValidationError on bad values
            validated = inst.__class__.model_validate(
                {**inst._field_values, self.field_name: new_value}
            )

            # Use _field_values on the validated instance, which
            # would return a Reactive via the descriptor
            clean_value = validated._field_values[self.field_name]

            inst._field_values[self.field_name] = clean_value
            inst.__dict__[self.field_name] = clean_value

            # If the validator transformed the value (e.g. lowercased a string),
            # sync the corrected value back to the reactive without re-entering
            if clean_value != new_value:
                _syncing[0] = True
                try:
                    ref.value = clean_value
                finally:
                    _syncing[0] = False

        disposer = ref.subscribe(sync_to_model)

        # Store the syncing flag so __set__ can push already-validated values
        # to the ref without re-entering sync_to_model
        if not hasattr(instance, "_sync_disposers"):
            instance.__dict__["_sync_disposers"] = {}
        instance.__dict__["_sync_disposers"][self.field_name] = (
            _syncing,
            disposer,
        )

        # Unsubscribe when the Solara session that owns this ref shuts down.
        # Registered after subscribing so it runs before Solara's leak check.
        context = current_kernel_context()
        if context is not None:
            context.on_close(lambda: self._dispose(instance_ref()))

        self._ref_cache[instance] = ref
        return ref

    def _dispose(self, instance):
        """Remove the instance's sync subscription and cached ref for this field."""
        if instance is None:
            return
        entry = instance.__dict__.get("_sync_disposers", {}).pop(self.field_name, None)
        if entry is not None:
            _, disposer = entry
            disposer()
        self._ref_cache.pop(instance, None)

    def __set__(self, instance, value: T):
        instance._field_values[self.field_name] = value
        instance.__dict__[self.field_name] = value

        if instance in self._ref_cache:
            ref = self._ref_cache[instance]
            sync_disposers = instance.__dict__.get("_sync_disposers", {})

            if self.field_name in sync_disposers:
                syncing, _ = sync_disposers[self.field_name]
                syncing[0] = True  # Value is already validated; skip sync_to_model
                try:
                    ref.value = value
                finally:
                    syncing[0] = False
            else:
                ref.value = value


def StateField(default: T = ..., **kwargs) -> T:
    """Create a reactive state field with Pydantic validation."""
    # Only pass default if it's explicitly provided and default_factory isn't
    if "default_factory" in kwargs:
        return Field(**kwargs)
    elif default is not ...:
        return Field(default=default, **kwargs)
    else:
        # If no default provied, let Pydantic treat it as a required field
        # rather than silently coercing to None
        return Field(**kwargs)


class BaseStateMeta(type(BaseModel)):
    """Metaclass to create reactive descriptors for state fields."""

    def __new__(cls, name, bases, namespace):
        # Create the class first
        new_class = super().__new__(cls, name, bases, namespace)

        # Only process if this class has pydantic fields
        if hasattr(new_class, "model_fields") and new_class.model_fields:
            # Get field information from pydantic
            for field_name, field_info in new_class.model_fields.items():
                if not field_name.startswith("_"):
                    # Get default value from field definition
                    default_value = (
                        field_info.default if field_info.default is not ... else None
                    )

                    # Create reactive descriptor
                    descriptor = ReactiveDescriptor(field_name, default_value)
                    setattr(new_class, field_name, descriptor)

        return new_class


class BaseState(BaseModel, metaclass=BaseStateMeta):
    """Base class for reactive state objects."""

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, **data):
        super().__init__(**data)
        # Initialize field values directly from pydantic's __dict__ to avoid descriptors
        self._field_values = {}
        for field_name in self.__class__.model_fields:
            # Get value directly from __dict__ which contains pydantic's stored values
            self._field_values[field_name] = self.__dict__.get(field_name)

    def __setattr__(self, name, value):
        # If it's a field with a descriptor, validate first then use the descriptor
        if hasattr(self.__class__, name) and isinstance(
            getattr(self.__class__, name), ReactiveDescriptor
        ):
            # Run pydantic validation first
            if name in self.__class__.model_fields:
                # Create a temporary dict with the new value to validate, using actual values not reactive objects
                temp_dict = self._field_values.copy()
                temp_dict[name] = value
                # This will raise ValidationError if invalid
                validated = self.__class__.model_validate(temp_dict)
                # Store the coerced/transformed value, not the raw input
                value = validated._field_values[name]

            getattr(self.__class__, name).__set__(self, value)
        else:
            # Otherwise, use normal pydantic setattr
            super().__setattr__(name, value)

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other

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
            if key not in self.__class__.model_fields:
                warnings.warn(
                    f"'{key}' is not a field of {self.__class__.__name__} and will be ignored.",
                    UserWarning,
                    stacklevel=2,
                )
            else:
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
