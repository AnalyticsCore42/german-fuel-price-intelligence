"""
Test Suite: test_ui_app.py
Verifies the Streamlit dashboard layout calculations, Plotly configuration,
and UI helper functions execution to catch any runtime or Plotly layout exceptions.

Run with:  pytest tests/ -v
"""

import sys
from pathlib import Path
from datetime import date

# Make the project root importable so we can load ui/04_app.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import MagicMock

# Create a mock streamlit module
class MockStreamlit:
    def __init__(self):
        self.target_language = "en"
        # Session state mock
        self.session_state = MagicMock()
        self.captured_texts = []
        self.rendered_charts = []
        self.radio_overrides = {}
        self.selectbox_overrides = {}

        def _rec(val):
            if isinstance(val, str):
                self.captured_texts.append(val)

        self._record_text = _rec
        
        # Sidebar mock
        self.sidebar = MagicMock()
        self.sidebar.__enter__ = MagicMock(return_value=self.sidebar)
        self.sidebar.__exit__ = MagicMock(return_value=False)
        self.sidebar.selectbox = MagicMock(side_effect=self.selectbox)
        self.sidebar.multiselect = MagicMock(side_effect=self.multiselect)
        self.sidebar.radio = MagicMock(side_effect=self.radio)
        self.sidebar.date_input = MagicMock(side_effect=self.date_input)
        self.sidebar.slider = MagicMock(side_effect=self.slider)
        self.sidebar.checkbox = MagicMock(side_effect=lambda label, *args, **kwargs: (_rec(label), False)[1])
        self.sidebar.button = MagicMock(side_effect=lambda label, *args, **kwargs: (_rec(label), False)[1])
        self.sidebar.markdown = MagicMock(side_effect=lambda *args, **kwargs: _rec(args[0]) if args else None)
        self.sidebar.info = MagicMock(side_effect=lambda *args, **kwargs: _rec(args[0]) if args else None)
        self.sidebar.divider = MagicMock()

        # Columns, tabs, containers
        self.columns = MagicMock(side_effect=self.create_columns)
        self.tabs = MagicMock(side_effect=self.create_tabs)
        self.sidebar.columns = MagicMock(side_effect=self.create_columns)
        self.container = MagicMock()
        self.container.return_value.__enter__ = MagicMock()
        self.container.return_value.__exit__ = MagicMock(return_value=False)

        # Simple elements
        self.plotly_chart = MagicMock(side_effect=self._record_plotly_chart)
        self.markdown = MagicMock(side_effect=lambda *args, **kwargs: _rec(args[0]) if args else None)
        self.info = MagicMock(side_effect=lambda *args, **kwargs: _rec(args[0]) if args else None)
        self.warning = MagicMock(side_effect=lambda *args, **kwargs: _rec(args[0]) if args else None)
        self.success = MagicMock(side_effect=lambda *args, **kwargs: _rec(args[0]) if args else None)
        self.error = MagicMock(side_effect=lambda *args, **kwargs: _rec(args[0]) if args else None)
        self.caption = MagicMock(side_effect=lambda *args, **kwargs: _rec(args[0]) if args else None)
        self.title = MagicMock(side_effect=lambda *args, **kwargs: _rec(args[0]) if args else None)
        self.header = MagicMock(side_effect=lambda *args, **kwargs: _rec(args[0]) if args else None)
        self.subheader = MagicMock(side_effect=lambda *args, **kwargs: _rec(args[0]) if args else None)
        self.text_input = MagicMock(side_effect=lambda label, *args, **kwargs: (_rec(label), _rec(kwargs.get("placeholder", "")), "")[2])
        self.set_page_config = MagicMock()
        self.divider = MagicMock()
        self.checkbox = MagicMock(side_effect=lambda label, *args, **kwargs: (_rec(label), False)[1])
        self.radio = MagicMock(side_effect=self.radio)
        self.multiselect = MagicMock(side_effect=self.multiselect)
        self.button = MagicMock(side_effect=lambda label, *args, **kwargs: (_rec(label), False)[1])
        self.download_button = MagicMock(side_effect=lambda label, *args, **kwargs: (_rec(label), False)[1])
        self.dataframe = MagicMock(side_effect=self._record_dataframe)
        self.cache_data = self._cache_decorator
        self.cache_resource = self._cache_decorator

        # Mock Context
        self.context = MagicMock()
        self.context.locale = "de"

    def _cache_decorator(self, *args, **kwargs):
        if len(args) == 1 and callable(args[0]):
            return args[0]
        def decorator(f):
            return f
        return decorator

    def _record_plotly_chart(self, figure, *args, **kwargs):
        self.rendered_charts.append(figure)
        if hasattr(figure, "layout"):
            if getattr(figure.layout, "title", None) and getattr(figure.layout.title, "text", None):
                self._record_text(figure.layout.title.text)
            if getattr(figure.layout, "xaxis", None) and getattr(figure.layout.xaxis, "title", None) and getattr(figure.layout.xaxis.title, "text", None):
                self._record_text(figure.layout.xaxis.title.text)
            if getattr(figure.layout, "yaxis", None) and getattr(figure.layout.yaxis, "title", None) and getattr(figure.layout.yaxis.title, "text", None):
                self._record_text(figure.layout.yaxis.title.text)
            if getattr(figure.layout, "annotations", None):
                for ann in figure.layout.annotations:
                    if getattr(ann, "text", None):
                        self._record_text(ann.text)
        if hasattr(figure, "data"):
            for tr in figure.data:
                if getattr(tr, "name", None):
                    self._record_text(tr.name)
                if getattr(tr, "hovertemplate", None):
                    self._record_text(tr.hovertemplate)
        return None

    def _record_dataframe(self, data, *args, **kwargs):
        import pandas as pd
        if isinstance(data, pd.DataFrame):
            for col in data.columns:
                self._record_text(str(col))
            for val in data.head(5).values.flatten():
                if isinstance(val, str):
                    self._record_text(val)
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            for row in data[:5]:
                for k, v in row.items():
                    self._record_text(str(k))
                    if isinstance(v, str):
                        self._record_text(v)

    def selectbox(self, label, options, *args, **kwargs):
        self._record_text(label)
        if kwargs.get("help"):
            self._record_text(kwargs["help"])
        for opt in options:
            if isinstance(opt, str):
                self._record_text(opt)
        # If options are ["en", "de"], return configured language
        if "en" in options and "de" in options:
            return self.target_language
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

    def multiselect(self, label, options, default=None, *args, **kwargs):
        self._record_text(label)
        if default is not None:
            return list(default)
        return [options[0]] if options else []

    def radio(self, label, options, *args, **kwargs):
        self._record_text(label)
        for opt in options:
            if isinstance(opt, str):
                self._record_text(opt)
        key = kwargs.get("key")
        overrides = getattr(self, "radio_overrides", {})
        if key and key in overrides:
            return overrides[key]
        for k, v in overrides.items():
            if k in label or k == label:
                return v
        idx = kwargs.get("index", 0)
        if options and 0 <= idx < len(options):
            return options[idx]
        return options[0] if options else MagicMock()

    def slider(self, label, *args, **kwargs):
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
    assert app.PLOT_CONFIG.get('displayModeBar') is False
    
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

def test_event_study_policy_events():
    """Verify that all 6 policy events (both starts and ends) are configured and translated."""
    import importlib
    app = importlib.import_module("ui.04_app")
    
    expected_events = [
        "Tankrabatt 1 Start (Jun 2022)",
        "Tankrabatt 1 End (Sep 2022)",
        "Tankrabatt 2 Start (May 2026)",
        "Tankrabatt 2 End (Jul 2026)",
        "Tankrabatt 3 Start (Oct 2026)",
        "Tankrabatt 3 End (Jan 2027)",
    ]
    
    for evt in expected_events:
        assert evt in app.EVENT_NAME_KEYS
        assert evt in app.POLICY_MILESTONES
        
        # Verify translations exist in en and de
        key = app.EVENT_NAME_KEYS[evt]
        assert key in app.TRANSLATIONS["en"]
        assert key in app.TRANSLATIONS["de"]


def test_compliance_subtab_translations():
    """Verify that all compliance subtabs and tactics keys are translated in both en and de."""
    import importlib
    app = importlib.import_module("ui.04_app")
    
    compliance_keys = [
        "compliance_subtab_audit",
        "compliance_subtab_tactics",
        "compliance_subtab_forensics",
        "compliance_tactics_title",
        "compliance_tactics_sub",
        "compliance_etl_box_title",
        "compliance_col_hike_nr",
        "compliance_col_noon_context",
        "compliance_col_etl_status"
    ]
    for k in compliance_keys:
        assert k in app.TRANSLATIONS["en"], f"Missing {k} in en translations"
        assert k in app.TRANSLATIONS["de"], f"Missing {k} in de translations"


def test_each_chart_is_really_loading():
    """
    Directly verifies that every single Plotly chart in the dashboard
    was genuinely constructed, contains real non-empty traces and data points,
    and successfully serializes without schema or Plotly layout exceptions.
    """
    import sys
    mock_st = sys.modules['streamlit']
    charts = mock_st.rendered_charts

    assert len(charts) >= 10, f"Expected at least 10 rendered Plotly charts, but only {len(charts)} were captured."

    for idx, fig in enumerate(charts):
        # 1. Type check
        assert isinstance(fig, go.Figure), f"Chart #{idx} is not a Plotly Figure: {type(fig)}"
        
        # 2. Non-empty check
        assert len(fig.data) > 0, f"Chart #{idx} has no data traces!"
        
        # 3. Data points check
        has_data_points = False
        for trace_idx, trace in enumerate(fig.data):
            x_vals = getattr(trace, "x", None)
            y_vals = getattr(trace, "y", None)
            if x_vals is not None and len(x_vals) > 0 and y_vals is not None and len(y_vals) > 0:
                has_data_points = True
                break
        assert has_data_points, f"Chart #{idx} has traces, but none contain valid (x, y) coordinates!"
        
        # 4. JSON serialization check (ensures Plotly layout, shapes, vlines, annotations have no invalid attributes)
        chart_dict = fig.to_dict()
        assert "data" in chart_dict
        assert "layout" in chart_dict
        assert len(chart_dict["data"]) > 0


import json
import ast
import re

def test_language_files_perfect_parity_and_completeness():
    """
    Verifies that ui/translations/de.json and ui/translations/en.json
    have 100% identical key sets, no empty values, and matching template variables.
    """
    proj_root = Path(__file__).resolve().parent.parent
    de_path = proj_root / "ui" / "translations" / "de.json"
    en_path = proj_root / "ui" / "translations" / "en.json"

    assert de_path.exists(), "ui/translations/de.json does not exist"
    assert en_path.exists(), "ui/translations/en.json does not exist"

    with open(de_path, "r", encoding="utf-8") as f:
        de = json.load(f)
    with open(en_path, "r", encoding="utf-8") as f:
        en = json.load(f)

    # 1. Key set parity
    de_keys = set(de.keys())
    en_keys = set(en.keys())
    missing_in_en = de_keys - en_keys
    missing_in_de = en_keys - de_keys
    assert not missing_in_en, f"Keys present in de.json but missing in en.json: {missing_in_en}"
    assert not missing_in_de, f"Keys present in en.json but missing in de.json: {missing_in_de}"

    # 2. Non-empty string check
    for k in de_keys:
        assert isinstance(de[k], str), f"de.json key '{k}' must be a string"
        assert isinstance(en[k], str), f"en.json key '{k}' must be a string"
        assert len(de[k].strip()) > 0, f"de.json key '{k}' has empty or whitespace-only value"
        assert len(en[k].strip()) > 0, f"en.json key '{k}' has empty or whitespace-only value"

        # 3. Format placeholders match (e.g. {count}, {fuel})
        de_vars = set(re.findall(r"\{([a-zA-Z0-9_]+)\}", de[k]))
        en_vars = set(re.findall(r"\{([a-zA-Z0-9_]+)\}", en[k]))
        assert de_vars == en_vars, f"Key '{k}' placeholder mismatch: DE has {de_vars} vs EN has {en_vars}"


def test_all_code_translate_calls_use_registered_json_keys():
    """
    Scans the abstract syntax trees (AST) of the UI code files to ensure that
    every call to translate('key') references a valid, registered key in the translation files.
    """
    proj_root = Path(__file__).resolve().parent.parent
    de_path = proj_root / "ui" / "translations" / "de.json"
    with open(de_path, "r", encoding="utf-8") as f:
        de_keys = set(json.load(f).keys())

    py_files = [
        proj_root / "ui" / "04_app.py",
        proj_root / "ui" / "tank_advisor_tab.py"
    ]

    unregistered_keys = []
    for p in py_files:
        if not p.exists():
            continue
        with open(p, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                is_trans = (isinstance(func, ast.Name) and func.id == "translate") or (
                    isinstance(func, ast.Attribute) and func.attr == "translate"
                )
                if is_trans and node.args:
                    arg0 = node.args[0]
                    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                        key = arg0.value
                        if key not in de_keys:
                            unregistered_keys.append((p.name, node.lineno, key))

    assert not unregistered_keys, f"Found unregistered translate() keys in code: {unregistered_keys}"


def test_no_hardcoded_german_in_streamlit_calls():
    """
    Scans AST of ui/04_app.py to ensure that user-facing Streamlit widgets and display
    functions do not receive raw German string literals without calling translate().
    """
    proj_root = Path(__file__).resolve().parent.parent
    app_path = proj_root / "ui" / "04_app.py"

    with open(app_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    st_methods = {
        "title", "header", "subheader", "caption", "text", "markdown",
        "info", "warning", "error", "success", "selectbox", "radio",
        "checkbox", "multiselect", "button", "download_button", "text_input"
    }
    german_flag_words = [
        "verstöße", "erhöhung", "tankstelle", "bundesweit", "mittelstand",
        "regeleinhaltung", "preisanhebung", "unzulässig", "stichtag",
        "tagesrhythmus", "beweisprotokoll"
    ]

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in st_methods:
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    val = node.args[0].value.strip()
                    # Skip CSS stylesheets
                    if val.startswith("<style") or val.startswith("/*"):
                        continue
                    for word in german_flag_words:
                        if word in val.lower():
                            violations.append((node.lineno, func.attr, word, val[:60]))
                            break

    assert not violations, f"Found hardcoded German strings in Streamlit UI calls: {violations}"


def test_ui_renders_strictly_in_english_without_german_leaks():
    """
    Renders the dashboard with target_language='en' and asserts that
    no German marker words leak into captured markdown, widgets, table columns, or chart titles.
    """
    import importlib
    import sys
    mock_st = sys.modules["streamlit"]
    mock_st.target_language = "en"
    mock_st.captured_texts.clear()
    mock_st.rendered_charts.clear()

    app = importlib.import_module("ui.04_app")
    importlib.reload(app)

    assert len(mock_st.captured_texts) > 50, "Expected at least 50 captured UI text elements in EN mode"

    german_markers = [
        "Verstöße", "Erhöhungen", "Preisanhebung", "Regeleinhaltung",
        "Mittelstand", "Unzulässig", "Stichtag", "Tagesrhythmus",
        "Beweisprotokoll", "Kulanzkorridor", "Vorkrieg"
    ]

    leaks = []
    for text in mock_st.captured_texts:
        if text.startswith("<style"):
            continue
        for m in german_markers:
            if m.lower() in text.lower():
                leaks.append((m, text[:120].replace("\n", " ")))
                break

    assert not leaks, f"German text leaked into English view ({len(leaks)} leaks): {leaks[:5]}"


def test_ui_renders_strictly_in_german_without_english_leaks():
    """
    Renders the dashboard with target_language='de' and asserts that
    English marker words do not leak into the German view.
    """
    import importlib
    import sys
    mock_st = sys.modules["streamlit"]
    mock_st.target_language = "de"
    mock_st.captured_texts.clear()
    mock_st.rendered_charts.clear()

    app = importlib.import_module("ui.04_app")
    importlib.reload(app)

    assert len(mock_st.captured_texts) > 50, "Expected at least 50 captured UI text elements in DE mode"

    english_markers = [
        "Violations (Hikes)", "Tolerance Window", "Isolated Variances",
        "Cut-off Date", "Statutory 12:00"
    ]

    leaks = []
    for text in mock_st.captured_texts:
        if text.startswith("<style"):
            continue
        for m in english_markers:
            if m.lower() in text.lower():
                leaks.append((m, text[:120].replace("\n", " ")))
                break

    assert not leaks, f"English text leaked into German view ({len(leaks)} leaks): {leaks[:5]}"


def test_discount_kpi_cards_mathematical_reconciliation_and_validation():
    """
    Validates that:
    1. Pass-through % is strictly bounded between 0% and 100% across all fuels.
    2. Tax Cut strictly reconciles: Steuersenkung == Weitergegeben + Einbehalten (Kosten & Marge).
    3. Retained amount is non-negative.
    4. Anomaly detection flags cases where raw pump drop exceeds statutory tax cut (e.g. Diesel 2026).
    """
    import importlib
    import polars as pl
    from datetime import date
    app = importlib.import_module("ui.04_app")

    df_full = app.load_data(start_date=date(2014, 6, 8))

    for fuel in ["diesel", "e5", "e10"]:
        pump_col = f"price_{fuel}"
        
        # Test Discount 1
        d1 = app._compute_discount_card_kpi(app.d1_start, app.d1_end, df_full, pump_col)
        assert 0.0 <= d1["pass_pct"] <= 100.0, f"{fuel} Discount 1 pass_pct={d1['pass_pct']} must be <= 100%"
        assert d1["retained_ct"] >= 0.0, f"{fuel} Discount 1 retained must be non-negative"
        assert abs((d1["passed_ct"] + d1["retained_ct"]) - d1["tax_drop_ct"]) < 0.05, f"{fuel} Discount 1 does not reconcile"
        assert d1["validation_error"] is None

        # Test Discount 2
        d2 = app._compute_discount_card_kpi(app.d2_start, app.d2_actual_end, df_full, pump_col)
        assert 0.0 <= d2["pass_pct"] <= 100.0, f"{fuel} Discount 2 pass_pct={d2['pass_pct']} must be <= 100%"
        assert d2["retained_ct"] >= 0.0, f"{fuel} Discount 2 retained must be non-negative"
        assert abs((d2["passed_ct"] + d2["retained_ct"]) - d2["tax_drop_ct"]) < 0.05, f"{fuel} Discount 2 does not reconcile"
        assert d2["validation_error"] is None

    # Diesel 2026 specific anomaly verification
    d2_diesel = app._compute_discount_card_kpi(app.d2_start, app.d2_actual_end, df_full, "price_diesel")
    assert d2_diesel["is_anomaly"] is True, "Diesel 2026 must be flagged as anomaly due to post-Iran crude collapse"
    assert d2_diesel["raw_pass_pct"] > 100.0, "Diesel 2026 raw unadjusted pass-through exceeded 100%"
    assert d2_diesel["pass_pct"] <= 100.0, "Corrected pass-through must be <= 100%"


def test_compliance_lateness_labels_and_tactics_consistency():
    """Verify that lateness distribution labels contain no PE Flash Rebound and tactics accurately describe groups."""
    import importlib
    app = importlib.import_module("ui.04_app")
    
    # 1. Check all 9 lateness bucket keys exist and contain no 'PE Flash'
    for b_id in range(1, 10):
        found = False
        for k in app.TRANSLATIONS["de"].keys():
            if k.startswith(f"compliance_late_b{b_id}"):
                found = True
                de_val = app.TRANSLATIONS["de"][k]
                en_val = app.TRANSLATIONS["en"][k]
                assert "PE Flash" not in de_val, f"Found PE Flash in {k}: {de_val}"
                assert "PE Flash" not in en_val, f"Found PE Flash in {k}: {en_val}"
                assert "Flash Rebound" not in de_val, f"Found Flash Rebound in {k}: {de_val}"
                assert "Flash Rebound" not in en_val, f"Found Flash Rebound in {k}: {en_val}"
        assert found, f"Missing translation for lateness bucket b{b_id}"

    # Specifically verify b6 (13:00 - 15:00) is clean Early Afternoon
    assert "Früher Nachmittag" in app.TRANSLATIONS["de"]["compliance_late_b6_early_pm"]
    assert "Early Afternoon" in app.TRANSLATIONS["en"]["compliance_late_b6_early_pm"]

    # 2. Check tactics texts reflect Esso is largest volume network but not top 1 per station
    de_kpi1 = app.TRANSLATIONS["de"]["compliance_tactics_kpi1_html"]
    de_kpi2 = app.TRANSLATIONS["de"]["compliance_tactics_kpi2_html"]
    en_kpi1 = app.TRANSLATIONS["en"]["compliance_tactics_kpi1_html"]
    en_kpi2 = app.TRANSLATIONS["en"]["compliance_tactics_kpi2_html"]

    assert "nicht Top 1 pro Station" in de_kpi1
    assert "not top 1 per station" in en_kpi1
    assert "Höhere Quote pro Station" in de_kpi2
    assert "Higher rate per station" in en_kpi2


def test_all_compliance_view_modes_and_clock_chart_render_without_error():
    """
    Directly tests that View 2 (Time-of-Day Clock Distribution) and all filter modes
    (including cuts) build their Plotly figures without any TypeError, keyword argument
    collisions (like xaxis), or rendering crashes in BOTH German and English.
    """
    import sys
    import importlib
    mock_st = sys.modules['streamlit']
    app = importlib.import_module("ui.04_app")

    for target_lang in ["de", "en"]:
        mock_st.rendered_charts.clear()
        mock_st.target_language = target_lang

        clock_view_val = app.TRANSLATIONS[target_lang]["compliance_view_clock"]
        all_filter_val = app.TRANSLATIONS[target_lang]["compliance_filter_all"]
        view_mode_label = app.TRANSLATIONS[target_lang]["compliance_view_mode"]
        filter_mode_label = app.TRANSLATIONS[target_lang]["compliance_filter_mode"]

        mock_st.radio_overrides = {
            view_mode_label: clock_view_val,
            filter_mode_label: all_filter_val,
            "compliance_view": clock_view_val,
            "compliance_filter": all_filter_val,
        }

        try:
            importlib.reload(app)
            assert len(mock_st.rendered_charts) >= 10, f"Charts must be rendered in View 2 ({target_lang})"
            for idx, fig in enumerate(mock_st.rendered_charts):
                assert isinstance(fig, go.Figure), f"Chart #{idx} is not a Plotly Figure ({target_lang})"
                c_dict = fig.to_dict()
                assert "layout" in c_dict
                assert "data" in c_dict
                assert len(c_dict["data"]) > 0
        finally:
            mock_st.radio_overrides.clear()

    # Reset back to default English
    mock_st.target_language = "en"
    importlib.reload(app)







