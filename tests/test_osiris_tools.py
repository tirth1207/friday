import pytest

from tools.osiris.osiris_tools import _build_params, _validate_endpoint, osiris_endpoint_catalog
from tools.osiris.intelligence_router import _select_endpoints


def test_osiris_rejects_unknown_endpoint():
    with pytest.raises(ValueError, match="Unsupported OSIRIS endpoint"):
        _validate_endpoint("https://example.com/api")


def test_osiris_catalog_returns_only_logical_allowlist():
    catalog = osiris_endpoint_catalog()
    assert catalog["news"] == "/api/news"
    assert catalog["weather"] == "/api/weather"
    assert all(path.startswith("/api/") for path in catalog.values())


def test_generic_news_request_only_forwards_query():
    assert _build_params("news", query="India", latitude=23.0, longitude=72.0, radius_km=25) == {"q": "India"}


def test_generic_region_request_only_forwards_coordinates():
    assert _build_params("region_dossier", query="India", latitude=23.0, longitude=72.0, radius_km=25) == {
        "lat": 23.0,
        "lon": 72.0,
    }


def test_generic_feed_drops_unsupported_optional_parameters():
    assert _build_params("weather", query="Ahmedabad", latitude=23.0, longitude=72.0, radius_km=25) == {}


def test_router_matches_topics_by_tokens_and_caps_sources():
    assert _select_endpoints("wildfire near Delhi", max_sources=1) == ("fires",)
    assert _select_endpoints("satellite status", max_sources=2) == ("satellites", "space_weather")


def test_router_unknown_topic_falls_back_to_news():
    assert _select_endpoints("tell me something completely unrelated", max_sources=4) == ("news",)
