import sqlite3
import os

db_path = "empenhos.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Atualizando configuracoes no empenhos.db...")
    try:
        cursor.execute(
            "UPDATE configuracoes SET valor = ? WHERE chave = ?",
            ("opencode-go/qwen3.6-plus", "api_openrouter_modelo")
        )
        conn.commit()
        print("Model configuration updated successfully.")
        
        # Verify the change
        rows = cursor.execute("SELECT valor FROM configuracoes WHERE chave = 'api_openrouter_modelo'").fetchone()
        print(f"Novo valor de api_openrouter_modelo: {rows[0] if rows else 'não encontrado'}")
        
    except Exception as e:
        print(f"Erro ao atualizar: {e}")
    finally:
        conn.close()
else:
    print("empenhos.db nao encontrado")
