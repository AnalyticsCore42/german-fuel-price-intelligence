"""
Test Suite: test_ui_app.py
Verifies the Streamlit dashboard layout calculations, Plotly configuration,
and UI helper functions execution to catch any runtime or Plotly layout exceptions.

Run with:  pytest tests/ -v
"""

import sys
from pathlib import Path
from datetime import date
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock

# Create a mock streamlit module
class MockStreamlit:
    def __init__(self):
        # Session state mock
        self.session_state = MagicMock()
        
        # Sidebar mock
        self.sidebar = MagicMock()
        self.sidebar.__enter__ = MagicMock(return_value=self.sidebar)
        self.sidebar.__exit__ = MagicMock(return_value=False)
        self.sidebar.selectbox = MagicMock(side_effect=self.selectbox)
        self.sidebar.date_input = MagicMock(side_effect=self.date_input)
        self.sidebar.slider = MagicMock(side_effect=self.slider)
        self.sidebar.checkbox = MagicMock(return_value=False)
        self.sidebar.markdown = MagicMock()
        self.sidebar.info = MagicMock()
        self.sidebar.divider = MagicMock()

        # Columns, tabs, containers
        self.columns = MagicMock(side_effect=self.create_columns)
        self.tabs = MagicMock(side_effect=self.create_tabs)
        self.sidebar.columns = MagicMock(side_effect=self.create_columns)
        self.container = MagicMock()
        self.container.return_value.__enter__ = MagicMock()
        self.container.return_value.__exit__ = MagicMock(return_value=False)

        # Simple elements
        self.plotly_chart = MagicMock()
        self.markdown = MagicMock()
        self.info = MagicMock()
        self.title = MagicMock()
        self.subheader = MagicMock()
        self.set_page_config = MagicMock()
        self.divider = MagicMock()
        self.checkbox = MagicMock(return_value=False)
        self.cache_data = MagicMock(return_value=lambda f: f)
        
        # Mock Context
        self.context = MagicMock()
        self.context.locale = "de"

    def selectbox(self, label, options, *args, **kwargs):
        # If options are ["en", "de"], return "en"
        if "en" in options:
            return "en"
        # If options are ["e5", "e10", "diesel"], return "e5"
        if "e5" in options:
            return "e5"
        # If options are [1, 7, 14, 30], return 1
        if 1 in options:
            return 1
        # If options are ["hide", "combined", "detailed"], return "detailed"
        if "detailed" in options:
            return "detailed"
        # If options are ["brent", "refined"], return "brent"
        if "brent" in options:
            return "brent"
        # If options are brand list, return first
        return options[0] if options else MagicMock()

    def slider(self, label, *args, **kwargs):
        # Return a range of dates
        val = kwargs.get("value")
        if val is not None:
            return val
        return (date(2022, 1, 1), date(2026, 6, 20))

    def date_input(self, label, *args, **kwargs):
        val = kwargs.get("value")
        if val is not None:
            return val
        return [date(2021, 1, 1), date(2026, 6, 20)]

    def create_columns(self, spec, *args, **kwargs):
        if isinstance(spec, int):
            count = spec
        else:
            count = len(spec)
        return [MagicMock() for _ in range(count)]

    def create_tabs(self, tabs_list, *args, **kwargs):
        return [MagicMock() for _ in range(len(tabs_list))]

    def __getattr__(self, name):
        return MagicMock()

# Inject the mock streamlit module into sys.modules before importing the app
sys.modules['streamlit'] = MockStreamlit()

import pytest
import plotly.graph_objs as go

def test_app_loads_and_runs_successfully():
    """
    Smoke test: Import ui/04_app.py and verify that the module compiles,
    loads the dataset, and builds all Plotly figure layouts without raising any exceptions.
    """
    # Import the module dynamically since it starts with a number
    import importlib
    app = importlib.import_module("ui.04_app")
    
    # Verify that PLOT_LAYOUT and PLOT_CONFIG are properly defined
    assert "PLOT_LAYOUT" in dir(app)
    assert "PLOT_CONFIG" in dir(app)
    assert app.PLOT_CONFIG == {'displayModeBar': False}
    
    # Test add_discount_bands function directly on a Plotly figure
    fig = go.Figure()
    processed_fig = app.add_discount_bands(fig)
    assert isinstance(processed_fig, go.Figure)
    
    # Verify we did not introduce any invalid properties like 'cliponaxis' to annotations
    annotations = processed_fig.layout.annotations
    for annotation in annotations:
        assert hasattr(annotation, 'text')
        # Ensure it has standard attributes
        assert annotation.showarrow is False
        assert annotation.xanchor in ["left", "right"]
