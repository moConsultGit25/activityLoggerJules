# tests/shared_kernel/test_event_dispatcher.py
import unittest
from unittest.mock import MagicMock, call
import dataclasses

from src.shared_kernel.events import DomainEvent, EventDispatcher

# Define some test events
@dataclasses.dataclass
class TestEventA(DomainEvent):
    value: int

@dataclasses.dataclass
class TestEventB(DomainEvent):
    message: str

class TestEventDispatcher(unittest.TestCase):

    def setUp(self):
        self.dispatcher = EventDispatcher() # Create a new dispatcher for each test

    def test_subscribe_and_publish_single_handler(self):
        # --- Arrange ---
        mock_handler = MagicMock()
        event_instance = TestEventA(value=10)

        self.dispatcher.subscribe(TestEventA, mock_handler)

        # --- Act ---
        self.dispatcher.publish(event_instance)

        # --- Assert ---
        mock_handler.assert_called_once_with(event_instance)

    def test_publish_multiple_handlers_for_same_event(self):
        # --- Arrange ---
        mock_handler1 = MagicMock()
        mock_handler2 = MagicMock()
        event_instance = TestEventA(value=20)

        self.dispatcher.subscribe(TestEventA, mock_handler1)
        self.dispatcher.subscribe(TestEventA, mock_handler2)

        # --- Act ---
        self.dispatcher.publish(event_instance)

        # --- Assert ---
        mock_handler1.assert_called_once_with(event_instance)
        mock_handler2.assert_called_once_with(event_instance)

    def test_publish_event_with_no_handlers(self):
        # --- Arrange ---
        event_instance = TestEventB(message="Hello")
        # No handlers subscribed for TestEventB

        # --- Act ---
        # Publishing should not raise an error
        try:
            self.dispatcher.publish(event_instance)
        except Exception as e:
            self.fail(f"Publishing event with no handlers raised an exception: {e}")
        # No specific assertion on calls, just that it runs without error.

    def test_handler_raising_exception_does_not_stop_other_handlers(self):
        # --- Arrange ---
        mock_handler_good1 = MagicMock(name="GoodHandler1")
        mock_handler_bad = MagicMock(name="BadHandler", side_effect=ValueError("Simulated Handler Error"))
        mock_handler_good2 = MagicMock(name="GoodHandler2")

        event_instance = TestEventA(value=30)

        self.dispatcher.subscribe(TestEventA, mock_handler_good1)
        self.dispatcher.subscribe(TestEventA, mock_handler_bad) # This one will raise error
        self.dispatcher.subscribe(TestEventA, mock_handler_good2)

        # --- Act ---
        # The dispatcher's publish method should catch the exception from mock_handler_bad
        # and continue to call other handlers.
        self.dispatcher.publish(event_instance)

        # --- Assert ---
        mock_handler_good1.assert_called_once_with(event_instance)
        mock_handler_bad.assert_called_once_with(event_instance) # It was called
        mock_handler_good2.assert_called_once_with(event_instance) # Should still be called

    def test_subscribe_multiple_event_types(self):
        # --- Arrange ---
        mock_handler_a = MagicMock()
        mock_handler_b = MagicMock()

        event_a = TestEventA(value=40)
        event_b = TestEventB(message="Event B Test")

        self.dispatcher.subscribe(TestEventA, mock_handler_a)
        self.dispatcher.subscribe(TestEventB, mock_handler_b)

        # --- Act ---
        self.dispatcher.publish(event_a)
        self.dispatcher.publish(event_b)

        # --- Assert ---
        mock_handler_a.assert_called_once_with(event_a)
        mock_handler_b.assert_called_once_with(event_b)
        # Ensure they were not called with the wrong event
        mock_handler_a.assert_has_calls([call(event_a)])
        mock_handler_b.assert_has_calls([call(event_b)])


if __name__ == '__main__':
    unittest.main()
