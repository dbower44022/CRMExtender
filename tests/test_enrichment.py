"""Tests for enrichment provider interface, pipeline, and website scraper."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from poc.database import get_connection, init_db
from poc.enrichment_pipeline import (
    AUTO_ACCEPT_THRESHOLD,
    _apply_direct_fields,
    _apply_email_addresses,
    _apply_phone_numbers,
    _apply_social_profiles,
    _store_field_values,
    create_enrichment_run,
    execute_enrichment,
    get_enrichment_field_values,
    get_enrichment_run,
    get_enrichment_runs,
)
from poc.enrichment_provider import (
    EnrichmentProvider,
    FieldValue,
    SourceTier,
    get_provider,
    list_providers,
    register_provider,
)
from poc.hierarchy import (
    add_phone_number,
    create_company,
    get_addresses,
    get_company,
    get_company_social_profiles,
    get_email_addresses,
    get_phone_numbers,
    update_company,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary database and point config at it."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)
    return db_file


@pytest.fixture()
def sample_company(tmp_db):
    """Create a test company and return its dict."""
    row = create_company("Acme Corp", domain="acme.com", description="")
    return row


# ---------------------------------------------------------------------------
# Mock provider for testing
# ---------------------------------------------------------------------------

class MockProvider(EnrichmentProvider):
    """A mock provider that returns configurable field values."""

    def __init__(self, field_values=None, should_fail=False):
        self._field_values = field_values or []
        self._should_fail = should_fail

    @property
    def name(self) -> str:
        return "mock_provider"

    @property
    def tier(self) -> SourceTier:
        return SourceTier.FREE_API

    def enrich(self, entity: dict) -> list[FieldValue]:
        if self._should_fail:
            raise RuntimeError("Provider error")
        return self._field_values


# ===========================================================================
# Registry tests
# ===========================================================================

class TestProviderRegistry:
    def test_register_and_get(self, tmp_db):
        p = MockProvider()
        register_provider(p)
        assert get_provider("mock_provider") is p

    def test_get_nonexistent(self, tmp_db):
        assert get_provider("nonexistent") is None

    def test_list_providers(self, tmp_db):
        p = MockProvider()
        register_provider(p)
        providers = list_providers()
        assert any(prov.name == "mock_provider" for prov in providers)

    def test_field_value_defaults(self):
        fv = FieldValue(field_name="industry", field_value="Tech")
        assert fv.confidence == 0.0
        assert fv.source_url == ""

    def test_source_tier_ordering(self):
        assert SourceTier.INFERRED < SourceTier.WEBSITE_SCRAPE
        assert SourceTier.WEBSITE_SCRAPE < SourceTier.PAID_API
        assert SourceTier.PAID_API < SourceTier.MANUAL


# ===========================================================================
# Pipeline CRUD tests
# ===========================================================================

class TestPipelineCRUD:
    def test_create_enrichment_run(self, sample_company):
        run = create_enrichment_run("company", sample_company["id"], "test_provider")
        assert run["status"] == "pending"
        assert run["entity_type"] == "company"
        assert run["provider"] == "test_provider"

    def test_get_enrichment_run(self, sample_company):
        run = create_enrichment_run("company", sample_company["id"], "test_provider")
        fetched = get_enrichment_run(run["id"])
        assert fetched is not None
        assert fetched["id"] == run["id"]

    def test_get_enrichment_run_not_found(self, tmp_db):
        assert get_enrichment_run("nonexistent") is None

    def test_get_enrichment_runs_all(self, sample_company):
        create_enrichment_run("company", sample_company["id"], "p1")
        create_enrichment_run("company", sample_company["id"], "p2")
        runs = get_enrichment_runs()
        assert len(runs) >= 2

    def test_get_enrichment_runs_filtered(self, sample_company):
        create_enrichment_run("company", sample_company["id"], "p1")
        runs = get_enrichment_runs(entity_type="company", entity_id=sample_company["id"])
        assert len(runs) >= 1
        assert all(r["entity_id"] == sample_company["id"] for r in runs)

    def test_store_field_values(self, sample_company):
        run = create_enrichment_run("company", sample_company["id"], "test")
        fvs = [
            FieldValue("industry", "Technology", 0.9),
            FieldValue("description", "A tech company", 0.8),
        ]
        stored = _store_field_values(run["id"], fvs)
        assert len(stored) == 2

        fetched = get_enrichment_field_values(run["id"])
        assert len(fetched) == 2
        names = {fv["field_name"] for fv in fetched}
        assert names == {"industry", "description"}


# ===========================================================================
# Pipeline execution tests
# ===========================================================================

class TestPipelineExecution:
    def test_execute_with_mock_provider(self, sample_company):
        provider = MockProvider(field_values=[
            FieldValue("industry", "Technology", 0.9),
            FieldValue("description", "Great company", 0.8),
        ])
        register_provider(provider)

        result = execute_enrichment("company", sample_company["id"], "mock_provider")
        assert result["status"] == "completed"
        assert result["fields_discovered"] == 2
        assert result["fields_applied"] == 2

        # Verify fields were applied
        company = get_company(sample_company["id"])
        assert company["industry"] == "Technology"
        assert company["description"] == "Great company"

    def test_execute_provider_not_found(self, sample_company):
        result = execute_enrichment("company", sample_company["id"], "nonexistent_xyz")
        assert result["status"] == "failed"
        assert "not found" in result["error"]

    def test_execute_entity_not_found(self, tmp_db):
        provider = MockProvider()
        register_provider(provider)
        result = execute_enrichment("company", "no-such-id", "mock_provider")
        assert result["status"] == "failed"
        assert "Entity not found" in result["error"]

    def test_execute_provider_failure(self, sample_company):
        provider = MockProvider(should_fail=True)
        register_provider(provider)
        result = execute_enrichment("company", sample_company["id"], "mock_provider")
        assert result["status"] == "failed"
        assert "Provider error" in result["error"]

    def test_low_confidence_rejected(self, sample_company):
        # Set existing value
        update_company(sample_company["id"], industry="Old Value")

        provider = MockProvider(field_values=[
            FieldValue("industry", "New Value", 0.3),  # Below threshold
        ])
        register_provider(provider)

        result = execute_enrichment("company", sample_company["id"], "mock_provider")
        assert result["status"] == "completed"
        assert result["fields_applied"] == 0

        company = get_company(sample_company["id"])
        assert company["industry"] == "Old Value"

    def test_apply_phone_dedup(self, sample_company):
        add_phone_number("company", sample_company["id"], "555-1234", phone_type="main")

        provider = MockProvider(field_values=[
            FieldValue("phone", "555-1234", 0.8),  # Already exists
            FieldValue("phone", "555-5678", 0.8),  # New
        ])
        register_provider(provider)

        result = execute_enrichment("company", sample_company["id"], "mock_provider")
        phones = get_phone_numbers("company", sample_company["id"])
        assert len(phones) == 2  # One existing + one new

    def test_apply_email_dedup(self, sample_company):
        from poc.hierarchy import add_email_address
        add_email_address("company", sample_company["id"], "info@acme.com")

        provider = MockProvider(field_values=[
            FieldValue("email", "info@acme.com", 0.8),  # Duplicate
            FieldValue("email", "sales@acme.com", 0.8),  # New
        ])
        register_provider(provider)

        result = execute_enrichment("company", sample_company["id"], "mock_provider")
        emails = get_email_addresses("company", sample_company["id"])
        assert len(emails) == 2

    def test_apply_social_profiles(self, sample_company):
        provider = MockProvider(field_values=[
            FieldValue("social_linkedin", "https://linkedin.com/company/acme", 0.9),
            FieldValue("social_twitter", "https://twitter.com/acme", 0.8),
        ])
        register_provider(provider)

        result = execute_enrichment("company", sample_company["id"], "mock_provider")
        profiles = get_company_social_profiles(sample_company["id"])
        assert len(profiles) == 2
        platforms = {p["platform"] for p in profiles}
        assert platforms == {"linkedin", "twitter"}

    def test_field_values_marked_accepted(self, sample_company):
        provider = MockProvider(field_values=[
            FieldValue("industry", "Tech", 0.9),
            FieldValue("description", "Low conf", 0.3),  # Below threshold
        ])
        register_provider(provider)

        result = execute_enrichment("company", sample_company["id"], "mock_provider")
        run_id = result["run_id"]
        field_values = get_enrichment_field_values(run_id)
        accepted = {fv["field_name"]: fv["is_accepted"] for fv in field_values}
        assert accepted["industry"] == 1
        assert accepted["description"] == 0


# ===========================================================================
# Website scraper tests
# ===========================================================================

class TestWebsiteScraper:
    def test_provider_registered(self, tmp_db):
        """website_scraper should be auto-registered on import."""
        from poc import website_scraper  # noqa: F401
        p = get_provider("website_scraper")
        assert p is not None
        assert p.name == "website_scraper"
        assert p.tier == SourceTier.WEBSITE_SCRAPE

    def test_normalize_url(self):
        from poc.website_scraper import _normalize_url
        assert _normalize_url("acme.com") == "https://acme.com"
        assert _normalize_url("https://acme.com") == "https://acme.com"
        assert _normalize_url("http://acme.com") == "http://acme.com"
        assert _normalize_url("") == ""

    def test_robots_txt_allows(self):
        from poc.website_scraper import _is_allowed_by_robots
        robots = "User-agent: *\nDisallow: /admin\n"
        assert _is_allowed_by_robots(robots, "/") is True
        assert _is_allowed_by_robots(robots, "/about") is True
        assert _is_allowed_by_robots(robots, "/admin") is False
        assert _is_allowed_by_robots(robots, "/admin/secret") is False

    def test_robots_txt_none_allows_all(self):
        from poc.website_scraper import _is_allowed_by_robots
        assert _is_allowed_by_robots(None, "/anything") is True

    def test_extract_meta_description(self):
        from poc.website_scraper import _extract_meta
        from bs4 import BeautifulSoup
        html = '<html><head><meta name="description" content="We build widgets."></head></html>'
        soup = BeautifulSoup(html, "lxml")
        results = _extract_meta(soup)
        assert len(results) == 1
        assert results[0].field_name == "description"
        assert results[0].field_value == "We build widgets."

    def test_extract_meta_og_fallback(self):
        from poc.website_scraper import _extract_meta
        from bs4 import BeautifulSoup
        html = '<html><head><meta property="og:description" content="OG desc"></head></html>'
        soup = BeautifulSoup(html, "lxml")
        results = _extract_meta(soup)
        assert len(results) == 1
        assert results[0].field_value == "OG desc"

    def test_extract_meta_prefers_description(self):
        from poc.website_scraper import _extract_meta
        from bs4 import BeautifulSoup
        html = (
            '<html><head>'
            '<meta name="description" content="Meta desc">'
            '<meta property="og:description" content="OG desc">'
            '</head></html>'
        )
        soup = BeautifulSoup(html, "lxml")
        results = _extract_meta(soup)
        assert len(results) == 1
        assert results[0].field_value == "Meta desc"

    def test_extract_json_ld_organization(self):
        from poc.website_scraper import _extract_json_ld
        from bs4 import BeautifulSoup
        ld_data = json.dumps({
            "@type": "Organization",
            "description": "A great org",
            "foundingDate": "2010-01-15",
            "numberOfEmployees": {"@type": "QuantitativeValue", "value": 500},
            "sameAs": ["https://linkedin.com/company/acme"],
        })
        html = f'<html><head><script type="application/ld+json">{ld_data}</script></head></html>'
        soup = BeautifulSoup(html, "lxml")
        results = _extract_json_ld(soup)
        names = {fv.field_name for fv in results}
        assert "description" in names
        assert "founded_year" in names
        assert "employee_count" in names
        assert "social_linkedin" in names
        # Check values
        desc = next(fv for fv in results if fv.field_name == "description")
        assert desc.field_value == "A great org"
        year = next(fv for fv in results if fv.field_name == "founded_year")
        assert year.field_value == "2010"

    def test_extract_json_ld_address(self):
        from poc.website_scraper import _extract_json_ld
        from bs4 import BeautifulSoup
        ld_data = json.dumps({
            "@type": "Organization",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "123 Main St",
                "addressLocality": "Springfield",
                "addressRegion": "IL",
                "postalCode": "62701",
            },
        })
        html = f'<html><head><script type="application/ld+json">{ld_data}</script></head></html>'
        soup = BeautifulSoup(html, "lxml")
        results = _extract_json_ld(soup)
        addr = next((fv for fv in results if fv.field_name == "address"), None)
        assert addr is not None
        assert "123 Main St" in addr.field_value
        assert "Springfield" in addr.field_value

    def test_extract_json_ld_graph(self):
        from poc.website_scraper import _extract_json_ld
        from bs4 import BeautifulSoup
        ld_data = json.dumps({
            "@graph": [
                {"@type": "WebPage"},
                {"@type": "Organization", "description": "In a graph"},
            ]
        })
        html = f'<html><head><script type="application/ld+json">{ld_data}</script></head></html>'
        soup = BeautifulSoup(html, "lxml")
        results = _extract_json_ld(soup)
        assert any(fv.field_value == "In a graph" for fv in results)

    def test_extract_social_links(self):
        from poc.website_scraper import _extract_social_links
        from bs4 import BeautifulSoup
        html = '''<html><body>
            <a href="https://linkedin.com/company/acme">LinkedIn</a>
            <a href="https://twitter.com/acme">Twitter</a>
            <a href="https://github.com/acme">GitHub</a>
            <a href="https://example.com/not-social">Other</a>
        </body></html>'''
        soup = BeautifulSoup(html, "lxml")
        results = _extract_social_links(soup, "acme.com")
        platforms = {fv.field_name for fv in results}
        assert "social_linkedin" in platforms
        assert "social_twitter" in platforms
        assert "social_github" in platforms
        assert len(results) == 3

    def test_extract_contact_info_phone(self):
        from poc.website_scraper import _extract_contact_info
        from bs4 import BeautifulSoup
        html = '<html><body>Call us at (555) 123-4567 or 800-555-9999</body></html>'
        soup = BeautifulSoup(html, "lxml")
        results = _extract_contact_info(soup, "acme.com")
        phones = [fv for fv in results if fv.field_name == "phone"]
        assert len(phones) == 2

    def test_extract_contact_info_email(self):
        from poc.website_scraper import _extract_contact_info
        from bs4 import BeautifulSoup
        html = '<html><body>Email us at info@acme.com or <a href="mailto:sales@acme.com">sales</a></body></html>'
        soup = BeautifulSoup(html, "lxml")
        results = _extract_contact_info(soup, "acme.com")
        emails = [fv for fv in results if fv.field_name == "email"]
        values = {e.field_value for e in emails}
        assert "info@acme.com" in values
        assert "sales@acme.com" in values

    def test_extract_contact_info_skips_bad_domains(self):
        from poc.website_scraper import _extract_contact_info
        from bs4 import BeautifulSoup
        html = '<html><body>user@example.com and user@sentry.io</body></html>'
        soup = BeautifulSoup(html, "lxml")
        results = _extract_contact_info(soup, "acme.com")
        emails = [fv for fv in results if fv.field_name == "email"]
        assert len(emails) == 0

    def test_full_enrich_with_mocked_http(self, sample_company):
        """Test the full enrich() method with mocked HTTP responses."""
        from poc import website_scraper
        from poc.website_scraper import WebsiteScraperProvider

        homepage_html = '''<html><head>
            <meta name="description" content="Acme makes widgets">
            <script type="application/ld+json">
            {"@type": "Organization", "foundingDate": "2015"}
            </script>
        </head><body>
            <a href="https://linkedin.com/company/acme">LinkedIn</a>
            Call: (555) 111-2222
        </body></html>'''

        mock_session = MagicMock()

        # robots.txt response
        robots_resp = MagicMock()
        robots_resp.status_code = 200
        robots_resp.text = "User-agent: *\nAllow: /"

        # Homepage response
        homepage_resp = MagicMock()
        homepage_resp.status_code = 200
        homepage_resp.content = homepage_html.encode()
        homepage_resp.headers = {}

        # HEAD for about/contact pages (404)
        head_resp = MagicMock()
        head_resp.status_code = 404

        def mock_get(url, **kwargs):
            if "robots.txt" in url:
                return robots_resp
            return homepage_resp

        mock_session.get = mock_get
        mock_session.head = MagicMock(return_value=head_resp)
        mock_session.headers = {}

        provider = WebsiteScraperProvider()
        # Mock the rate limiter to avoid sleeps
        provider._rate_limiter = MagicMock()
        provider._rate_limiter.acquire = MagicMock()

        with patch("poc.website_scraper.requests.Session", return_value=mock_session):
            results = provider.enrich({"domain": "acme.com"})

        names = {fv.field_name for fv in results}
        assert "description" in names
        assert "founded_year" in names
        assert "social_linkedin" in names
        assert "phone" in names

    def test_enrich_no_domain_returns_empty(self, tmp_db):
        from poc.website_scraper import WebsiteScraperProvider
        provider = WebsiteScraperProvider()
        results = provider.enrich({"name": "No Domain Corp"})
        assert results == []

    def test_enrich_uses_website_field(self, tmp_db):
        """Provider should fall back to website if domain is empty."""
        from poc.website_scraper import WebsiteScraperProvider, _normalize_url
        provider = WebsiteScraperProvider()
        provider._rate_limiter = MagicMock()
        provider._rate_limiter.acquire = MagicMock()

        mock_session = MagicMock()
        robots_resp = MagicMock()
        robots_resp.status_code = 404
        page_resp = MagicMock()
        page_resp.status_code = 200
        page_resp.content = b'<html><head><meta name="description" content="Hello"></head></html>'
        page_resp.headers = {}
        head_resp = MagicMock()
        head_resp.status_code = 404

        mock_session.get = MagicMock(side_effect=lambda url, **kw: robots_resp if "robots" in url else page_resp)
        mock_session.head = MagicMock(return_value=head_resp)
        mock_session.headers = {}

        with patch("poc.website_scraper.requests.Session", return_value=mock_session):
            results = provider.enrich({"website": "https://acme.com"})
        assert any(fv.field_name == "description" for fv in results)


# ===========================================================================
# Web tests (enrich button)
# ===========================================================================

class TestWebEnrich:
    @pytest.fixture()
    def client(self, tmp_db):
        from poc.web.app import create_app
        app = create_app()
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_detail_page_shows_enrich_button(self, client, sample_company):
        resp = client.get(f"/companies/{sample_company['id']}")
        assert resp.status_code == 200
        assert "Enrich" in resp.text

    def test_detail_page_no_enrich_without_domain(self, client, tmp_db):
        company = create_company("No Domain Corp")
        # Company has no domain or website, so should not show enrich button
        # Actually check — domain defaults to empty string
        resp = client.get(f"/companies/{company['id']}")
        assert resp.status_code == 200
        # The button is conditionally rendered only if domain or website exists
        assert 'hx-post' not in resp.text or 'enrich' not in resp.text

    def test_enrich_post_redirects(self, client, sample_company):
        """POST to enrich should redirect back to detail (with mocked enrichment)."""
        with patch("poc.enrichment_pipeline.execute_enrichment") as mock_enrich:
            mock_enrich.return_value = {
                "run_id": "test-run", "status": "completed",
                "fields_discovered": 0, "fields_applied": 0, "error": None,
            }
            resp = client.post(
                f"/companies/{sample_company['id']}/enrich",
                follow_redirects=False,
            )
            assert resp.status_code == 303
            assert f"/companies/{sample_company['id']}" in resp.headers.get("location", "")
