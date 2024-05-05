from unittest.mock import MagicMock
import pytest


@pytest.fixture
def mock_logger():
    class MockLogger:
        def __init__(self):
            self.debug = MagicMock()
            self.error = MagicMock()
            self.info = MagicMock()

    return MockLogger()
