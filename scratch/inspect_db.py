import sqlite3
import os

db_path = "empenhos.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=== CONFIGURACOES ===")
    try:
        rows = cursor.execute("SELECT chave, valor FROM configuracoes").fetchall()
        for r in rows:
            print(f"{r['chave']}: {r['valor']}")
    except Exception as e:
        print(f"Erro ao ler configuracoes: {e}")
        
    conn.close()
else:
    print("Banco de dados empenhos.db nao encontrado na pasta atual.")
