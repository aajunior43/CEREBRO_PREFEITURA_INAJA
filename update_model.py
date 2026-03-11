import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'empenhos.db')
conn = sqlite3.connect(db_path)
conn.execute("UPDATE configuracoes SET valor='openrouter/free' WHERE chave='api_openrouter_modelo'")
conn.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('api_openrouter_modelo', 'openrouter/free')")
conn.commit()
# Verify
row = conn.execute("SELECT valor FROM configuracoes WHERE chave='api_openrouter_modelo'").fetchone()
conn.close()
print(f"Modelo no banco: {row[0] if row else 'N/A'}")
