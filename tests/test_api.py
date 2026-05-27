from fastapi.testclient import TestClient

from api.infra import database as db
from api.infra.publisher import Publisher
from api.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_pedido_returns_accepted(monkeypatch):
    monkeypatch.setattr(db, "init_db", lambda: None)
    monkeypatch.setattr(Publisher, "publish", lambda self, exchange, routing_key, body: True)

    with TestClient(app) as client:
        response = client.post(
            "/pedidos",
            json={"id": "1", "item": "cafe", "quantidade": 2},
        )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}


def test_get_pedidos_returns_saved_items(monkeypatch):
    expected = [
        {
            "id": "1",
            "item": "cafe",
            "quantidade": 2,
            "status": "processado",
            "received_at": "2026-05-27 00:00:00",
            "processed_at": None,
        }
    ]
    monkeypatch.setattr(db, "list_pedidos", lambda: expected)
    monkeypatch.setattr(db, "init_db", lambda: None)

    with TestClient(app) as client:
        response = client.get("/pedidos")

    assert response.status_code == 200
    assert response.json() == expected
