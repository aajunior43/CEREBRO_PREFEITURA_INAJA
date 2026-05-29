"""Blueprint: CNPJ Consultation"""

import json
import re
import urllib.request as _urllib_req
import urllib.error as _urllib_err
from flask import Blueprint, request, jsonify

bp = Blueprint("cnpj", __name__)


def _cnpj_so_numeros(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj)


def _cnpj_valido(cnpj: str) -> bool:
    digits = _cnpj_so_numeros(cnpj)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    nums = [int(ch) for ch in digits]
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma1 = sum(nums[i] * pesos1[i] for i in range(12))
    resto1 = soma1 % 11
    dv1 = 0 if resto1 < 2 else 11 - resto1
    if nums[12] != dv1:
        return False
    pesos2 = [6] + pesos1
    soma2 = sum(nums[i] * pesos2[i] for i in range(12)) + dv1 * pesos2[12]
    resto2 = soma2 % 11
    dv2 = 0 if resto2 < 2 else 11 - resto2
    return nums[13] == dv2


def _fmt_moeda(v):
    try:
        return (
            f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
    except Exception:
        return str(v) if v else ""


def _buscar_cnpja(cnpj: str, api_key: str = "") -> dict:
    url = f"https://open.cnpja.com/office/{cnpj}"
    headers = {"User-Agent": "Mozilla/5.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = _urllib_req.Request(url, headers=headers)
    with _urllib_req.urlopen(req, timeout=3) as r:
        d = json.loads(r.read().decode())
    end = d.get("address", {})
    telefones = [
        f"({p.get('area', '')}) {p.get('number', '')} [{p.get('type', '')}]"
        for p in d.get("phones", [])
        if p.get("number")
    ]
    emails = [
        f"{e.get('address', '')} [{e.get('ownership', '')}]"
        for e in d.get("emails", [])
        if e.get("address")
    ]
    socios = [
        {
            "nome": m.get("person", {}).get("name", ""),
            "qualificacao": m.get("role", {}).get("text", ""),
        }
        for m in d.get("company", {}).get("members", [])
    ]
    cnaes_sec = [a.get("text", "") for a in d.get("sideActivities", [])]
    complemento = end.get("details", "")
    end_str = f"{end.get('street', '')} {end.get('number', '')}".strip()
    if complemento:
        end_str += f", {complemento}"
    end_str += f" - {end.get('district', '')} - {end.get('city', '')}/{end.get('state', '')} - CEP {end.get('zip', '')}"
    return {
        "cnpj": cnpj,
        "razao_social": d.get("company", {}).get("name", ""),
        "nome_fantasia": d.get("alias", ""),
        "situacao": d.get("status", {}).get("text", ""),
        "situacao_id": d.get("status", {}).get("id", ""),
        "data_situacao": d.get("statusDate", ""),
        "data_abertura": d.get("founded", ""),
        "natureza_juridica": d.get("company", {}).get("nature", {}).get("text", ""),
        "capital_social": _fmt_moeda(d.get("company", {}).get("equity")),
        "porte": d.get("company", {}).get("size", {}).get("text", ""),
        "simples": "Sim"
        if d.get("company", {}).get("simples", {}).get("optant")
        else "Não",
        "mei": "Sim" if d.get("company", {}).get("simei", {}).get("optant") else "Não",
        "matriz": "Sim" if d.get("head") else "Filial",
        "endereco": end_str,
        "cnae_principal": d.get("mainActivity", {}).get("text", ""),
        "cnaes_secundarios": cnaes_sec,
        "socios": socios,
        "telefones": telefones,
        "emails": emails,
        "fonte": "CNPJá",
    }


def _buscar_receitaws(cnpj: str) -> dict:
    url = f"https://www.receitaws.com.br/v1/cnpj/{cnpj}"
    req = _urllib_req.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with _urllib_req.urlopen(req, timeout=5) as r:
        d = json.loads(r.read().decode())
    if d.get("status") == "ERROR":
        raise Exception(d.get("message", "CNPJ não encontrado"))
    socios = [
        {"nome": s.get("nome", ""), "qualificacao": s.get("qual", "")}
        for s in d.get("qsa", [])
    ]
    return {
        "cnpj": cnpj,
        "razao_social": d.get("nome", ""),
        "nome_fantasia": d.get("fantasia", ""),
        "situacao": d.get("situacao", ""),
        "situacao_id": (d.get("situacao") or "").upper(),
        "data_abertura": d.get("abertura", ""),
        "natureza_juridica": d.get("natureza_juridica", ""),
        "capital_social": d.get("capital_social", ""),
        "porte": d.get("porte", ""),
        "simples": d.get("simples", ""),
        "mei": d.get("mei", ""),
        "endereco": f"{d.get('logradouro', '')} {d.get('numero', '')}".strip(),
        "cnae_principal": d.get("atividade_principal", [{}])[0].get("text", "")
        if d.get("atividade_principal")
        else "",
        "cnaes_secundarios": [
            a.get("text", "") for a in d.get("atividades_secundarias", [])
        ],
        "socios": socios,
        "telefones": [d.get("telefone", "")] if d.get("telefone") else [],
        "emails": [d.get("email", "")] if d.get("email") else [],
        "fonte": "ReceitaWS",
    }


def _buscar_brasilapi(cnpj: str) -> dict:
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
    req = _urllib_req.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with _urllib_req.urlopen(req, timeout=3) as r:
        d = json.loads(r.read().decode())
    
    end_str = f"{d.get('logradouro', '')} {d.get('numero', '')}".strip()
    comp = d.get('complemento')
    if comp:
        end_str += f", {comp}"
    end_str += f" - {d.get('bairro', '')} - {d.get('municipio', '')}/{d.get('uf', '')} - CEP {d.get('cep', '')}"
    
    socios = [
        {
            "nome": s.get("nome_socio", ""),
            "qualificacao": str(s.get("codigo_qualificacao_socio", ""))
        }
        for s in d.get("qsa", [])
    ]
    
    cnaes_sec = [a.get("descricao", "") for a in d.get("cnaes_secundarios", []) if a.get("descricao")]
    
    tel1 = d.get("ddd_telefone_1") or ""
    tels = [tel1] if tel1 else []
    
    email = d.get("email") or ""
    emails = [email] if email else []
    
    return {
        "cnpj": cnpj,
        "razao_social": d.get("razao_social", ""),
        "nome_fantasia": d.get("nome_fantasia", "") or d.get("razao_social", ""),
        "situacao": d.get("descricao_situacao_cadastral", ""),
        "situacao_id": str(d.get("situacao_cadastral", "")),
        "data_situacao": d.get("data_situacao_cadastral", ""),
        "data_abertura": d.get("data_inicio_atividade", ""),
        "natureza_juridica": str(d.get("codigo_natureza_juridica", "")),
        "capital_social": _fmt_moeda(d.get("capital_social")),
        "porte": d.get("descricao_porte", ""),
        "simples": "Sim" if d.get("opcao_pelo_simples") else "Não",
        "mei": "Sim" if d.get("opcao_pelo_mei") else "Não",
        "matriz": "Sim" if d.get("identificador_matriz_filial") == 1 else "Filial",
        "endereco": end_str,
        "cnae_principal": d.get("cnae_fiscal_principal_descricao", ""),
        "cnaes_secundarios": cnaes_sec,
        "socios": socios,
        "telefones": tels,
        "emails": emails,
        "fonte": "BrasilAPI",
    }


@bp.route("/api/cnpj/buscar", methods=["POST"])
def cnpj_buscar():
    d = request.get_json() or {}
    cnpj = _cnpj_so_numeros(d.get("cnpj", ""))
    api_key = d.get("api_key_cnpja", "").strip()
    if len(cnpj) != 14:
        return jsonify({"error": "CNPJ deve ter 14 dígitos"}), 400
    if not _cnpj_valido(cnpj):
        return jsonify({"error": "CNPJ inválido"}), 400
    
    # 1. Se possuir chave para o CNPJá, tenta primeiro por ele
    if api_key:
        try:
            return jsonify(_buscar_cnpja(cnpj, api_key))
        except _urllib_err.HTTPError as e:
            if e.code == 429:
                return jsonify(
                    {"error": "Limite de consultas no CNPJá atingido (5/min). Aguarde 1 minuto."}
                ), 429
        except Exception:
            pass
            
    # 2. Tenta BrasilAPI (excelente serviço público, gratuito, rápido e sem chaves)
    try:
        return jsonify(_buscar_brasilapi(cnpj))
    except Exception:
        pass
        
    # 3. Tenta ReceitaWS como último recurso
    try:
        return jsonify(_buscar_receitaws(cnpj))
    except Exception as e2:
        return jsonify({"error": f"CNPJ não encontrado nos serviços de consulta: {e2}"}), 404
