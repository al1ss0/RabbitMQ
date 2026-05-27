from unittest.mock import MagicMock
import pytest
import pika
from fastapi.testclient import TestClient

from api.infra import database as db
from api.infra.publisher import Publisher
from api.main import app

_PEDIDO_VALIDO = {"id": "1", "descricao": "Notebook ASUS", "valor": 3500.0}


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_pedido_returns_accepted(monkeypatch):
    monkeypatch.setattr(db, "init_db", lambda: None)
    monkeypatch.setattr(Publisher, "publish", lambda self, exchange, routing_key, body: True)

    with TestClient(app) as client:
        response = client.post("/pedidos", json=_PEDIDO_VALIDO)

    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}


def test_post_pedido_broker_falha(monkeypatch):
    monkeypatch.setattr(db, "init_db", lambda: None)
    monkeypatch.setattr(Publisher, "publish", lambda self, exchange, routing_key, body: False)

    with TestClient(app) as client:
        response = client.post("/pedidos", json=_PEDIDO_VALIDO)

    assert response.status_code == 500


def test_post_pedido_payload_invalido(monkeypatch):
    monkeypatch.setattr(db, "init_db", lambda: None)
    monkeypatch.setattr(Publisher, "publish", lambda self, exchange, routing_key, body: True)

    with TestClient(app) as client:
        response = client.post("/pedidos", json={"id": "1", "descricao": "Produto", "valor": -10})

    assert response.status_code == 422


def test_get_pedidos_returns_saved_items(monkeypatch):
    expected = [
        {
            "id": "1",
            "descricao": "Notebook ASUS",
            "valor": 3500.0,
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


# ── api/infra/database ────────────────────────────────────────────────────────

def test_api_init_db_and_list_pedidos(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "pedidos.db")
    db.init_db()
    result = db.list_pedidos()
    assert result == []


def test_api_save_and_list_pedidos(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "pedidos.db")
    db.init_db()

    from worker.infra import database as worker_db
    monkeypatch.setattr(worker_db, "DB_PATH", tmp_path / "pedidos.db")
    worker_db.save_pedido({"id": "1", "descricao": "Produto", "valor": 10.0}, status="processado")

    result = db.list_pedidos()
    assert len(result) == 1
    assert result[0]["id"] == "1"


# ── api/infra/publisher ───────────────────────────────────────────────────────

def test_publisher_publish_sucesso():
    mock_conn = MagicMock(spec=pika.BlockingConnection)
    mock_channel = MagicMock()
    mock_channel.basic_publish.return_value = None
    publisher = Publisher(mock_conn, mock_channel)
    result = publisher.publish("pedidos_exchange", "pedidos.novo", {"id": "1"})
    assert result is True


def test_publisher_publish_falha():
    mock_conn = MagicMock(spec=pika.BlockingConnection)
    mock_channel = MagicMock()
    mock_channel.basic_publish.side_effect = Exception("Broker down")
    publisher = Publisher(mock_conn, mock_channel)
    result = publisher.publish("pedidos_exchange", "pedidos.novo", {"id": "1"})
    assert result is False