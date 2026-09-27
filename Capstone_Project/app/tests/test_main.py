from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "k3s-capstone-app"


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_items_empty():
    response = client.get("/items")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_and_list_item():
    create_response = client.post("/items", json={"name": "widget"})
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "widget"
    assert "id" in created

    list_response = client.get("/items")
    assert list_response.status_code == 200
    assert any(item["id"] == created["id"] and item["name"] == "widget" for item in list_response.json())


def test_get_item_not_found():
    response = client.get("/items/999999")
    assert response.status_code == 404
