from datetime import datetime
from pathlib import Path
from typing import Any

from renomer.organizador_ia import OrganizadorIA
from renomer.organizador_local_avancado import OrganizadorLocalAvancado


def adaptar_resultado(resultado: dict[str, Any]) -> dict[str, Any]:
    base = {
        'nome': resultado.get('nome_original', ''),
        'sucesso': resultado.get('sucesso', False),
        'data': resultado.get('detalhes', {}).get('data', {}),
        'conta': resultado.get('detalhes', {}).get('conta', {}),
        'banco': resultado.get('detalhes', {}).get('banco'),
        'tipo_conta': resultado.get('detalhes', {}).get('tipo_conta'),
        'confianca': resultado.get('detalhes', {}).get('confianca'),
    }
    if resultado.get('sucesso'):
        base['nome_novo'] = Path(resultado.get('arquivo_destino', '')).name
        base['estrutura'] = resultado.get('estrutura', '')
        base['destino'] = resultado.get('arquivo_destino', '')
        base['acao'] = resultado.get('acao', '')
        if resultado.get('metodo'):
            base['metodo'] = resultado['metodo']
    else:
        base['erro'] = resultado.get('erro', 'Erro desconhecido')
    return base


def validar_origem_destino(origem: str, destino: str) -> str | None:
    origem_path = Path(origem)
    destino_path = Path(destino)
    if not origem or not origem_path.is_dir():
        return 'Pasta de origem inválida ou não encontrada'
    if not destino:
        return 'Pasta de destino obrigatória'
    if origem_path.resolve() == destino_path.resolve():
        return 'Origem e destino não podem ser iguais'
    return None


def coletar_arquivos(origem: str) -> list[Path]:
    origem_path = Path(origem)
    arquivos: list[Path] = []
    for ext in ['*.pdf', '*.PDF', '*.ofx', '*.OFX']:
        arquivos.extend(origem_path.rglob(ext))
    return arquivos


def processar_extratos(origem: str, destino: str, usar_ia: bool, api_key_ia: str, modelo_ia: str, modo_teste: bool) -> dict[str, Any]:
    arquivos = coletar_arquivos(origem)
    if usar_ia and api_key_ia:
        organizador = OrganizadorIA(origem, destino, api_key_ia, modelo_ia)
    else:
        organizador = OrganizadorLocalAvancado(origem, destino)

    resultados = [adaptar_resultado(organizador.processar_arquivo(arquivo, modo_teste=modo_teste)) for arquivo in arquivos]
    sucessos = [resultado for resultado in resultados if resultado['sucesso']]
    erros = [resultado for resultado in resultados if not resultado['sucesso']]

    payload = {
        'total': len(arquivos),
        'sucessos': len(sucessos),
        'erros': len(erros),
        'resultados': resultados,
    }
    if not modo_teste:
        payload['concluido_em'] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    return payload


def listar_subpastas(caminho: str) -> dict[str, Any]:
    path = Path(caminho) if caminho else Path.home()
    if not path.exists():
        path = Path.home()
    itens = [
        {'nome': str(item.name), 'caminho': str(item), 'tipo': 'dir' if item.is_dir() else 'file'}
        for item in sorted(path.iterdir())
        if item.is_dir()
    ]
    return {'caminho_atual': str(path), 'pai': str(path.parent), 'itens': itens}
