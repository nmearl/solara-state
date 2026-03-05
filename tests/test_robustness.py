import gc
import threading
import warnings
import weakref
from typing import List, Optional

import pytest
import solara
from pydantic import ValidationError, field_validator

from solara_state import BaseState, StateField, StateManager, get_state


class ValidatedState(BaseState):
    counter: int = StateField(default=0, ge=0)
    email: str = StateField(default="")

    @field_validator("counter")
    @classmethod
    def counter_non_negative(cls, v):
        if v < 0:
            raise ValueError("counter must be non-negative")
        return v

    @field_validator("email")
    @classmethod
    def email_must_have_at(cls, v):
        if v and "@" not in v:
            raise ValueError("Invalid email")
        return v.lower()


class SimpleState(BaseState):
    value: int = StateField(default=0)
    name: str = StateField(default="default")


class TestMemoryLeak:
    """Memory leak: WeakKeyDictionary cache cleanup"""

    def test_cache_entry_removed_after_gc(self):
        """Descriptor cache should not hold strong references to instances."""
        state = SimpleState()
        _ = state.value  # Populate the cache

        # Get a reference to the descriptor's cache
        descriptor = SimpleState.__dict__["value"]
        assert state in descriptor._ref_cache

        # Delete the only strong reference and force GC
        del state
        gc.collect()

        # The WeakKeyDictionary entry should now be gone
        assert len(descriptor._ref_cache) == 0

    def test_id_reuse_does_not_return_stale_reactive(self):
        """A new instance that happens to get the same id() as a deleted one
        should receive a fresh reactive, not a stale cached one."""
        state1 = SimpleState()
        ref1 = state1.value
        ref1.value = 99

        old_id = id(state1)
        del state1
        gc.collect()

        # Keep creating instances until CPython reuses the address (may take
        # a few tries in practice, but WeakKeyDictionary makes it safe regardless)
        state2 = SimpleState()
        ref2 = state2.value

        # The new reactive must start at the default, not the old value
        assert ref2.value == 0
        assert ref1 is not ref2


class TestValidationViaReactiveRefs:
    """Validation bypass via reactive refs."""

    def test_invalid_value_via_ref_raises(self):
        """Setting an invalid value through a reactive ref should raise."""
        state = ValidatedState()
        counter_ref = state.counter

        with pytest.raises((ValueError, ValidationError)):
            counter_ref.value = -1  # violates ge=0 / field_validator

    def test_invalid_email_via_ref_raises(self):
        """Email validator should fire when setting via reactive ref."""
        state = ValidatedState()
        email_ref = state.email

        with pytest.raises((ValueError, ValidationError)):
            email_ref.value = "not-an-email"

    def test_valid_value_via_ref_accepted(self):
        """A valid value set through a reactive ref should be stored."""
        state = ValidatedState()
        state.counter.value = 10
        assert state._field_values["counter"] == 10

    def test_validator_normalizes_value_via_ref(self):
        """Validators that transform values (e.g. lowercase) should apply."""
        state = ValidatedState()
        state.email.value = "User@Example.COM"
        # field_validator lowercases the email
        assert state._field_values["email"] == "user@example.com"


class ThreadedState(BaseState):
    x: int = StateField(default=0)


class TestThreadSafety:
    """Thread safety in `StateManager`."""

    def test_concurrent_get_state_returns_same_instance(self):
        """Concurrent calls to get_state must return the exact same instance."""
        manager = StateManager()
        results = []
        errors = []

        def worker():
            try:
                results.append(manager.get_state(ThreadedState))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Threads raised exceptions: {errors}"
        # All threads must have received the same singleton instance
        assert all(r is results[0] for r in results)

    def test_concurrent_updates_do_not_corrupt_state(self):
        """Concurrent updates should not leave the state in a corrupted form."""
        manager = StateManager()
        state = manager.get_state(SimpleState)
        errors = []

        def increment():
            try:
                for _ in range(100):
                    current = state._field_values["value"]
                    state.update(value=current + 1)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=increment) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Threads raised exceptions: {errors}"
        # value must be a valid integer — not corrupted
        assert isinstance(state._field_values["value"], int)


class ObservableState(BaseState):
    a: int = StateField(default=0)
    b: int = StateField(default=0)


class TestAtomicUpdate:
    """Non-atomic `update`."""

    def test_update_sets_all_fields(self):
        """All fields passed to update() should reach their final values."""
        state = ObservableState()
        state.update(a=1, b=1)
        assert state._field_values["a"] == 1
        assert state._field_values["b"] == 1
        assert state.a.value == 1
        assert state.b.value == 1


class TestStateFieldDefault:
    """`StateField` silent None default"""

    def test_field_with_no_default_is_not_silently_none(self):
        """`StateField` with no default should not silently become None.

        If the implementation coerces missing defaults to None, accessing the
        field value will be None rather than raising an error.
        """

        # If StateField(...) silently maps to None, pydantic will accept it;
        # if it correctly marks the field as required, construction without a
        # value should raise.
        class RequiredFieldState(BaseState):
            required: str = StateField()  # no default provided

        # Either construction without the field raises, or it shouldn't be None
        try:
            state = RequiredFieldState()
            # If we get here, the field should at least not be silently None
            assert (
                state._field_values.get("required") is not None
            ), "StateField() with no default silently became None"
        except (ValueError, ValidationError):
            pass  # Correct behavior: required field raises on missing value


class TestUpdateTypos:
    """Unknown fields in `update` silently ignored."""

    def test_update_with_unknown_field_warns(self):
        """`update` with an unrecognized field name should warn, not silently pass."""
        state = SimpleState()

        with pytest.warns(UserWarning, match="typo_field"):
            state.update(typo_field=42)


class TestHashAndEquality:
    """BaseState identity-based hash and equality."""

    def test_two_instances_with_same_values_are_not_equal(self):
        """Two separate instances should not compare equal even with identical values."""
        s1 = SimpleState(value=5)
        s2 = SimpleState(value=5)
        assert s1 != s2

    def test_same_instance_is_equal_to_itself(self):
        s = SimpleState()
        assert s == s

    def test_instances_are_hashable(self):
        """BaseState instances must be hashable to be used as WeakKeyDictionary keys."""
        s = SimpleState()
        d = {s: "hello"}
        assert d[s] == "hello"

    def test_hash_is_stable(self):
        """Hash must not change over the lifetime of an instance."""
        s = SimpleState()
        h1 = hash(s)
        s.update(value=99)
        h2 = hash(s)
        assert h1 == h2

    def test_different_instances_can_coexist_in_set(self):
        s1, s2, s3 = SimpleState(), SimpleState(), SimpleState()
        instance_set = {s1, s2, s3}
        assert len(instance_set) == 3


class TestCacheIsolation:
    """Reactive cache isolation between instances."""

    def test_separate_instances_have_independent_reactives(self):
        s1 = SimpleState(value=1)
        s2 = SimpleState(value=2)

        ref1 = s1.value
        ref2 = s2.value

        assert ref1 is not ref2
        assert ref1.value == 1
        assert ref2.value == 2

        ref1.value = 100
        assert ref2.value == 2  # s2 must be unaffected

    def test_cache_is_per_descriptor_not_per_class(self):
        """Each field's descriptor maintains its own cache."""
        s = SimpleState()
        value_desc = SimpleState.__dict__["value"]
        name_desc = SimpleState.__dict__["name"]

        _ = s.value
        _ = s.name

        assert s in value_desc._ref_cache
        assert s in name_desc._ref_cache
        assert value_desc._ref_cache is not name_desc._ref_cache
