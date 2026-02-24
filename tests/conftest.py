import pytest
import solara
import solara.lab

@pytest.fixture
def clear_state_manager():
    """Clear global state manager before each test"""
    from solara_state.manager import _global_manager
    _global_manager.clear_all()
    yield
    _global_manager.clear_all()