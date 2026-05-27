import json
from unittest.mock import MagicMock, patch

import pytest

from worker.infra import database as worker_db
from worker.infra.consumer import handle_message
from worker.infra.topology import setup_topology
from worker.domain.models import Pedido


# ── database ──────────────────────────────────────────────────────────────────

def test_init_db_and_save_pedido(tmp_path, monkeypatch):
    test_db_path = tmp_path / "pedidos.db"
    monkeypatch.setattr(worker_db, "DB_PATH", test_db_path)
    worker_db.init_db()
    payload = {"id": "1", "descricao": "Notebook ASUS", "valor": 3500.0}
    worker_db.save_pedido(payload, status="processado")

    with worker_db.get_connection() as connection:
        row = connection.execute(
            "SELECT id, descricao, valor, status FROM pedidos WHERE id = ?",
            (payload["id"],),
        ).fetchone()

    assert row is not None
    assert row["descricao"] == "Notebook ASUS"
    assert row["valor"] == 3500.0
    assert row["status"] == "processado"


def test_save_pedido_atualiza_existente(tmp_path, monkeypatch):
    test_db_path = tmp_path / "pedidos.db"
    monkeypatch.setattr(worker_db, "DB_PATH", test_db_path)
    worker_db.init_db()
    payload = {"id": "1", "descricao": "Produto", "valor": 10.0}
    worker_db.save_pedido(payload, status="processado")
    worker_db.save_pedido(payload, status="erro")

    with worker_db.get_connection() as connection:
        row = connection.execute(
            "SELECT status FROM pedidos WHERE id = ?", ("1",)
        ).fetchone()

    assert row["status"] == "erro"


# ── models ────────────────────────────────────────────────────────────────────

def test_pedido_model_campos():
    p = Pedido(id="1", descricao="Produto", valor=10.0, status="PENDENTE")
    assert p.id == "1"
    assert p.descricao == "Produto"
    assert p.valor == 10.0
    assert p.status == "PENDENTE"


def test_pedido_model_imutavel():
    p = Pedido(id="1", descricao="Produto", valor=10.0, status="PENDENTE")
    with pytest.raises(Exception):
        p.status = "alterado"  # type: ignore

# ── consumer ──────────────────────────────────────────────────────────────────

def test_handle_message_sucesso(tmp_path, monkeypatch):
    test_db_path = tmp_path / "pedidos.db"
    monkeypatch.setattr(worker_db, "DB_PATH", test_db_path)
    worker_db.init_db()

    body = json.dumps({"id": "1", "descricao": "Produto", "valor": 10.0}).encode()
    handle_message(body)

    with worker_db.get_connection() as connection:
        row = connection.execute(
            "SELECT status FROM pedidos WHERE id = ?", ("1",)
        ).fetchone()

    assert row["status"] == "processado"


def test_handle_message_payload_invalido():
    body = json.dumps({"id": "99"}).encode()
    with pytest.raises(KeyError):
        handle_message(body)


# ── topology ──────────────────────────────────────────────────────────────────

def test_setup_topology_chama_declares():
    mock_channel = MagicMock()
    setup_topology(mock_channel)
    assert mock_channel.exchange_declare.call_count == 2
    assert mock_channel.queue_declare.call_count == 2
    assert mock_channel.queue_bind.call_count == 2