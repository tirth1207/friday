import pytest

from tools.osiris.osiris_tools import _build_params, _validate_endpoint, osiris_endpoint_catalog
from tools.osiris.intelligence_router import _select_endpoints


def test_osiris_rejects_unknown_endpoint():
    with pytest.raises(ValueError, match="Unsupported OSIRIS endpoint"):
        _validate_endpoint("https://example.com/api")


def test_osiris_catalog_contains_live_operational_feeds():
    catalog = osiris_endpoint_catalog()
    assert catalog["news"] == "/api/news"
    assert catalog["weather"] == "/api/weather"
    assert catalog["conflicts"] == "/api/conflicts"
    assert catalog["flights"] == "/api/flights"
    assert catalog["earthquakes"] == "/api/earthquakes"
    assert catalog["malware"] == "/api/malware"
    assert all(path.startswith("/api/") for path in catalog.values())


def test_generic_news_request_only_forwards_query():
    assert _build_params("news", query="India", latitude=23.0, longitude=72.0, radius_km=25) == {"q": "India"}


def test_region_request_uses_osiris_documented_lat_lng_names():
    assert _build_params("region_dossier", query="India", latitude=23.0, longitude=72.0, radius_km=25) == {
        "lat": 23.0,
        "lng": 72.0,
    }


def test_sentinel_request_accepts_documented_coordinates_and_filters():
    assert _build_params("sentinel", latitude=23.0, longitude=72.0, radius_km=25, days=30) == {
        "lat": 23.0,
        "lng": 72.0,
        "radius": 25,
        "days": 30,
    }


def test_osint_lookup_parameters_are_not_leaked_between_endpoint_families():
    assert _build_params("osint_dns", domain="example.com", latitude=23.0) == {
        "domain": "example.com",
    }
    assert _build_params("osint_sanctions", query="Acme", schema="Organization", limit=10) == {
        "query": "Acme",
        "schema": "Organization",
        "limit": 10,
    }


def test_generic_feed_drops_unsupported_optional_parameters():
    assert _build_params("weather", query="Ahmedabad", latitude=23.0, longitude=72.0, radius_km=25) == {}


def test_router_matches_topics_by_tokens_and_caps_sources():
    assert _select_endpoints("wildfire near Delhi", max_sources=1) == ("fires",)
    assert _select_endpoints("satellite status", max_sources=2) == ("satellites", "space_weather")
    assert _select_endpoints("war in Europe", max_sources=4) == ("conflicts", "frontlines", "gdelt", "news")


def test_router_unknown_topic_falls_back_to_news():
    assert _select_endpoints("tell me something completely unrelated", max_sources=4) == ("news",)
