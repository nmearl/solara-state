import threading
from typing import Dict, Type, TypeVar, Optional
from .state import BaseState

StateType = TypeVar("StateType", bound=BaseState)


class StateManager:
    """Manages global state instances across the application."""

    def __init__(self):
        self._states: Dict[Type[BaseState], BaseState] = {}
        self._lock = threading.Lock()

    def get_state(self, state_class: Type[StateType]) -> StateType:
        """Get or create a global state instance."""
        with self._lock:
            if state_class not in self._states:
                self._states[state_class] = state_class()
            return self._states[state_class]

    def reset_state(self, state_class: Type[StateType]):
        """Reset a specific state to its default values."""
        with self._lock:
            if state_class in self._states:
                self._states[state_class].reset()

    def clear_all(self):
        """Clear all managed states."""
        with self._lock:
            self._states.clear()


# Global state manager instance
_global_manager = StateManager()


def get_state(state_class: Type[StateType]) -> StateType:
    """Get a global state instance."""
    return _global_manager.get_state(state_class)


def reset_state(state_class: Type[StateType]):
    """Reset a global state instance."""
    _global_manager.reset_state(state_class)


def clear_all_states():
    """Clear all global state instances."""
    _global_manager.clear_all()
