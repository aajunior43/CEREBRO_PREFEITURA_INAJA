def listar_empenhos_mes(conn, ano, mes, row_to_dict):
    rows = conn.execute(
        "SELECT credor_id, ano, mes, empenhado, timestamp FROM empenhos WHERE ano=? AND mes=? AND empenhado=1",
        (ano, mes)
    ).fetchall()
    return [row_to_dict(r) for r in rows]


def persistir_empenho(conn, credor_id, ano, mes, now_str):
    credor = conn.execute("SELECT id, nome FROM credores WHERE id=?", (credor_id,)).fetchone()
    if not credor:
        raise ValueError('Credor não encontrado')

    existing = conn.execute(
        "SELECT id, empenhado FROM empenhos WHERE credor_id=? AND ano=? AND mes=?",
        (credor_id, ano, mes)
    ).fetchone()

    if existing:
        novo_estado = 0 if int(existing['empenhado'] or 0) == 1 else 1
        conn.execute(
            "UPDATE empenhos SET empenhado=?, timestamp=? WHERE id=?",
            (novo_estado, now_str, existing['id'])
        )
    else:
        novo_estado = 1
        conn.execute(
            "INSERT INTO empenhos (credor_id, ano, mes, empenhado, timestamp) VALUES (?,?,?,?,?)",
            (credor_id, ano, mes, novo_estado, now_str)
        )

    conn.execute(
        "INSERT INTO logs (acao, credor_id, credor_nome, detalhes) VALUES (?,?,?,?)",
        ('EMPENHAR' if novo_estado else 'DESEMPENHAR', credor_id, credor['nome'], f'{int(mes):02d}/{ano}')
    )
    return {'credor_id': credor_id, 'empenhado': bool(novo_estado)}


def listar_historico_credor(conn, cid, meses, now_struct):
    refs = []
    ano = now_struct.tm_year
    mes = now_struct.tm_mon
    for _ in range(meses):
        refs.append((ano, mes))
        mes -= 1
        if mes == 0:
            mes = 12
            ano -= 1

    rows = conn.execute(
        "SELECT ano, mes, empenhado FROM empenhos WHERE credor_id=?",
        (cid,)
    ).fetchall()
    marcado = {(r['ano'], r['mes']): bool(r['empenhado']) for r in rows}
    nomes_meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    resultado = []
    for ano_ref, mes_ref in refs:
        resultado.append({
            'ano': ano_ref,
            'mes': mes_ref,
            'mes_nome': nomes_meses[mes_ref - 1],
            'empenhado': marcado.get((ano_ref, mes_ref), False),
        })
    return resultado
