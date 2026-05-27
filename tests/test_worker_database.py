from worker.infra import database as worker_db


def test_init_db_and_save_pedido(tmp_path, monkeypatch):
    test_db_path = tmp_path / "pedidos.db"
    monkeypatch.setattr(worker_db, "DB_PATH", test_db_path)

    worker_db.init_db()
    payload = {"id": "1", "item": "cafe", "quantidade": 2}
    worker_db.save_pedido(payload, status="processado")

    with worker_db.get_connection() as connection:
        row = connection.execute(
            "SELECT id, item, quantidade, status FROM pedidos WHERE id = ?",
            (payload["id"],),
        ).fetchone()

    assert row is not None
    assert row["item"] == "cafe"
    assert row["status"] == "processado"
