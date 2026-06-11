"""
Migracao: corrige inconsistencias encontradas na tabela de credores.

Problemas corrigidos:
  1. Tres entradas PRODASP com mesmo CNPJ -> renomeadas com sufixo descritivo
  2. validade = '' (string vazia) -> NULL em dois credores
  3. Empenho orfao (credor_id=18, PRISMA excluido) -> removido
  4. Reconstroi indice FTS5 dos credores

Como executar (com o servidor parado):
    python scripts/fix_credores_issues.py

Ou passando o caminho do banco:
    python scripts/fix_credores_issues.py empenhos.db
"""

import sqlite3
import sys
import os
from datetime import datetime

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "..", "empenhos.db"
)


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    print("[%s] %s" % (now(), msg))


def main():
    if not os.path.exists(DB_PATH):
        print("Banco nao encontrado: %s" % DB_PATH)
        sys.exit(1)

    log("Abrindo banco: %s" % DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    try:
        # ----------------------------------------------------------
        # Passo 1: remover triggers do FTS para permitir UPDATE
        # ----------------------------------------------------------
        conn.execute("DROP TRIGGER IF EXISTS credores_fts_ai")
        conn.execute("DROP TRIGGER IF EXISTS credores_fts_ad")
        conn.execute("DROP TRIGGER IF EXISTS credores_fts_au")
        conn.commit()
        log("Triggers FTS removidos temporariamente.")

        # ----------------------------------------------------------
        # Passo 2: renomear os 3 PRODASP com nomes distintos
        # ----------------------------------------------------------
        renames = [
            (12, "PRODASP – CÂMARA MUNICIPAL"),
            (20, "PRODASP – PREFEITURA MUNICIPAL"),
            (28, "PRODASP – CÂMARA MUNICIPAL 2"),
        ]

        for cid, novo_nome in renames:
            row = conn.execute(
                "SELECT nome, departamento, cnpj FROM credores WHERE id=?", (cid,)
            ).fetchone()
            if not row:
                log("  AVISO: credor id=%s nao encontrado, pulando." % cid)
                continue

            nome_anterior = row["nome"]
            conn.execute(
                "UPDATE credores SET nome=?, atualizado_em=? WHERE id=?",
                (novo_nome, now(), cid),
            )
            detalhe = "Migracao: renomeado de '%s' para '%s' (separacao PRODASP mesmo CNPJ)" % (
                nome_anterior, novo_nome
            )
            conn.execute(
                "INSERT INTO logs (acao,credor_id,credor_nome,credor_departamento,credor_cnpj,detalhes) "
                "VALUES (?,?,?,?,?,?)",
                ("EDITAR", cid, novo_nome, row["departamento"] or "", row["cnpj"] or "", detalhe),
            )
            log("  Credor %s: '%s' -> '%s'" % (cid, nome_anterior, novo_nome))

        # ----------------------------------------------------------
        # Passo 3a: corrigir validade = '' -> NULL
        # ----------------------------------------------------------
        affected = conn.execute(
            "SELECT id, nome FROM credores WHERE validade = ''"
        ).fetchall()

        for r in affected:
            conn.execute(
                "UPDATE credores SET validade=NULL, atualizado_em=? WHERE id=?",
                (now(), r["id"]),
            )
            log("  Credor %s (%s): validade '' -> NULL" % (r["id"], r["nome"]))

        if not affected:
            log("  Nenhum credor com validade vazia encontrado.")

        # ----------------------------------------------------------
        # Passo 3b: remover empenhos orfaos (credor excluido)
        # ----------------------------------------------------------
        orphans = conn.execute(
            "SELECT e.id, e.credor_id, e.ano, e.mes "
            "FROM empenhos e "
            "LEFT JOIN credores c ON c.id = e.credor_id "
            "WHERE c.id IS NULL OR c.ativo = 0"
        ).fetchall()

        if orphans:
            for o in orphans:
                eid = o["id"]
                ecid = o["credor_id"]
                eano = o["ano"]
                emes = o["mes"]
                conn.execute("DELETE FROM empenhos WHERE id=?", (eid,))
                log("  Empenho orfao removido: id=%s, credor_id=%s, %s/%s" % (eid, ecid, emes, eano))
        else:
            log("  Nenhum empenho orfao encontrado.")

        conn.commit()
        log("Alteracoes de dados salvas.")

        # ----------------------------------------------------------
        # Passo 4: recriar FTS do zero e reinstalar triggers
        # ----------------------------------------------------------
        conn.execute("DROP TABLE IF EXISTS credores_fts")
        conn.execute(
            "CREATE VIRTUAL TABLE credores_fts USING fts5("
            "nome, descricao, cnpj, email, content=credores, content_rowid=id)"
        )
        conn.execute("INSERT INTO credores_fts(credores_fts) VALUES('rebuild')")
        conn.commit()
        log("FTS reconstruido.")

        conn.executescript(
            "CREATE TRIGGER credores_fts_ai AFTER INSERT ON credores BEGIN "
            "INSERT INTO credores_fts(rowid,nome,descricao,cnpj,email) "
            "VALUES(new.id,new.nome,new.descricao,new.cnpj,new.email); END;\n"
            "CREATE TRIGGER credores_fts_ad AFTER DELETE ON credores BEGIN "
            "INSERT INTO credores_fts(credores_fts,rowid,nome,descricao,cnpj,email) "
            "VALUES('delete',old.id,old.nome,old.descricao,old.cnpj,old.email); END;\n"
            "CREATE TRIGGER credores_fts_au AFTER UPDATE ON credores BEGIN "
            "INSERT INTO credores_fts(credores_fts,rowid,nome,descricao,cnpj,email) "
            "VALUES('delete',old.id,old.nome,old.descricao,old.cnpj,old.email); "
            "INSERT INTO credores_fts(rowid,nome,descricao,cnpj,email) "
            "VALUES(new.id,new.nome,new.descricao,new.cnpj,new.email); END;"
        )
        conn.commit()
        log("Triggers FTS reinstalados.")
        log("Migracao concluida com sucesso.")

    except Exception as e:
        conn.rollback()
        log("ERRO - rollback aplicado: %s" % e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
