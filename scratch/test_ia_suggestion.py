import os
import sys
import sqlite3
import json

# Add root folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load dotenv to get API keys
def load_dotenv():
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()

def run_test():
    load_dotenv()
    
    # Initialize Flask app
    from server import create_app
    app, _, init_db, migrate_db = create_app()
    
    # Setup database
    with app.app_context():
        init_db()
        
    print("Conectando ao banco de dados...")
    conn = sqlite3.connect('empenhos.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if there is an OpenRouter API key configured
    key_row = cursor.execute("SELECT valor FROM configuracoes WHERE chave='api_openrouter_key'").fetchone()
    api_key = key_row["valor"] if key_row else os.environ.get("OPENROUTER_API_KEY", "")
    
    if not api_key:
        print("AVISO: Nenhuma chave OpenRouter encontrada no banco de dados ou no .env!")
        # Let's check for fallback keys
        fallback_row = cursor.execute("SELECT valor FROM configuracoes WHERE chave='api_opencode_go_key'").fetchone()
        if fallback_row:
            api_key = fallback_row["valor"]
            print("Usando chave fallback api_opencode_go_key.")
            
    if not api_key:
        print("ERRO: Configure a chave da IA antes de testar.")
        return
        
    # Create documents directory and a mock file
    doc_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "documentos_centro", "biblioteca-leis", "lei-teste-2026")
    os.makedirs(doc_dir, exist_ok=True)
    mock_file_path = os.path.join(doc_dir, "documento_original.txt")
    
    # Write a mock document content that looks like a Municipal Law
    mock_content = """
    ESTADO DO PARANÁ
    PREFEITURA MUNICIPAL DE INAJÁ
    LEI COMPLEMENTAR Nº 987, DE 02 DE JUNHO DE 2026
    Súmula: Dispõe sobre o plano de cargos, carreiras e salários dos servidores da Prefeitura de Inajá e dá outras providências.
    O Prefeito Municipal de Inajá, no uso de suas atribuições legais, faz saber que a Câmara aprovou e ele sanciona a seguinte lei...
    """
    
    with open(mock_file_path, "w", encoding="utf-8") as f:
        f.write(mock_content)
        
    # Register this document in the database documents_centro table
    cursor.execute("DELETE FROM documentos_centro WHERE nome_original='documento_original.txt'")
    cursor.execute(
        "INSERT INTO documentos_centro (nome_original, nome_arquivo, categoria, referencia, descricao, tamanho, extensao, caminho_relativo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "documento_original.txt",
            "documento_original.txt",
            "biblioteca-leis",
            "lei-987-2026",
            "Documento de teste enviado automaticamente",
            len(mock_content),
            ".txt",
            "biblioteca-leis/lei-teste-2026/documento_original.txt"
        )
    )
    conn.commit()
    doc_id = cursor.lastrowid
    print(f"Documento de teste inserido com ID: {doc_id}")
    
    # Run the suggestion route using Flask Test Client
    print("Chamando a rota da IA /api/documentos/<id>/sugerir-nome...")
    client = app.test_client()
    
    # Simulate being logged in as aleksandro (session variables)
    with client.session_transaction() as sess:
        sess["usuario_id"] = 1
        sess["usuario_login"] = "aleksandro"
        sess["usuario_nivel"] = "admin"
        
    res = client.get(f"/api/documentos/{doc_id}/sugerir-nome")
    
    print(f"Resposta HTTP: {res.status_code}")
    print("JSON retornado:")
    data = json.loads(res.data.decode("utf-8"))
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    # Clean up test database record
    cursor.execute("DELETE FROM documentos_centro WHERE id=?", (doc_id,))
    conn.commit()
    
    # Clean up test file
    try:
        os.remove(mock_file_path)
    except Exception:
        pass

if __name__ == '__main__':
    run_test()
