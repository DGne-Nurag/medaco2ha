"""Fixtures for tests that run the integration inside Home Assistant."""

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock, enable_custom_integrations):
    """Start the recorder before hass and allow loading custom_components/medaco."""
    return
