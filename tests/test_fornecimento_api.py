import uuid

from server import create_app


def test_fornecimento_solicitacoes_crud():
    app, _, init_db, migrate_db = create_app()
    app.testing = True

    marker = f"codex-test-{uuid.uuid4().hex[:8]}"
    created_ids = []

    with app.app_context():
        init_db()
        migrate_db()
        conn = app._get_db()
        conn.execute(
            "DELETE FROM fornecimento_solicitacoes WHERE solicitante LIKE ?",
            (f"{marker}%",),
        )
        conn.commit()

    client = app.test_client()
    payload = {
        "solicitante": marker,
        "empresa": "Empresa Teste",
        "data": "2026-04-10",
        "obs": "Observacao teste",
        "items": [
            {"nome": "Caneta", "desc": "Azul", "qtd": "2", "preco": "3,50"},
            {"nome": "Papel", "desc": "A4", "qtd": "1", "preco": "10,00"},
        ],
    }

    try:
        response = client.post("/api/fornecimento/solicitacoes", json=payload)
        assert response.status_code == 201
        created = response.get_json()
        created_ids.append(created["id"])
        assert created["solicitante"] == marker
        assert created["total_itens"] == 2
        assert created["valor_total"] == 17.0
        assert len(created["items"]) == 2

        response = client.get(f"/api/fornecimento/solicitacoes?q={marker}")
        assert response.status_code == 200
        listed = response.get_json()
        assert any(item["id"] == created["id"] for item in listed)

        update_payload = {
            **payload,
            "empresa": "Empresa Atualizada",
            "items": [{"nome": "Agenda", "desc": "", "qtd": "3", "preco": "12"}],
        }
        response = client.put(
            f"/api/fornecimento/solicitacoes/{created['id']}",
            json=update_payload,
        )
        assert response.status_code == 200
        updated = response.get_json()
        assert updated["empresa"] == "Empresa Atualizada"
        assert updated["total_itens"] == 1
        assert updated["valor_total"] == 36.0

        response = client.post(
            f"/api/fornecimento/solicitacoes/{created['id']}/duplicate"
        )
        assert response.status_code == 201
        duplicated = response.get_json()
        created_ids.append(duplicated["id"])
        assert duplicated["id"] != created["id"]
        assert duplicated["solicitante"] == marker

        response = client.delete(f"/api/fornecimento/solicitacoes/{created['id']}")
        assert response.status_code == 200
        assert response.get_json()["ok"] is True
    finally:
        if created_ids:
            with app.app_context():
                conn = app._get_db()
                conn.executemany(
                    "DELETE FROM fornecimento_solicitacoes WHERE id=?",
                    [(item_id,) for item_id in created_ids],
                )
                conn.commit()
