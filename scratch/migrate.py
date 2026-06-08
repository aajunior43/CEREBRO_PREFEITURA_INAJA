import sqlite3

def run_migration():
    conn = sqlite3.connect('empenhos.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if table usuarios_old exists (from failed run)
    old_exists = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios_old'").fetchone()
    
    if old_exists:
        print("Restaurando de usuarios_old...")
        # Drop usuarios if it exists
        cursor.execute("DROP TABLE IF EXISTS usuarios")
        
        # Create usuarios with updated CHECK constraint
        cursor.execute("""
            CREATE TABLE usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT DEFAULT '',
                login TEXT NOT NULL UNIQUE,
                senha_hash TEXT NOT NULL,
                nivel TEXT NOT NULL DEFAULT 'padrao' CHECK (nivel IN ('adm','padrao')),
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT DEFAULT (datetime('now','localtime')),
                atualizado_em TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        
        # Copy records from old mapping admin->adm, other->padrao
        cursor.execute("""
            INSERT INTO usuarios (id, nome, email, login, senha_hash, nivel, ativo, criado_em, atualizado_em)
            SELECT id, nome, email, login, senha_hash,
                   CASE WHEN nivel IN ('admin', 'adm') THEN 'adm' ELSE 'padrao' END,
                   ativo, criado_em, atualizado_em
            FROM usuarios_old
        """)
        
        # Drop old backup table
        cursor.execute("DROP TABLE usuarios_old")
        conn.commit()
        print("Migração concluída!")

    # Check if we need to seed Maicon/Luana if they are missing
    for user_login, name in [("maicon", "Maicon"), ("luana", "Luana")]:
        exists = cursor.execute("SELECT id FROM usuarios WHERE login=?", (user_login,)).fetchone()
        if not exists:
            # We seed them with temporary password '123456' hashed:
            import hashlib
            h = hashlib.sha256('123456'.encode()).hexdigest()
            cursor.execute(
                "INSERT INTO usuarios (nome, email, login, senha_hash, nivel, ativo) VALUES (?, ?, ?, ?, ?, 1)",
                (name, f"{user_login}@inaja.pr.gov.br", user_login, h, "padrao")
            )
            conn.commit()
            print(f"Usuário {name} cadastrado.")
            
    # List actual credentials/logins
    print("\nUsuários no Banco:")
    rows = conn.execute("SELECT id, nome, login, nivel, ativo, senha_hash FROM usuarios").fetchall()
    for row in rows:
        print(f"ID: {row['id']} | Nome: {row['nome']} | Login: {row['login']} | Nível: {row['nivel']} | Ativo: {row['ativo']}")

if __name__ == '__main__':
    run_migration()
