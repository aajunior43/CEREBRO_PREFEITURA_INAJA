"""
tests/test_app_structure.py - Testes da estrutura modular
"""

import os
import sys
import unittest


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)


def _safe_print(message):
    text = str(message)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))


def test_imports():
    """Testa todos os imports."""
    _safe_print("=" * 60)
    _safe_print("TESTANDO IMPORTS")
    _safe_print("=" * 60)

    try:
        from app import create_app  # noqa: F401
        _safe_print("[OK] app.create_app")
    except Exception as e:
        _safe_print(f"[ERRO] app.create_app: {e}")
        return False

    try:
        from app.utils.db import get_db, init_db  # noqa: F401
        _safe_print("[OK] app.utils.db.get_db, init_db")
    except Exception as e:
        _safe_print(f"[ERRO] app.utils.db: {e}")
        return False

    try:
        from app.utils.helpers import (  # noqa: F401
            row_to_dict, normalizar_cnpj, parse_bool, slugify, normalize_phone_br
        )
        _safe_print("[OK] app.utils.helpers")
    except Exception as e:
        _safe_print(f"[ERRO] app.utils.helpers: {e}")
        return False

    blueprints = [
        ("auth", "app.routes.auth"),
        ("config", "app.routes.config"),
        ("credores", "app.routes.credores"),
        ("empenhos", "app.routes.empenhos"),
        ("rpas", "app.routes.rpas"),
        ("kanban", "app.routes.kanban"),
        ("documentos", "app.routes.documentos"),
        ("autentique", "app.routes.autentique"),
        ("prazos", "app.routes.prazos"),
        ("protocolo", "app.routes.protocolo"),
        ("extratos", "app.routes.extratos"),
        ("ia", "app.routes.ia"),
        ("cnpj", "app.routes.cnpj"),
        ("pdf", "app.routes.pdf"),
    ]

    for name, module in blueprints:
        try:
            mod = __import__(module, fromlist=["bp"])
            bp = getattr(mod, "bp")
            _safe_print(f"[OK] {name} (bp: {bp.name})")
        except Exception as e:
            _safe_print(f"[ERRO] {name}: {e}")
            return False

    try:
        from app.routes import (  # noqa: F401
            credores_bp, empenhos_bp, rpas_bp, kanban_bp,
            documentos_bp, autentique_bp, prazos_bp, protocolo_bp,
            extratos_bp, ia_bp, cnpj_bp, pdf_bp, auth_bp, config_bp
        )
        _safe_print("[OK] app.routes (todos blueprints)")
    except Exception as e:
        _safe_print(f"[ERRO] app.routes: {e}")
        return False

    return True


def test_helpers():
    """Testa funcoes auxiliares."""
    _safe_print("")
    _safe_print("=" * 60)
    _safe_print("TESTANDO HELPERS")
    _safe_print("=" * 60)

    from app.utils.helpers import (
        normalizar_cnpj, cnpj_valido, parse_bool, slugify, normalize_phone_br
    )

    assert normalizar_cnpj("12.345.678/0001-99") == "12345678000199"
    assert normalizar_cnpj("12345678000199") == "12345678000199"
    assert normalizar_cnpj("") == ""
    _safe_print("[OK] normalizar_cnpj")

    assert cnpj_valido("12.345.678/0001-95") is True
    assert cnpj_valido("12345678000195") is True
    assert cnpj_valido("11.111.111/1111-11") is False
    assert cnpj_valido("12.345.678/0001-99") is False
    _safe_print("[OK] cnpj_valido")

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

    assert slugify("Teste Com Acento") == "teste-com-acento"
    assert slugify("Especial: @#$%") == "especial"
    assert slugify("") == "geral"
    _safe_print("[OK] slugify")

    assert normalize_phone_br("(65) 99999-9999") == "5565999999999"
    assert normalize_phone_br("65999999999") == "5565999999999"
    _safe_print("[OK] normalize_phone_br")

    return True


def test_app_factory():
    """Testa criacao do app."""
    _safe_print("")
    _safe_print("=" * 60)
    _safe_print("TESTANDO APP FACTORY")
    _safe_print("=" * 60)

    from app import create_app

    app = create_app()
    _safe_print(f"[OK] App criado: {app.name}")

    expected_blueprints = [
        "auth", "config", "credores", "empenhos", "rpas",
        "kanban", "documentos", "autentique", "prazos", "protocolo",
        "extratos", "ia", "cnpj", "pdf"
    ]

    registered = list(app.blueprints.keys())
    for bp_name in expected_blueprints:
        if bp_name in registered:
            _safe_print(f"[OK] Blueprint '{bp_name}' registrado")
        else:
            _safe_print(f"[ERRO] Blueprint '{bp_name}' NAO registrado")
            return False

    rules = [str(r) for r in app.url_map.iter_rules()]
    static_routes = ["/", "/static/<path:filename>", "/<path:filename>"]
    for route in static_routes:
        if any(route.replace("<path:filename>", "test") in r for r in rules):
            _safe_print(f"[OK] Rota estatica: {route}")

    return True


def test_db_connection():
    """Testa conexao com banco de dados."""
    _safe_print("")
    _safe_print("=" * 60)
    _safe_print("TESTANDO BANCO DE DADOS")
    _safe_print("=" * 60)

    from app import create_app
    from app.utils.db import get_db, init_db

    app = create_app()

    with app.app_context():
        init_db()
        _safe_print("[OK] init_db() executado")

        conn = get_db()
        cursor = conn.execute("SELECT 1")
        result = cursor.fetchone()
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
            "configuracoes", "logs", "documentos_centro",
            "autentique_envios", "autentique_contatos",
        ]

        table_names = [t["name"] for t in tables]
        for table in expected_tables:
            if table in table_names:
                _safe_print(f"[OK] Tabela '{table}' existe")
            else:
                _safe_print(f"[ERRO] Tabela '{table}' nao encontrada")
                return False

    return True


def run_all_tests():
    """Executa todos os testes."""
    _safe_print("")
    _safe_print("=" * 60)
    _safe_print("TESTES DA ESTRUTURA MODULAR")
    _safe_print("=" * 60)
    _safe_print("")

    tests = [
        ("Imports", test_imports),
        ("Helpers", test_helpers),
        ("App Factory", test_app_factory),
        ("Banco de Dados", test_db_connection),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result, None))
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
    for fn in (test_imports, test_helpers, test_app_factory, test_db_connection):
        suite.addTest(unittest.FunctionTestCase(fn))
    return suite


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
