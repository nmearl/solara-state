import asyncio
import warnings
import pytest
from pydantic import ValidationError
from solara_state import BaseState, StateField, StateManager, get_state, reset_state
from solara_state.manager import GLOBAL_SCOPE


class SessionState(BaseState):
    count: int = StateField(default=0, ge=0)
    name: str = StateField(default="anonymous")


@pytest.fixture
def make_session():
    """Create Solara virtual kernel contexts, each standing in for a browser session"""
    # Importing the server module makes Solara scope reactive values per kernel,
    # exactly as it does under `solara run`
    with warnings.catch_warnings():
        # Third-party deprecation noise (e.g. websockets.legacy) on import
        warnings.simplefilter("ignore", DeprecationWarning)
        import solara.server.starlette  # noqa: F401
    from solara.server import kernel, kernel_context

    created = []

    def factory(session_id):
        context = kernel_context.VirtualKernelContext(
            id=session_id,
            session_id=session_id,
            kernel=kernel.Kernel(),
            event_loop=asyncio.new_event_loop(),
        )
        created.append(context)
        return context

    yield factory

    for context in created:
        if not context.closed_event.is_set():
            context.close()
        context.event_loop.close()


class TestPerSessionState:

    def test_sessions_get_distinct_instances(self, clear_state_manager, make_session):
        """Test that each session gets its own state instance"""
        session_a, session_b = make_session("a"), make_session("b")

        with session_a:
            state_a = get_state(SessionState)
            assert get_state(SessionState) is state_a
        with session_b:
            state_b = get_state(SessionState)

        assert state_a is not state_b

    def test_writes_do_not_leak_between_sessions(self, clear_state_manager, make_session):
        """Test that one session's writes are invisible to another session"""
        session_a, session_b = make_session("a"), make_session("b")

        with session_a:
            get_state(SessionState).count.value = 5
        with session_b:
            state_b = get_state(SessionState)
            assert state_b.count.value == 0
            assert state_b.to_dict() == {'count': 0, 'name': "anonymous"}
        with session_a:
            state_a = get_state(SessionState)
            assert state_a.count.value == 5
            assert state_a.to_dict()['count'] == 5

    def test_ref_and_model_stay_in_sync_per_session(self, clear_state_manager, make_session):
        """Test that reactive refs and the pydantic model agree within every session"""
        session_a, session_b = make_session("a"), make_session("b")

        with session_a:
            get_state(SessionState).count.value = 5
        with session_b:
            state_b = get_state(SessionState)
            state_b.count.value = 3
            assert state_b.to_dict()['count'] == 3
        with session_a:
            assert get_state(SessionState).to_dict()['count'] == 5

    def test_validation_runs_in_every_session(self, clear_state_manager, make_session):
        """Test that ref writes are validated in sessions other than the first"""
        session_a, session_b = make_session("a"), make_session("b")

        with session_a:
            # Touch the ref so its validation subscription is created in session A
            get_state(SessionState).count.value = 1
        with session_b:
            state_b = get_state(SessionState)
            with pytest.raises(ValidationError):
                state_b.count.value = -1

    def test_reset_state_only_affects_current_session(self, clear_state_manager, make_session):
        """Test that reset_state resets only the active session's instance"""
        session_a, session_b = make_session("a"), make_session("b")

        with session_a:
            get_state(SessionState).count.value = 5
        with session_b:
            get_state(SessionState).count.value = 7
            reset_state(SessionState)
            assert get_state(SessionState).count.value == 0
        with session_a:
            assert get_state(SessionState).count.value == 5

    def test_session_states_dropped_on_close(self, make_session):
        """Test that a session's states are released when its kernel closes"""
        manager = StateManager()
        session = make_session("a")

        with session:
            manager.get_state(SessionState)
        assert "a" in manager._states

        session.close()

        assert "a" not in manager._states

    def test_outside_session_uses_global_scope(self, make_session):
        """Test that code outside any session shares a single global scope"""
        manager = StateManager()
        session = make_session("a")

        outside = manager.get_state(SessionState)
        with session:
            inside = manager.get_state(SessionState)

        assert outside is manager.get_state(SessionState)
        assert outside is not inside
        assert set(manager._states) == {GLOBAL_SCOPE, "a"}

    def test_clear_all_clears_every_session(self, make_session):
        """Test that clear_all removes states from all sessions"""
        manager = StateManager()
        session_a, session_b = make_session("a"), make_session("b")

        with session_a:
            manager.get_state(SessionState)
        with session_b:
            manager.get_state(SessionState)

        manager.clear_all()

        assert manager._states == {}

    def test_session_close_disposes_subscriptions(self, make_session):
        """Test that closing a session unsubscribes its refs without leak warnings"""
        manager = StateManager()
        session = make_session("a")

        with session:
            state = manager.get_state(SessionState)
            state.count.value = 1  # creates the ref and its sync subscription
            state.count = 2        # direct assignment must not add subscriptions
            state.name.value = "ada"

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            session.close()

        assert not [w for w in caught if "still active when its kernel closed" in str(w.message)]
        assert state.__dict__["_sync_disposers"] == {}
