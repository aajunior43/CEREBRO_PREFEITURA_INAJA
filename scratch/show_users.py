import os
import sys
import sqlite3

# Add root folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def load_dotenv():
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    k, v = line.split('=', 1)
                    os.environ[k.strip()] = v.strip()

def show():
    load_dotenv()
    
    # Initialize the database using application context to run migrations and seeds
    from server import create_app
    app, _, init_db, migrate_db = create_app()
    with app.app_context():
        init_db()
        
    # Open sqlite connection to empenhos.db
    conn = sqlite3.connect('empenhos.db')
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, nome, login, nivel, ativo, senha_hash FROM usuarios").fetchall()
    
    print("\n==================================================")
    print("   CREDENCIAS E USUÁRIOS REGISTRADOS NO SISTEMA   ")
    print("==================================================")
    for r in rows:
        print(f"Nome:     {r['nome']}")
        print(f"Login:    {r['login']}")
        print(f"Nível:    {r['nivel']}")
        print(f"Status:   {'Ativo' if r['ativo'] else 'Inativo'}")
        print(f"Hash:     {r['senha_hash']}")
        # Compare with known/provised passwords
        import hashlib
        pass_found = "Desconhecida (criptografada)"
        for candidate in ["admin123", "123456", "1234"]:
            if hashlib.sha256(candidate.encode()).hexdigest() == r['senha_hash']:
                pass_found = f"'{candidate}' (Senha padrão)"
                break
        print(f"Senha:    {pass_found}")
        print("--------------------------------------------------")

if __name__ == '__main__':
    show()
