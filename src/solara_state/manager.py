import threading
from typing import Dict, Type, TypeVar
from .state import BaseState, current_kernel_context

StateType = TypeVar("StateType", bound=BaseState)

# Scope used outside a Solara server session (scripts, Jupyter, tests)
GLOBAL_SCOPE = "global"


class StateManager:
    """Manages state instances with one per state class per Solara session."""

    def __init__(self):
        self._states: Dict[str, Dict[Type[BaseState], BaseState]] = {}
        self._lock = threading.Lock()

    def _scope_states(self) -> Dict[Type[BaseState], BaseState]:
        """Get the state registry for the current scope, creating it if needed.

        Must be called with ``self._lock`` held.
        """
        context = current_kernel_context()
        scope = context.id if context is not None else GLOBAL_SCOPE

        if scope not in self._states:
            self._states[scope] = {}
            if context is not None:
                # Drop the session's states when its kernel shuts down
                context.on_close(lambda: self._drop_scope(scope))
        return self._states[scope]

    def _drop_scope(self, scope: str):
        with self._lock:
            self._states.pop(scope, None)

    def get_state(self, state_class: Type[StateType]) -> StateType:
        """Get or create the state instance for the current session."""
        with self._lock:
            states = self._scope_states()
            if state_class not in states:
                states[state_class] = state_class()
            return states[state_class]

    def reset_state(self, state_class: Type[StateType]):
        """Reset a specific state in the current session to its default values."""
        with self._lock:
            state = self._scope_states().get(state_class)
        # Reset outside the lock: subscribers notified by reset() may call get_state()
        if state is not None:
            state.reset()

    def clear_all(self):
        """Clear all managed states across every session."""
        with self._lock:
            self._states.clear()


# Global state manager instance
_global_manager = StateManager()


def get_state(state_class: Type[StateType]) -> StateType:
    """Get the state instance for the current session."""
    return _global_manager.get_state(state_class)


def reset_state(state_class: Type[StateType]):
    """Reset the current session's state instance."""
    _global_manager.reset_state(state_class)


def clear_all_states():
    """Clear all state instances across every session."""
    _global_manager.clear_all()
