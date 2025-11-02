from django.test import Client, TestCase, override_settings

import json
from datetime import date, timedelta

from pgcommitfest.commitfest.models import CommitFest


@override_settings(AUTO_CREATE_COMMITFESTS=False)
class NeedsCIEndpointTestCase(TestCase):
    """Test the /api/v1/commitfests/needs_ci endpoint."""

    @classmethod
    def setUpTestData(cls):
        today = date.today()

        # Create test commitfests with various statuses
        cls.open_cf = CommitFest.objects.create(
            name="2025-01",
            status=CommitFest.STATUS_OPEN,
            startdate=today - timedelta(days=30),
            enddate=today + timedelta(days=30),
            draft=False,
        )

        cls.in_progress_cf = CommitFest.objects.create(
            name="2024-11",
            status=CommitFest.STATUS_INPROGRESS,
            startdate=today - timedelta(days=60),
            enddate=today + timedelta(days=0),
            draft=False,
        )

        # Previous CF that ended 3 days ago (should be included - within 7 day window)
        cls.recent_previous_cf = CommitFest.objects.create(
            name="2024-09",
            status=CommitFest.STATUS_CLOSED,
            startdate=today - timedelta(days=90),
            enddate=today - timedelta(days=3),
            draft=False,
        )

        # Old previous CF that ended 10 days ago (should be excluded - outside 7 day window)
        cls.old_previous_cf = CommitFest.objects.create(
            name="2024-07",
            status=CommitFest.STATUS_CLOSED,
            startdate=today - timedelta(days=120),
            enddate=today - timedelta(days=10),
            draft=False,
        )

        # Draft commitfest
        cls.draft_cf = CommitFest.objects.create(
            name="2025-03-draft",
            status=CommitFest.STATUS_OPEN,
            startdate=today + timedelta(days=60),
            enddate=today + timedelta(days=120),
            draft=True,
        )

    def setUp(self):
        self.client = Client()

    def test_endpoint_returns_200(self):
        """Test that the endpoint returns HTTP 200 OK."""
        response = self.client.get("/api/v1/commitfests/needs_ci")
        self.assertEqual(response.status_code, 200)

    def test_response_is_valid_json(self):
        """Test that the response is valid JSON."""
        response = self.client.get("/api/v1/commitfests/needs_ci")
        try:
            data = json.loads(response.content)
        except json.JSONDecodeError:
            self.fail("Response is not valid JSON")

        self.assertIn("commitfests", data)
        self.assertIsInstance(data["commitfests"], dict)

    def test_response_content_type(self):
        """Test that the response has correct Content-Type header."""
        response = self.client.get("/api/v1/commitfests/needs_ci")
        self.assertEqual(response["Content-Type"], "application/json")

    def test_cors_header_present(self):
        """Test that CORS header is present for API access."""
        response = self.client.get("/api/v1/commitfests/needs_ci")
        self.assertEqual(response["Access-Control-Allow-Origin"], "*")

    def test_includes_open_commitfest(self):
        """Test that open commitfests are included in response."""
        response = self.client.get("/api/v1/commitfests/needs_ci")
        data = json.loads(response.content)
        commitfests = data["commitfests"]

        # Should include the open commitfest
        self.assertIn("open", commitfests)
        self.assertEqual(commitfests["open"]["name"], self.open_cf.name)

    def test_includes_in_progress_commitfest(self):
        """Test that in-progress commitfests are included in response."""
        response = self.client.get("/api/v1/commitfests/needs_ci")
        data = json.loads(response.content)
        commitfests = data["commitfests"]

        # Should include the in-progress commitfest
        self.assertEqual(commitfests["in_progress"]["name"], self.in_progress_cf.name)

    def test_includes_recent_previous_commitfest(self):
        """Test that recently ended commitfests are included (within 7 days)."""
        response = self.client.get("/api/v1/commitfests/needs_ci")
        data = json.loads(response.content)
        commitfests = data["commitfests"]

        # Should include recent previous commitfest (ended 3 days ago)
        self.assertIsNotNone(commitfests["previous"])

    def test_excludes_old_previous_commitfest(self):
        """Test that old commitfests are excluded (older than 7 days)."""
        response = self.client.get("/api/v1/commitfests/needs_ci")
        data = json.loads(response.content)
        commitfests = data["commitfests"]

        # Should not include old previous commitfest (ended 10 days ago)
        self.assertNotEqual(
            commitfests["previous"]["name"],
            self.old_previous_cf.name,
            "Old previous commitfest should be excluded",
        )

    def test_excludes_next_open_and_final(self):
        """Test that next_open and final are excluded from response."""
        response = self.client.get("/api/v1/commitfests/needs_ci")
        data = json.loads(response.content)
        commitfests = data["commitfests"]

        # These keys should not be present in the response
        self.assertNotIn("next_open", commitfests)
        self.assertNotIn("final", commitfests)

    def test_response_structure(self):
        """Test that response has expected structure."""
        response = self.client.get("/api/v1/commitfests/needs_ci")
        data = json.loads(response.content)

        # Top-level structure
        self.assertIn("commitfests", data)
        self.assertIsInstance(data["commitfests"], dict)

        # Check that commitfest objects have expected fields
        commitfests = data["commitfests"]
        for key, cf_data in commitfests.items():
            self.assertIsInstance(cf_data, dict)
            # Basic fields that should be present
            self.assertIn("id", cf_data)
            self.assertIn("name", cf_data)
            self.assertIn("status", cf_data)
            self.assertIn("startdate", cf_data)
            self.assertIn("enddate", cf_data)
