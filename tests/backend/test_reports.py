"""
Tests for reports API endpoints and their filtering.
"""
import pytest


class TestQuarterlyReports:
    """Test suite for the quarterly reports endpoint."""

    def test_get_quarterly_reports(self, client):
        """Test getting quarterly performance reports."""
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        first = data[0]
        assert "quarter" in first
        assert "total_orders" in first
        assert "total_revenue" in first
        assert "avg_order_value" in first
        assert "fulfillment_rate" in first

    def test_quarters_are_sorted(self, client):
        """Test that quarters come back in chronological order."""
        data = client.get("/api/reports/quarterly").json()
        quarters = [q["quarter"] for q in data]
        assert quarters == sorted(quarters)

    def test_quarterly_value_types(self, client):
        """Test that quarterly figures are usable numbers."""
        data = client.get("/api/reports/quarterly").json()

        for quarter in data:
            assert isinstance(quarter["total_orders"], int)
            assert isinstance(quarter["total_revenue"], (int, float))
            assert isinstance(quarter["avg_order_value"], (int, float))
            assert quarter["total_orders"] > 0
            assert quarter["total_revenue"] >= 0
            assert 0 <= quarter["fulfillment_rate"] <= 100

    def test_avg_order_value_calculation(self, client):
        """Test that average order value is revenue divided by order count."""
        data = client.get("/api/reports/quarterly").json()

        for quarter in data:
            expected = quarter["total_revenue"] / quarter["total_orders"]
            assert abs(quarter["avg_order_value"] - expected) < 0.01

    def test_quarterly_totals_match_orders(self, client):
        """Test that quarterly order counts add up to the full order list."""
        orders = client.get("/api/orders").json()
        data = client.get("/api/reports/quarterly").json()

        assert sum(q["total_orders"] for q in data) == len(orders)

    def test_filter_by_warehouse(self, client):
        """Test that a warehouse filter narrows the quarterly figures."""
        unfiltered = client.get("/api/reports/quarterly").json()
        filtered = client.get("/api/reports/quarterly?warehouse=Tokyo").json()

        assert sum(q["total_orders"] for q in filtered) < sum(q["total_orders"] for q in unfiltered)

        tokyo_orders = client.get("/api/orders?warehouse=Tokyo").json()
        assert sum(q["total_orders"] for q in filtered) == len(tokyo_orders)

    def test_filter_by_category(self, client):
        """Test that a category filter narrows the quarterly figures."""
        filtered = client.get("/api/reports/quarterly?category=sensors").json()
        sensor_orders = client.get("/api/orders?category=sensors").json()

        assert sum(q["total_orders"] for q in filtered) == len(sensor_orders)

    def test_filter_by_status(self, client):
        """Test that a status filter gives a 100 percent fulfilment rate for Delivered."""
        filtered = client.get("/api/reports/quarterly?status=Delivered").json()

        for quarter in filtered:
            assert quarter["fulfillment_rate"] == 100.0

    def test_filter_by_month(self, client):
        """Test that a month filter leaves only that month's quarter."""
        filtered = client.get("/api/reports/quarterly?month=2025-03").json()

        assert len(filtered) == 1
        assert filtered[0]["quarter"] == "Q1-2025"

    def test_filter_by_quarter(self, client):
        """Test that a quarter filter leaves only that quarter."""
        filtered = client.get("/api/reports/quarterly?month=Q2-2025").json()

        assert len(filtered) == 1
        assert filtered[0]["quarter"] == "Q2-2025"

    def test_all_filter_value_is_ignored(self, client):
        """Test that the 'all' sentinel does not filter anything out."""
        unfiltered = client.get("/api/reports/quarterly").json()
        with_all = client.get(
            "/api/reports/quarterly?warehouse=all&category=all&status=all&month=all"
        ).json()

        assert with_all == unfiltered

    def test_multiple_filters(self, client):
        """Test combining filters on the quarterly report."""
        response = client.get("/api/reports/quarterly?warehouse=Tokyo&status=Delivered")
        assert response.status_code == 200

        data = response.json()
        matching = client.get("/api/orders?warehouse=Tokyo&status=Delivered").json()
        assert sum(q["total_orders"] for q in data) == len(matching)


class TestMonthlyTrends:
    """Test suite for the monthly trends endpoint."""

    def test_get_monthly_trends(self, client):
        """Test getting month-over-month trends."""
        response = client.get("/api/reports/monthly-trends")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        first = data[0]
        assert "month" in first
        assert "order_count" in first
        assert "revenue" in first
        assert "delivered_count" in first

    def test_months_are_sorted(self, client):
        """Test that months come back in chronological order."""
        data = client.get("/api/reports/monthly-trends").json()
        months = [m["month"] for m in data]
        assert months == sorted(months)

    def test_month_format(self, client):
        """Test that months use the YYYY-MM format the client parses."""
        data = client.get("/api/reports/monthly-trends").json()

        for entry in data:
            assert len(entry["month"]) == 7
            year, month = entry["month"].split("-")
            assert year.isdigit()
            assert 1 <= int(month) <= 12

    def test_delivered_count_never_exceeds_order_count(self, client):
        """Test that delivered orders are a subset of all orders in a month."""
        data = client.get("/api/reports/monthly-trends").json()

        for entry in data:
            assert entry["delivered_count"] <= entry["order_count"]

    def test_monthly_totals_match_orders(self, client):
        """Test that monthly order counts add up to the full order list."""
        orders = client.get("/api/orders").json()
        data = client.get("/api/reports/monthly-trends").json()

        assert sum(m["order_count"] for m in data) == len(orders)

    def test_monthly_revenue_matches_quarterly(self, client):
        """Test that the two report endpoints agree on total revenue."""
        monthly = client.get("/api/reports/monthly-trends").json()
        quarterly = client.get("/api/reports/quarterly").json()

        monthly_total = sum(m["revenue"] for m in monthly)
        quarterly_total = sum(q["total_revenue"] for q in quarterly)
        assert abs(monthly_total - quarterly_total) < 0.01

    def test_filter_by_warehouse(self, client):
        """Test that a warehouse filter narrows the monthly trends."""
        filtered = client.get("/api/reports/monthly-trends?warehouse=London").json()
        london_orders = client.get("/api/orders?warehouse=London").json()

        assert sum(m["order_count"] for m in filtered) == len(london_orders)

    def test_filter_by_month_leaves_one_entry(self, client):
        """Test that a month filter reduces the trend to a single month."""
        filtered = client.get("/api/reports/monthly-trends?month=2025-03").json()

        assert len(filtered) == 1
        assert filtered[0]["month"] == "2025-03"

    def test_filter_by_category(self, client):
        """Test that a category filter narrows the monthly trends."""
        filtered = client.get("/api/reports/monthly-trends?category=actuators").json()
        actuator_orders = client.get("/api/orders?category=actuators").json()

        assert sum(m["order_count"] for m in filtered) == len(actuator_orders)

    def test_filters_agree_across_report_endpoints(self, client):
        """Test that both report endpoints apply the same filter consistently."""
        quarterly = client.get("/api/reports/quarterly?warehouse=Tokyo").json()
        monthly = client.get("/api/reports/monthly-trends?warehouse=Tokyo").json()

        assert sum(q["total_orders"] for q in quarterly) == sum(m["order_count"] for m in monthly)

    def test_restrictive_filter_returns_empty_list(self, client):
        """Test that a filter matching no orders returns an empty report."""
        response = client.get("/api/reports/monthly-trends?warehouse=Atlantis")
        assert response.status_code == 200
        assert response.json() == []
