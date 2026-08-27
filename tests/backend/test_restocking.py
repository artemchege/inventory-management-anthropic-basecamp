"""
Tests for restocking API endpoints and the demand forecast fields they depend on.
"""
from datetime import datetime

import pytest

import main


@pytest.fixture(autouse=True)
def clean_restock_store():
    """Reset the in-memory restocking store so each test starts from empty."""
    main.submitted_restock_orders.clear()
    yield
    main.submitted_restock_orders.clear()


def build_order(items=None, budget=None, warehouse="San Francisco"):
    """Build a valid create-restock-order payload."""
    if items is None:
        items = [
            {
                "sku": "WDG-001",
                "name": "Industrial Widget Type A",
                "quantity": 150,
                "unit_price": 28.50,
            }
        ]

    payload = {"items": items, "warehouse": warehouse}
    if budget is not None:
        payload["budget"] = budget
    return payload


class TestRestockingEndpoints:
    """Test suite for restocking order endpoints."""

    def test_get_restock_orders_empty_initially(self, client):
        """Test that no restocking orders exist before any are submitted."""
        response = client.get("/api/restocking/orders")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_create_restock_order(self, client):
        """Test submitting a restocking order."""
        response = client.post("/api/restocking/orders", json=build_order(budget=7000))
        assert response.status_code == 201

        order = response.json()
        assert "id" in order
        assert "order_number" in order
        assert "items" in order
        assert "status" in order
        assert "order_date" in order
        assert "expected_delivery" in order
        assert "total_value" in order
        assert "lead_time_days" in order

        assert order["status"] == "Processing"
        assert order["customer"] == "Internal Restocking"
        assert order["warehouse"] == "San Francisco"
        assert order["actual_delivery"] is None

    def test_created_order_appears_in_list(self, client):
        """Test that a submitted order is returned by the list endpoint."""
        create_response = client.post("/api/restocking/orders", json=build_order())
        created = create_response.json()

        response = client.get("/api/restocking/orders")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["order_number"] == created["order_number"]

    def test_order_numbers_are_sequential_and_prefixed(self, client):
        """Test that order numbers use the RSO prefix and never collide."""
        first = client.post("/api/restocking/orders", json=build_order()).json()
        second = client.post("/api/restocking/orders", json=build_order()).json()

        year = datetime.now().year
        assert first["order_number"] == f"RSO-{year}-0001"
        assert second["order_number"] == f"RSO-{year}-0002"
        assert first["order_number"] != second["order_number"]

    def test_restock_order_numbers_do_not_collide_with_customer_orders(self, client):
        """Test that restocking order numbers stay clear of the ORD- series."""
        created = client.post("/api/restocking/orders", json=build_order()).json()

        existing = client.get("/api/orders").json()
        existing_numbers = {order["order_number"] for order in existing}

        assert created["order_number"].startswith("RSO-")
        assert created["order_number"] not in existing_numbers

    def test_total_value_calculation(self, client):
        """Test that total value is the sum of quantity times unit price."""
        items = [
            {"sku": "WDG-001", "name": "Industrial Widget Type A", "quantity": 150, "unit_price": 28.50},
            {"sku": "CTL-330", "name": "Logic Controller Board", "quantity": 1, "unit_price": 28.90},
        ]
        response = client.post("/api/restocking/orders", json=build_order(items=items))
        order = response.json()

        calculated_total = sum(item["quantity"] * item["unit_price"] for item in items)
        assert abs(order["total_value"] - calculated_total) < 0.01

    def test_lead_time_uses_slowest_category(self, client):
        """Test that lead time comes from the slowest category in the order."""
        items = [
            # Power Supplies is 10 days, Circuit Boards is 21 - the order quotes 21
            {"sku": "PSU-501", "name": "5V 10A Switching Power Supply", "quantity": 2, "unit_price": 18.99},
            {"sku": "WDG-001", "name": "Industrial Widget Type A", "quantity": 150, "unit_price": 28.50},
        ]
        response = client.post("/api/restocking/orders", json=build_order(items=items))
        assert response.json()["lead_time_days"] == 21

    def test_lead_time_for_single_category(self, client):
        """Test that a single-category order uses that category's lead time."""
        items = [
            {"sku": "PSU-501", "name": "5V 10A Switching Power Supply", "quantity": 2, "unit_price": 18.99}
        ]
        order = client.post("/api/restocking/orders", json=build_order(items=items)).json()

        assert order["lead_time_days"] == 10
        assert order["category"] == "Power Supplies"

    def test_mixed_category_order_is_labelled_mixed(self, client):
        """Test that an order spanning categories is labelled Mixed."""
        items = [
            {"sku": "PSU-501", "name": "5V 10A Switching Power Supply", "quantity": 2, "unit_price": 18.99},
            {"sku": "SNR-420", "name": "Temperature Sensor Module", "quantity": 2, "unit_price": 89.50},
        ]
        order = client.post("/api/restocking/orders", json=build_order(items=items)).json()
        assert order["category"] == "Mixed"

    def test_expected_delivery_matches_lead_time(self, client):
        """Test that expected delivery is the order date plus the lead time."""
        order = client.post("/api/restocking/orders", json=build_order()).json()

        order_date = datetime.strptime(order["order_date"], "%Y-%m-%dT%H:%M:%S")
        expected_delivery = datetime.strptime(order["expected_delivery"], "%Y-%m-%dT%H:%M:%S")

        assert (expected_delivery - order_date).days == order["lead_time_days"]

    def test_order_items_structure(self, client):
        """Test that submitted order items keep the standard item shape."""
        order = client.post("/api/restocking/orders", json=build_order()).json()

        assert isinstance(order["items"], list)
        for item in order["items"]:
            assert "sku" in item
            assert "name" in item
            assert "quantity" in item
            assert "unit_price" in item
            assert isinstance(item["quantity"], int)
            assert isinstance(item["unit_price"], (int, float))
            assert item["quantity"] > 0

    def test_create_restock_order_without_budget(self, client):
        """Test that a budget is optional."""
        response = client.post("/api/restocking/orders", json=build_order())
        assert response.status_code == 201
        assert response.json()["budget"] is None

    def test_create_restock_order_rejects_empty_items(self, client):
        """Test that an order with no items is rejected."""
        response = client.post("/api/restocking/orders", json={"items": []})
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data
        assert "at least one item" in data["detail"].lower()

    def test_create_restock_order_rejects_zero_quantity(self, client):
        """Test that an item with no quantity is rejected."""
        items = [{"sku": "WDG-001", "name": "Industrial Widget Type A", "quantity": 0, "unit_price": 28.50}]
        response = client.post("/api/restocking/orders", json=build_order(items=items))
        assert response.status_code == 400

        data = response.json()
        assert "quantity" in data["detail"].lower()

    def test_create_restock_order_rejects_over_budget(self, client):
        """Test that an order costing more than the budget is rejected."""
        response = client.post("/api/restocking/orders", json=build_order(budget=10))
        assert response.status_code == 400

        data = response.json()
        assert "budget" in data["detail"].lower()

    def test_rejected_order_is_not_stored(self, client):
        """Test that a rejected order never reaches the list endpoint."""
        client.post("/api/restocking/orders", json=build_order(budget=10))

        response = client.get("/api/restocking/orders")
        assert len(response.json()) == 0

    def test_create_restock_order_validates_payload(self, client):
        """Test that a malformed item payload fails validation."""
        items = [{"sku": "WDG-001", "quantity": 5}]
        response = client.post("/api/restocking/orders", json=build_order(items=items))
        assert response.status_code == 422

    def test_restock_orders_stay_out_of_customer_orders(self, client):
        """Test that restocking orders do not appear in the customer orders feed."""
        before = len(client.get("/api/orders").json())

        client.post("/api/restocking/orders", json=build_order())

        after = client.get("/api/orders").json()
        assert len(after) == before
        assert all(not order["order_number"].startswith("RSO-") for order in after)


class TestDemandForecastRestockingFields:
    """Test suite for the demand forecast fields restocking depends on."""

    def test_forecasts_expose_category_and_unit_cost(self, client):
        """Test that every forecast carries the fields the budget math needs."""
        response = client.get("/api/demand")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0

        for forecast in data:
            assert "category" in forecast
            assert "unit_cost" in forecast
            assert forecast["category"] is not None
            assert forecast["unit_cost"] is not None

    def test_forecast_unit_costs_are_positive_numbers(self, client):
        """Test that unit costs are usable in a budget calculation."""
        data = client.get("/api/demand").json()

        for forecast in data:
            assert isinstance(forecast["unit_cost"], (int, float))
            assert forecast["unit_cost"] > 0

    def test_forecast_categories_have_known_lead_times(self, client):
        """Test that every forecast category maps to a configured lead time."""
        data = client.get("/api/demand").json()

        for forecast in data:
            assert forecast["category"] in main.RESTOCK_LEAD_TIMES

    def test_forecast_categories_match_inventory_categories(self, client):
        """Test that forecast categories are real inventory categories."""
        inventory = client.get("/api/inventory").json()
        inventory_categories = {item["category"] for item in inventory}

        data = client.get("/api/demand").json()
        for forecast in data:
            assert forecast["category"] in inventory_categories
