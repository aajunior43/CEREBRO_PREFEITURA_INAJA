import sqlite3

conn = sqlite3.connect('empenhos.db')
conn.row_factory = sqlite3.Row

# IDs dos credores reais para reativar (excluindo PRODASP id=76 que pode ser duplicata)
# EMPASOFT=1, MUNICIPIO PARANAVAI=14, PRISMA=18, LUCIO FERNANDES ENARES=25, PRODASP=76
ids_para_reativar = [1, 14, 18, 25, 76]

print('=== REATIVANDO CREDORES ===')
for cid in ids_para_reativar:
    row = conn.execute('SELECT id, nome, tipo_valor, departamento FROM credores WHERE id=?', (cid,)).fetchone()
    if row:
        conn.execute('UPDATE credores SET ativo=1 WHERE id=?', (cid,))
        conn.execute(
            "INSERT INTO logs (acao, credor_id, credor_nome, detalhes) VALUES (?,?,?,?)",
            ('REATIVAR', cid, row['nome'], 'Credor reativado manualmente - estava ativo=0 sem motivo')
        )
        print(f'  OK Reativado: [{cid}] {row["nome"]} | {row["departamento"]}')

conn.commit()

# Confirmar resultado
total_ativos = conn.execute('SELECT COUNT(*) FROM credores WHERE ativo=1').fetchone()[0]
print(f'\nTotal de credores ativos agora: {total_ativos}')

# Avisar sobre PRODASP duplicado
prodasps = conn.execute("SELECT id, nome, departamento FROM credores WHERE nome LIKE '%PRODASP%' AND ativo=1").fetchall()
print('\n=== PRODASPs ativos (verificar duplicatas) ===')
for r in prodasps:
    print(f'  [{r["id"]}] {r["nome"]} | {r["departamento"]}')

conn.close()
print('\nPronto! Refresque a página do sistema para ver os credores.')
