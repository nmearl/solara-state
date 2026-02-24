import pytest
import time
from solara_state import BaseState, StateField, get_state


class PerformanceState(BaseState):
    counter: int = StateField(default=0)


class TestPerformance:
    
    def test_ref_caching_performance(self, clear_state_manager):
        """Test that ref caching improves performance"""
        state = get_state(PerformanceState)
        
        # First access (should create ref)
        start = time.perf_counter()
        ref1 = state.counter
        first_time = time.perf_counter() - start
        
        # Second access (should use cached ref)
        start = time.perf_counter()
        ref2 = state.counter
        second_time = time.perf_counter() - start
        
        assert ref1 is ref2
        assert second_time < first_time  # Cached access should be faster
    
    def test_bulk_updates_efficient(self, clear_state_manager):
        """Test that bulk updates don't create excessive overhead"""
        state = get_state(PerformanceState)
        
        start = time.perf_counter()
        for i in range(100):
            state.update(counter=i)
        end = time.perf_counter()
        
        assert end - start < 0.1  # Should complete quickly
        assert state.counter.value == 99