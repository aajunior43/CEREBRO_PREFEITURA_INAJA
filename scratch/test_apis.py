import os
import sys
import unittest

# Add root folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from server import create_app

class TestAPIsAuthentication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure app to use a temporary DB for isolation
        import server
        cls.orig_db = server.DB_PATH
        cls.test_db = os.path.join(os.path.dirname(cls.orig_db), "test_auth_apis.db")
        server.DB_PATH = cls.test_db
        
        cls.app, _, cls.init_db, cls.migrate_db = create_app()
        with cls.app.app_context():
            cls.init_db()
            cls.migrate_db()
            
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        # Clean up temporary test DB
        if os.path.exists(cls.test_db):
            try:
                os.remove(cls.test_db)
            except Exception:
                pass
        import server
        server.DB_PATH = cls.orig_db

    def test_anonymous_access_blocked(self):
        """Verifica se acessos anônimos a rotas protegidas retornam 401."""
        endpoints = [
            ("/api/documentos", "GET"),
            ("/api/empenhos/2026/6", "GET"),
            ("/api/calendario", "GET"),
            ("/api/logs", "GET"),
            ("/api/despesas/importacoes", "GET"),
            ("/api/fornecimento/dados", "GET"),
            ("/api/prazos", "GET"),
            ("/api/cnpj/buscar", "POST"),
            ("/api/audit-trail", "GET"),
            ("/api/latex-pdf/gerar", "POST"),
        ]
        
        for url, method in endpoints:
            if method == "GET":
                res = self.client.get(url)
            else:
                res = self.client.post(url, json={})
            
            # Assegura que o status retornado é 401 devido ao @require_login
            self.assertEqual(
                res.status_code, 401,
                f"Endpoint {method} {url} exposto indevidamente! Código retornado: {res.status_code}"
            )

    def test_authenticated_access_allowed(self):
        """Verifica se acessos com login ativo são autorizados."""
        # Cria sessão ativa no cliente de testes
        with self.client.session_transaction() as sess:
            sess["usuario_id"] = 1
            sess["usuario_nome"] = "Auditor Teste"
            sess["usuario_nivel"] = "admin"

        # Endpoints seguros e estruturados para responder 200 no banco vazio
        endpoints = [
            ("/api/documentos", "GET"),
            ("/api/empenhos/2026/6", "GET"),
            ("/api/calendario", "GET"),
            ("/api/logs", "GET"),
            ("/api/despesas/importacoes", "GET"),
            ("/api/fornecimento/dados", "GET"),
            ("/api/prazos", "GET"),
            ("/api/audit-trail", "GET"),
        ]
        
        for url, method in endpoints:
            res = self.client.get(url)
            # Deve retornar 200 (sucesso) já que estamos autenticados na sessão
            self.assertEqual(
                res.status_code, 200,
                f"Falha de acesso autenticado em {method} {url}! Código retornado: {res.status_code}"
            )

if __name__ == '__main__':
    unittest.main()
