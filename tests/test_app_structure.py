"""
tests/test_app_structure.py - Testes da estrutura modular (Atualizado para server.py)
"""

import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Usar banco de dados temporário de testes para evitar travar o de produção
import server  # noqa: E402
TEST_DB_PATH = os.path.join(BASE_DIR, "test_empenhos.db")
server.DB_PATH = TEST_DB_PATH


def _safe_print(message):
    text = str(message)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))


def test_imports():
    """Testa todos os imports ativos (server.py + routes/)."""
    _safe_print("=" * 60)
    _safe_print("TESTANDO IMPORTS ATIVOS")
    _safe_print("=" * 60)

    from server import create_app  # noqa: F401
    _safe_print("[OK] server.create_app")

    from routes.helpers import (  # noqa: F401
        normalizar_cnpj, cnpj_valido, parse_bool, slugify
    )
    _safe_print("[OK] routes.helpers")

    blueprints = [
        ("auth",               "routes.auth"),
        ("config",             "routes.config"),
        ("credores",           "routes.credores"),
        ("empenhos",           "routes.empenhos"),
        ("rpas",               "routes.rpas"),
        ("mural",              "routes.mural"),
        ("kanban",             "routes.kanban"),
        ("documentos",         "routes.documentos"),
        ("prazos",             "routes.prazos"),
        ("protocolos",         "routes.protocolos"),
        ("extratos",           "routes.extratos"),
        ("ia",                 "routes.ia"),
        ("cnpj",               "routes.cnpj"),
        ("pdf",                "routes.pdf"),
        ("despesas",           "routes.despesas"),
        ("classificador",      "routes.classificador"),
        ("empenho_assistente", "routes.empenho_assistente"),
    ]

    for name, module in blueprints:
        mod = __import__(module, fromlist=["bp"])
        bp = getattr(mod, "bp")
        assert bp is not None, f"Blueprint '{name}' nao encontrado em {module}"
        _safe_print(f"[OK] {name} (bp: {bp.name})")


def test_helpers():
    """Testa funcoes auxiliares de routes/helpers.py e routes/documentos.py."""
    _safe_print("")
    _safe_print("=" * 60)
    _safe_print("TESTANDO HELPERS")
    _safe_print("=" * 60)

    from routes.helpers import normalizar_cnpj, cnpj_valido, parse_bool, slugify
    from routes.documentos import _normalize_phone_br

    # normalizar_cnpj
    assert normalizar_cnpj("12.345.678/0001-99") == "12345678000199"
    assert normalizar_cnpj("12345678000199") == "12345678000199"
    assert normalizar_cnpj("") == ""
    _safe_print("[OK] normalizar_cnpj")

    # cnpj_valido
    assert cnpj_valido("12.345.678/0001-95") is True
    assert cnpj_valido("12345678000195") is True
    assert cnpj_valido("11.111.111/1111-11") is False
    assert cnpj_valido("12.345.678/0001-99") is False
    _safe_print("[OK] cnpj_valido")

    # parse_bool
    assert parse_bool(True) is True
    assert parse_bool("true") is True
    assert parse_bool("1") is True
    assert parse_bool("yes") is True
    assert parse_bool("on") is True
    assert parse_bool("sim") is True
    assert parse_bool(False) is False
    assert parse_bool("false") is False
    assert parse_bool("0") is False
    assert parse_bool("") is False
    _safe_print("[OK] parse_bool")

    # slugify
    assert slugify("Teste Com Acento") == "teste-com-acento"
    assert slugify("Especial: @#$%") == "especial"
    assert slugify("") == "geral"
    _safe_print("[OK] slugify")

    # _normalize_phone_br  (definido em routes/documentos.py)
    assert _normalize_phone_br("(65) 99999-9999") == "+5565999999999"
    assert _normalize_phone_br("65999999999") == "+5565999999999"
    _safe_print("[OK] _normalize_phone_br")


def test_app_factory():
    """Testa criacao do app e registro de blueprints."""
    _safe_print("")
    _safe_print("=" * 60)
    _safe_print("TESTANDO APP FACTORY")
    _safe_print("=" * 60)

    from server import create_app

    app, _, _, _ = create_app()
    _safe_print(f"[OK] App criado: {app.name}")

    expected_blueprints = [
        "auth", "config", "credores", "empenhos", "rpas",
        "mural", "kanban", "documentos", "autentique", "prazos", "protocolos",
        "extratos", "ia", "cnpj", "pdf", "despesas",
        "classificador", "empenho_assistente",
    ]

    registered = list(app.blueprints.keys())
    missing = [bp for bp in expected_blueprints if bp not in registered]
    for bp_name in expected_blueprints:
        if bp_name in registered:
            _safe_print(f"[OK] Blueprint '{bp_name}' registrado")
        else:
            _safe_print(f"[ERRO] Blueprint '{bp_name}' NAO registrado")

    assert not missing, f"Blueprints NAO registrados: {missing}"

    rules = [str(r) for r in app.url_map.iter_rules()]
    static_routes = ["/", "/static/<path:filename>", "/<path:filename>"]
    for route in static_routes:
        if any(route.replace("<path:filename>", "test") in r for r in rules):
            _safe_print(f"[OK] Rota estatica: {route}")


def test_db_connection():
    """Testa conexao com banco de dados usando banco temporario isolado."""
    _safe_print("")
    _safe_print("=" * 60)
    _safe_print("TESTANDO BANCO DE DADOS DE TESTES")
    _safe_print("=" * 60)

    # Remover db de teste antigo se existir
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    from server import create_app

    app, _, init_db, migrate_db = create_app()

    missing_tables = []
    try:
        with app.app_context():
            init_db()
            _safe_print("[OK] init_db() executado")
            migrate_db()
            _safe_print("[OK] migrate_db() executado")

            # app._get_db é exposto pelo server.py:
            #   app._get_db = get_db  (linha ~592)
            # Funciona no app_context sem necessitar de um request real.
            conn = app._get_db()
            result = conn.execute("SELECT 1").fetchone()
            assert result[0] == 1
            _safe_print("[OK] Conexao DB funcional")

            tables = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()

            expected_tables = [
                "credores", "empenhos", "rpas", "kanban_tasks",
                "mural_recados", "mural_anexos", "mural_comentarios",
                "configuracoes", "logs", "documentos_centro",
                "autentique_envios", "autentique_contatos",
                "fornecimento_solicitacoes", "fornecimento_solicitacao_itens",
            ]

            table_names = [t["name"] for t in tables]
            for table in expected_tables:
                if table in table_names:
                    _safe_print(f"[OK] Tabela '{table}' existe")
                else:
                    _safe_print(f"[ERRO] Tabela '{table}' nao encontrada")
                    missing_tables.append(table)
    finally:
        # Sempre limpa o db de teste ao final
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass

    assert not missing_tables, f"Tabelas nao encontradas: {missing_tables}"


# ── Suporte a unittest runner ────────────────────────────────
def test_mural_api_guards():
    """Testa protecao e validacao basica das rotas do mural."""
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    from server import create_app

    app, _, init_db, migrate_db = create_app()
    try:
        with app.app_context():
            init_db()
            migrate_db()

        client = app.test_client()
        assert client.get("/api/mural").status_code == 403

        with client.session_transaction() as sess:
            sess["usuario_id"] = 1
            sess["usuario_nome"] = "Teste"
            sess["usuario_nivel"] = "admin"

        created = client.post(
            "/api/mural",
            json={
                "titulo": "Recado",
                "conteudo": "Conteudo",
                "prioridade": "urgente",
                "categoria": "aviso",
            },
        )
        assert created.status_code == 201
        recado_id = created.get_json()["id"]

        invalid = client.put(f"/api/mural/{recado_id}", json={"status": "perdido"})
        assert invalid.status_code == 400

        missing_comment = client.post("/api/mural/999999/comments", json={"texto": "Oi"})
        assert missing_comment.status_code == 404
    finally:
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass


def test_protocolos_api():
    """Testa cadastro de protocolos, upload de anexos (PDFs) e download."""
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    from server import create_app
    import io

    app, _, init_db, migrate_db = create_app()
    try:
        with app.app_context():
            init_db()
            migrate_db()

        client = app.test_client()

        # 1. Obter próximo número
        res_num = client.get("/api/protocolos/proximo-numero")
        assert res_num.status_code == 200
        numero = res_num.get_json()["numero"]
        assert "PROT-" in numero

        # 2. Criar protocolo
        res_create = client.post(
            "/api/protocolos",
            json={
                "numero": numero,
                "tipo": "oficio",
                "direcao": "enviado",
                "origem_destino": "Setor de Finanças",
                "assunto": "Remessa de Balancete Mensal",
                "data_protocolo": "2026-05-29",
                "prazo_resposta": "2026-06-15",
                "observacoes": "PDF em anexo",
            },
        )
        assert res_create.status_code == 201
        data = res_create.get_json()
        assert data["id"] is not None
        assert data["origem_destino"] == "Setor de Finanças"
        assert data["assunto"] == "Remessa de Balancete Mensal"
        prot_id = data["id"]

        # 3. Listar protocolos (e filtrar por busca 'Finanças')
        res_list = client.get("/api/protocolos?busca=Finanças")
        assert res_list.status_code == 200
        list_data = res_list.get_json()
        assert list_data["total"] >= 1
        assert list_data["items"][0]["origem_destino"] == "Setor de Finanças"

        # 4. Upload de anexo PDF fictício
        dummy_pdf_content = b"%PDF-1.4 dummy pdf content for testing protocols"
        res_upload = client.post(
            f"/api/protocolos/{prot_id}/anexos",
            data={
                "arquivo": (io.BytesIO(dummy_pdf_content), "balancete.pdf", "application/pdf")
            },
            content_type="multipart/form-data",
        )
        assert res_upload.status_code == 201
        upload_data = res_upload.get_json()
        assert upload_data["id"] is not None
        assert upload_data["file_name"] == "balancete.pdf"
        anexo_id = upload_data["id"]

        # 5. Listar anexos
        res_anexos = client.get(f"/api/protocolos/{prot_id}/anexos")
        assert res_anexos.status_code == 200
        anexos_list = res_anexos.get_json()
        assert len(anexos_list) == 1
        assert anexos_list[0]["file_name"] == "balancete.pdf"

        # 6. Download de anexo
        res_download = client.get(f"/api/protocolos/{prot_id}/anexos/{anexo_id}/download")
        assert res_download.status_code == 200
        assert res_download.data == dummy_pdf_content

        # 7. Excluir anexo
        res_del_anexo = client.delete(f"/api/protocolos/{prot_id}/anexos/{anexo_id}")
        assert res_del_anexo.status_code == 200

        # 8. Excluir protocolo
        res_delete = client.delete(f"/api/protocolos/{prot_id}")
        assert res_delete.status_code == 200
    finally:
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass


def test_fornecimento_solicitacoes_api():
    """Testa cadastro, listagem, edicao, clonagem e exclusao de solicitacoes de fornecimento."""
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    from server import create_app

    app, _, init_db, migrate_db = create_app()
    try:
        with app.app_context():
            init_db()
            migrate_db()

        client = app.test_client()

        # 1. Criar solicitacao
        res_create = client.post(
            "/api/fornecimento/solicitacoes",
            json={
                "solicitante": "Joao da Silva",
                "empresa": "Material de Escritorio SA",
                "data": "30/05/2026",
                "obs": "Urgente",
                "items": [
                    {"nome": "Caneta", "desc": "Azul", "qtd": "10", "preco": "2,50"},
                    {"nome": "Papel A4", "desc": "Resma", "qtd": "5", "preco": "25,00"}
                ]
            }
        )
        assert res_create.status_code == 201
        data = res_create.get_json()
        assert data["id"] is not None
        assert data["solicitante"] == "Joao da Silva"
        assert len(data["items"]) == 2
        assert data["valor_total"] == 150.0 # 10*2.5 + 5*25 = 25 + 125 = 150
        sol_id = data["id"]

        # 2. Listar solicitacoes
        res_list = client.get("/api/fornecimento/solicitacoes")
        assert res_list.status_code == 200
        list_data = res_list.get_json()
        assert len(list_data) >= 1
        assert list_data[0]["id"] == sol_id

        # 3. Filtrar com busca
        res_search = client.get("/api/fornecimento/solicitacoes?q=Escritorio")
        assert res_search.status_code == 200
        assert len(res_search.get_json()) >= 1

        res_search_empty = client.get("/api/fornecimento/solicitacoes?q=Inexistente")
        assert res_search_empty.status_code == 200
        assert len(res_search_empty.get_json()) == 0

        # 4. Atualizar solicitacao (PUT)
        res_update = client.put(
            f"/api/fornecimento/solicitacoes/{sol_id}",
            json={
                "solicitante": "Joao da Silva Alterado",
                "empresa": "Material de Escritorio SA",
                "data": "30/05/2026",
                "obs": "Nao tao urgente",
                "items": [
                    {"nome": "Caneta", "desc": "Preta", "qtd": "20", "preco": "2,50"}
                ]
            }
        )
        assert res_update.status_code == 200
        up_data = res_update.get_json()
        assert up_data["solicitante"] == "Joao da Silva Alterado"
        assert len(up_data["items"]) == 1
        assert up_data["items"][0]["desc"] == "Preta"
        assert up_data["valor_total"] == 50.0

        # 5. Clonar solicitacao (POST /duplicate)
        res_clone = client.post(f"/api/fornecimento/solicitacoes/{sol_id}/duplicate")
        assert res_clone.status_code == 201
        clone_data = res_clone.get_json()
        assert clone_data["id"] is not None
        assert clone_data["id"] != sol_id
        assert clone_data["solicitante"] == "Joao da Silva Alterado"
        assert len(clone_data["items"]) == 1
        clone_id = clone_data["id"]

        # 6. Excluir solicitacoes
        res_del1 = client.delete(f"/api/fornecimento/solicitacoes/{sol_id}")
        assert res_del1.status_code == 200
        
        res_del2 = client.delete(f"/api/fornecimento/solicitacoes/{clone_id}")
        assert res_del2.status_code == 200

        # Verificacao de cascateamento
        with app.app_context():
            conn = app._get_db()
            items_left = conn.execute("SELECT COUNT(*) FROM fornecimento_solicitacao_itens").fetchone()[0]
            assert items_left == 0
            
    finally:
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass


def run_all_tests():
    """Executa todos os testes (uso direto: python tests/test_app_structure.py)."""
    _safe_print("")
    _safe_print("=" * 60)
    _safe_print("TESTES DA ESTRUTURA MODULAR ATIVA")
    _safe_print("=" * 60)
    _safe_print("")

    tests = [
        ("Imports",      test_imports),
        ("Helpers",      test_helpers),
        ("App Factory",  test_app_factory),
        ("Banco de Dados", test_db_connection),
        ("Mural API",    test_mural_api_guards),
        ("Protocolos API", test_protocolos_api),
        ("Fornecimento API", test_fornecimento_solicitacoes_api),
    ]

    results = []
    for name, test_func in tests:
        try:
            test_func()
            results.append((name, True, None))
        except Exception as e:
            results.append((name, False, str(e)))
            _safe_print(f"\n[ERRO] {name} falhou: {e}")

    _safe_print("")
    _safe_print("=" * 60)
    _safe_print("RESUMO")
    _safe_print("=" * 60)

    passed = sum(1 for _, r, _ in results if r)
    total = len(results)

    for name, result, error in results:
        status = "[OK] PASSOU" if result else "[ERRO] FALHOU"
        if error:
            status += f" ({error})"
        _safe_print(f"{status}: {name}")

    _safe_print("")
    _safe_print(f"Total: {passed}/{total} testes passaram")

    if passed == total:
        _safe_print("")
        _safe_print("TODOS OS TESTES PASSARAM!")
        return True

    _safe_print("")
    _safe_print("ALGUNS TESTES FALHARAM")
    return False


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for fn in (
        test_imports,
        test_helpers,
        test_app_factory,
        test_db_connection,
        test_mural_api_guards,
        test_protocolos_api,
        test_fornecimento_solicitacoes_api,
    ):
        suite.addTest(unittest.FunctionTestCase(fn))
    return suite


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
