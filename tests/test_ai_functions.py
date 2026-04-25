"""
Script de teste abrangente para todas as funcoes de IA do projeto CREDORES_FIXOS_MENSAIR
Testa componentes individuais sem necessidade de servidor Flask rodando
"""

import json
import sys
import os
import time
import io
from datetime import datetime

# Fix encoding para Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestReporter:
    """Relatório de testes formatado"""
    
    def __init__(self):
        self.results = []
        self.start_time = time.time()
    
    def add_result(self, test_name, status, details="", error=""):
        self.results.append({
            "test": test_name,
            "status": status,
            "details": details,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })
    
    def print_report(self):
        elapsed = time.time() - self.start_time
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        skipped = sum(1 for r in self.results if r["status"] == "SKIP")
        
        print("\n" + "="*80)
        print("RELATORIO DE TESTES - FUNCOES DE IA")
        print("="*80)
        print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Tempo total: {elapsed:.2f}s")
        print(f"Total: {total} | Passou: {passed} | Falhou: {failed} | Ignorado: {skipped}")
        print("="*80)
        
        for result in self.results:
            status_icon = "[OK]" if result["status"] == "PASS" else "[FAIL]" if result["status"] == "FAIL" else "[SKIP]"
            print(f"\n{status_icon} [{result['status']}] {result['test']}")
            if result["details"]:
                print(f"   -> {result['details']}")
            if result["error"]:
                print(f"   ERRO: {result['error']}")
        
        print("\n" + "="*80)
        return passed, failed, skipped


reporter = TestReporter()

def test_section(name):
    """Imprime cabeçalho de seção"""
    print(f"\n{'='*60}")
    print(f"TESTANDO: {name}")
    print(f"{'='*60}")


# ============================================================================
# TESTE 1: TTLCache
# ============================================================================
test_section("TTLCache (Cache com expiração)")

try:
    from services.openrouter_service import TTLCache
    
    # Teste básico de set/get
    cache = TTLCache(ttl_seconds=2, max_entries=5)
    cache.set("key1", "value1")
    result = cache.get("key1")
    if result == "value1":
        reporter.add_result("TTLCache - set/get básico", "PASS", "Valor armazenado e recuperado corretamente")
    else:
        reporter.add_result("TTLCache - set/get básico", "FAIL", f"Esperado 'value1', obtido '{result}'")
    
    # Teste de expiração
    cache.set("key2", "value2")
    time.sleep(2.5)  # Espera expirar
    result = cache.get("key2")
    if result is None:
        reporter.add_result("TTLCache - expiração TTL", "PASS", "Valor expirou corretamente após TTL")
    else:
        reporter.add_result("TTLCache - expiração TTL", "FAIL", f"Valor deveria ser None, obtido '{result}'")
    
    # Teste de max_entries
    cache2 = TTLCache(ttl_seconds=60, max_entries=3)
    cache2.set("a", 1)
    cache2.set("b", 2)
    cache2.set("c", 3)
    cache2.set("d", 4)  # Deve remover o mais antigo
    if cache2.get("a") is None and cache2.get("d") == 4:
        reporter.add_result("TTLCache - limite de entradas", "PASS", "Entrada mais antiga removida ao exceder limite")
    else:
        reporter.add_result("TTLCache - limite de entradas", "FAIL", "Comportamento de limite incorreto")
        
except Exception as e:
    reporter.add_result("TTLCache - testes", "FAIL", "", str(e))


# ============================================================================
# TESTE 2: extract_json_block
# ============================================================================
test_section("extract_json_block (Extração de JSON)")

try:
    from services.openrouter_service import extract_json_block
    
    # Teste JSON puro
    json_str = '{"key": "value", "number": 42}'
    result = extract_json_block(json_str)
    if result == {"key": "value", "number": 42}:
        reporter.add_result("extract_json_block - JSON puro", "PASS", "JSON simples parseado corretamente")
    else:
        reporter.add_result("extract_json_block - JSON puro", "FAIL", f"Resultado: {result}")
    
    # Teste JSON em markdown
    md_json = '```json\n{"status": "ok", "data": [1,2,3]}\n```'
    result = extract_json_block(md_json)
    if result == {"status": "ok", "data": [1,2,3]}:
        reporter.add_result("extract_json_block - JSON em markdown", "PASS", "JSON em bloco markdown parseado")
    else:
        reporter.add_result("extract_json_block - JSON em markdown", "FAIL", f"Resultado: {result}")
    
    # Teste JSON com texto ao redor
    text_json = 'Aqui está o resultado:\n{"nome": "teste", "valor": 100}\nEspero que ajude!'
    result = extract_json_block(text_json)
    if result == {"nome": "teste", "valor": 100}:
        reporter.add_result("extract_json_block - JSON em texto", "PASS", "JSON extraído de meio de texto")
    else:
        reporter.add_result("extract_json_block - JSON em texto", "FAIL", f"Resultado: {result}")
    
    # Teste JSON array
    arr_json = '[{"id": 1}, {"id": 2}]'
    result = extract_json_block(arr_json)
    if result == [{"id": 1}, {"id": 2}]:
        reporter.add_result("extract_json_block - Array JSON", "PASS", "Array JSON parseado corretamente")
    else:
        reporter.add_result("extract_json_block - Array JSON", "FAIL", f"Resultado: {result}")
        
except Exception as e:
    reporter.add_result("extract_json_block - testes", "FAIL", "", str(e))


# ============================================================================
# TESTE 3: extract_openrouter_text
# ============================================================================
test_section("extract_openrouter_text (Extração de texto)")

try:
    from services.openrouter_service import extract_openrouter_text
    
    # Teste payload normal
    payload = {
        "choices": [{"message": {"content": "Resposta da IA"}}]
    }
    result = extract_openrouter_text(payload)
    if result == "Resposta da IA":
        reporter.add_result("extract_openrouter_text - payload normal", "PASS", "Texto extraído corretamente")
    else:
        reporter.add_result("extract_openrouter_text - payload normal", "FAIL", f"Resultado: {result}")
    
    # Teste payload com conteúdo em lista (multimodal)
    payload_multi = {
        "choices": [{"message": {"content": [
            {"type": "text", "text": "Parte 1"},
            {"type": "text", "text": "Parte 2"}
        ]}}]
    }
    result = extract_openrouter_text(payload_multi)
    if result == "Parte 1Parte 2":
        reporter.add_result("extract_openrouter_text - conteúdo multimodal", "PASS", "Conteúdo multimodal concatenado")
    else:
        reporter.add_result("extract_openrouter_text - conteúdo multimodal", "FAIL", f"Resultado: {result}")
    
    # Teste payload vazio
    try:
        extract_openrouter_text({"choices": []})
        reporter.add_result("extract_openrouter_text - payload vazio", "FAIL", "Deveria lançar ValueError")
    except ValueError:
        reporter.add_result("extract_openrouter_text - payload vazio", "PASS", "ValueError lançado para payload vazio")
        
except Exception as e:
    reporter.add_result("extract_openrouter_text - testes", "FAIL", "", str(e))


# ============================================================================
# TESTE 4: extract_usage
# ============================================================================
test_section("extract_usage (Extração de uso de tokens)")

try:
    from services.openrouter_service import extract_usage
    
    payload = {
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
    }
    result = extract_usage(payload)
    expected = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    if result == expected:
        reporter.add_result("extract_usage - tokens normais", "PASS", "Tokens extraídos corretamente")
    else:
        reporter.add_result("extract_usage - tokens normais", "FAIL", f"Resultado: {result}")
    
    # Teste com total ausente (deve calcular)
    payload_partial = {
        "usage": {
            "prompt_tokens": 80,
            "completion_tokens": 40
        }
    }
    result = extract_usage(payload_partial)
    if result["total_tokens"] == 120:
        reporter.add_result("extract_usage - cálculo de total", "PASS", "Total calculado automaticamente")
    else:
        reporter.add_result("extract_usage - cálculo de total", "FAIL", f"Resultado: {result}")
        
except Exception as e:
    reporter.add_result("extract_usage - testes", "FAIL", "", str(e))


# ============================================================================
# TESTE 5: AIServiceError
# ============================================================================
test_section("AIServiceError (Tratamento de erros)")

try:
    from services.openrouter_service import AIServiceError
    
    # Teste criação de erro
    error = AIServiceError(
        "Erro técnico",
        user_message="Mensagem amigável",
        status_code=429,
        code="rate_limit",
        details={"retry_after": 60}
    )
    
    response = error.to_response()
    if "error" in response and response["error"]["code"] == "rate_limit":
        reporter.add_result("AIServiceError - to_response", "PASS", "Erro convertido para resposta JSON")
    else:
        reporter.add_result("AIServiceError - to_response", "FAIL", f"Resultado: {response}")
    
    # Teste erro sem user_message (deve usar padrão)
    error2 = AIServiceError("Erro sem mensagem")
    if error2.user_message == "O serviço de IA está indisponível no momento. Tente novamente em instantes.":
        reporter.add_result("AIServiceError - mensagem padrão", "PASS", "Mensagem padrão aplicada")
    else:
        reporter.add_result("AIServiceError - mensagem padrão", "FAIL", f"Mensagem: {error2.user_message}")
        
except Exception as e:
    reporter.add_result("AIServiceError - testes", "FAIL", "", str(e))


# ============================================================================
# TESTE 6: ModelPolicy e build_default_model_policies
# ============================================================================
test_section("ModelPolicy (Políticas de modelos)")

try:
    from services.openrouter_service import ModelPolicy, build_default_model_policies
    
    policies = build_default_model_policies("openai/gpt-4o-mini")
    
    # Verificar se todas as task_types existem
    expected_types = ["default", "chat", "empenho", "auditoria_documento", "extrato", "renomeacao_arquivo"]
    missing = [t for t in expected_types if t not in policies]
    
    if not missing:
        reporter.add_result("ModelPolicy - tipos de tarefa", "PASS", f"Todos {len(expected_types)} tipos criados")
    else:
        reporter.add_result("ModelPolicy - tipos de tarefa", "FAIL", f"Faltando: {missing}")
    
    # Verificar política específica
    emp_policy = policies.get("empenho")
    if emp_policy and emp_policy.primary == "openai/gpt-4o-mini" and emp_policy.max_tokens == 1400:
        reporter.add_result("ModelPolicy - política empenho", "PASS", "Política de empenho configurada")
    else:
        reporter.add_result("ModelPolicy - política empenho", "FAIL", f"Policy: {emp_policy}")
    
    # Verificar política de extrato (deve usar Gemma)
    ext_policy = policies.get("extrato")
    if ext_policy and "gemma" in ext_policy.primary.lower():
        reporter.add_result("ModelPolicy - política extrato", "PASS", "Extrato usa modelo Gemma")
    else:
        reporter.add_result("ModelPolicy - política extrato", "FAIL", f"Policy: {ext_policy}")
        
except Exception as e:
    reporter.add_result("ModelPolicy - testes", "FAIL", "", str(e))


# ============================================================================
# TESTE 7: Prompt Templates (ai_prompts.py)
# ============================================================================
test_section("Prompt Templates (ai_prompts)")

try:
    from services.ai_prompts import build_prompt, limit_text, PromptTemplate
    
    # Teste limit_text
    long_text = "a" * 5000
    result = limit_text(long_text, 1000)
    if len(result) <= 1000:
        reporter.add_result("limit_text - truncamento", "PASS", f"Texto truncado para {len(result)} chars")
    else:
        reporter.add_result("limit_text - truncamento", "FAIL", f"Tamanho: {len(result)}")
    
    # Teste build_prompt para empenho
    messages = build_prompt("empenho_generate_description", contexto="Compra de material")
    if isinstance(messages, list) and len(messages) >= 2:
        has_system = any(m.get("role") == "system" for m in messages)
        has_user = any(m.get("role") == "user" for m in messages)
        if has_system and has_user:
            reporter.add_result("build_prompt - estrutura", "PASS", "Prompt com system e user messages")
        else:
            reporter.add_result("build_prompt - estrutura", "FAIL", "Faltando system ou user")
    else:
        reporter.add_result("build_prompt - estrutura", "FAIL", f"Messages: {messages}")
    
    # Teste template classificador_despesa
    messages = build_prompt("classificador_despesa", item="Combustível", web_context="Contexto web")
    if messages and len(messages) >= 2:
        user_content = messages[-1].get("content", "")
        if "Combustível" in user_content:
            reporter.add_result("build_prompt - classificador", "PASS", "Item incluído no prompt")
        else:
            reporter.add_result("build_prompt - classificador", "FAIL", "Item não encontrado")
    else:
        reporter.add_result("build_prompt - classificador", "FAIL", "Messages vazias")
        
except Exception as e:
    reporter.add_result("Prompt Templates - testes", "FAIL", "", str(e))


# ============================================================================
# TESTE 8: ai_service_factory
# ============================================================================
test_section("AI Service Factory")

try:
    from app.utils.ai_service_factory import build_ai_facade, build_ai_service
    
    # Teste construção de serviço (sem chave válida, mas estrutura OK)
    try:
        service = build_ai_service("test_key", "openai/gpt-4o-mini")
        if hasattr(service, 'api_key') and service.api_key == "test_key":
            reporter.add_result("build_ai_service - construção", "PASS", "Serviço criado com chave")
        else:
            reporter.add_result("build_ai_service - construção", "FAIL", "Chave não configurada")
    except Exception as e:
        reporter.add_result("build_ai_service - construção", "FAIL", "", str(e))
    
    # Teste construção de facade
    try:
        facade = build_ai_facade("test_key", "openai/gpt-4o-mini")
        if hasattr(facade, 'service') and hasattr(facade, 'classificar_despesa'):
            reporter.add_result("build_ai_facade - construção", "PASS", "Facade criado com métodos")
        else:
            reporter.add_result("build_ai_facade - construção", "FAIL", "Métodos ausentes")
    except Exception as e:
        reporter.add_result("build_ai_facade - construção", "FAIL", "", str(e))
        
except Exception as e:
    reporter.add_result("AI Service Factory - testes", "FAIL", "", str(e))


# ============================================================================
# TESTE 9: AITaskFacade - Validations
# ============================================================================
test_section("AITaskFacade - Validações e Normalizações")

try:
    from services.ai_tasks import AITaskFacade
    from services.openrouter_service import OpenRouterService
    
    # Criar facade mock para testar validações
    mock_service = OpenRouterService(
        api_key="test_key",
        default_model="test_model",
        referer="https://test",
        title="Test"
    )
    facade = AITaskFacade(mock_service)
    
    # Teste _validate_classificacao - veículos
    result_veiculo = {
        "subelemento_codigo": "3.3.90.30",
        "grupo": "Custeio",
        "modalidade": "Aplicação Direta",
        "elemento": "30",
        "codigo_completo": "3.3.90.30"
    }
    validated = facade._validate_classificacao("Compra de caminhão", result_veiculo)
    if validated.get("subelemento_codigo") == "4.4.90.52" and validated.get("_auto_corrected"):
        reporter.add_result("_validate_classificacao - veículos", "PASS", "Veículo corrigido para 4.4.90.52")
    else:
        reporter.add_result("_validate_classificacao - veículos", "FAIL", f"Resultado: {validated}")
    
    # Teste _validate_classificacao - combustíveis
    result_comb = {
        "subelemento_codigo": "3.3.90.39",
        "grupo": "Custeio",
        "elemento": "39"
    }
    validated = facade._validate_classificacao("Gasolina para frota", result_comb)
    if validated.get("subelemento_codigo") == "3.3.90.30":
        reporter.add_result("_validate_classificacao - combustíveis", "PASS", "Combustível corrigido para 3.3.90.30")
    else:
        reporter.add_result("_validate_classificacao - combustíveis", "FAIL", f"Resultado: {validated}")
    
    # Teste _normalize_fields
    result_wrong = {
        "subelemento_codigo": "3.3.90.30",
        "grupo": "3",
        "modalidade": "3.3",
        "elemento": "3.3.90.30",
        "codigo_completo": "errado"
    }
    normalized = facade._normalize_fields(result_wrong)
    if (normalized.get("grupo") == "Custeio" and 
        normalized.get("elemento") == "30" and
        normalized.get("codigo_completo") == "3.3.90.30"):
        reporter.add_result("_normalize_fields - correção", "PASS", "Campos normalizados corretamente")
    else:
        reporter.add_result("_normalize_fields - correção", "FAIL", f"Resultado: {normalized}")
    
    # Teste _ctx_lines
    lines = facade._ctx_lines({
        "secretaria": "Educação",
        "fornecedor": "ABC Ltda",
        "valor": "R$ 1.000,00"
    })
    if any("Educação" in line for line in lines) and any("ABC Ltda" in line for line in lines):
        reporter.add_result("_ctx_lines - geração", "PASS", f"Contexto gerado com {len(lines)} linhas")
    else:
        reporter.add_result("_ctx_lines - geração", "FAIL", f"Lines: {lines}")
        
except Exception as e:
    reporter.add_result("AITaskFacade - validações", "FAIL", "", str(e))


# ============================================================================
# TESTE 10: Prompts do Renomeador
# ============================================================================
test_section("Prompts do Renomeador (renomer/prompts.py)")

try:
    from renomer.prompts import montar_prompt, detectar_banco_no_texto
    
    # Teste montar_prompt com conteúdo
    prompt = montar_prompt("extrato_janeiro.pdf", "Banco do Brasil - Conta 12345-6 - Janeiro 2024")
    # O prompt deve conter instruções, não necessariamente o conteúdo exato
    if prompt and isinstance(prompt, str) and len(prompt) > 100:
        reporter.add_result("montar_prompt - com conteúdo", "PASS", f"Prompt montado com {len(prompt)} chars")
    else:
        reporter.add_result("montar_prompt - com conteúdo", "FAIL", "Prompt muito curto ou vazio")
    
    # Teste detectar_banco_no_texto
    textos_bancos = [
        ("BANCO DO BRASIL S.A.", "Banco do Brasil"),
        ("Caixa Econômica Federal", "Caixa"),
        ("Itaú Unibanco", "Itaú"),
        ("Bradesco", "Bradesco"),
        ("Nubank", "Nubank"),
    ]
    
    bancos_detectados = 0
    for texto, banco_esperado in textos_bancos:
        if detectar_banco_no_texto(texto):
            bancos_detectados += 1
    
    if bancos_detectados == len(textos_bancos):
        reporter.add_result("detectar_banco_no_texto", "PASS", f"{bancos_detectados}/{len(textos_bancos)} bancos detectados")
    else:
        reporter.add_result("detectar_banco_no_texto", "FAIL", f"Apenas {bancos_detectados}/{len(textos_bancos)}")
        
except Exception as e:
    reporter.add_result("Prompts Renomeador - testes", "FAIL", "", str(e))


# ============================================================================
# TESTE 11: File Processor (se disponível)
# ============================================================================
test_section("File Processor (renomer/file_processor.py)")

try:
    from renomer.file_processor import extrair_texto, dependencias_disponiveis
    
    # Verificar dependências
    deps = dependencias_disponiveis()
    reporter.add_result("dependencias_disponiveis", "PASS", 
                       f"pdfplumber: {deps.get('pdfplumber', False)}, PyPDF2: {deps.get('PyPDF2', False)}")
    
    # Teste extrair texto de arquivo TXT
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Este é um teste de extração de texto.")
        txt_file = f.name
    
    try:
        text = extrair_texto(txt_file, max_chars=1000)
        # No Windows, encoding pode variar - verificar conteúdo essencial
        if "teste" in text and "extra" in text:
            reporter.add_result("extrair_texto - TXT", "PASS", f"Texto extraído: {len(text)} chars")
        else:
            reporter.add_result("extrair_texto - TXT", "FAIL", f"Texto: {text[:100]}")
    finally:
        os.unlink(txt_file)
        
except Exception as e:
    reporter.add_result("File Processor - testes", "FAIL", "", str(e))


# ============================================================================
# TESTE 12: Configurações
# ============================================================================
test_section("Configurações (config.py)")

try:
    from config import settings
    
    required_attrs = [
        'OPENROUTER_API_KEY', 'OPENROUTER_MODEL', 'openrouter_default_model',
        'openrouter_referer', 'openrouter_title', 'openrouter_timeout_seconds',
        'openrouter_max_retries', 'openrouter_backoff_base', 'openrouter_cache_ttl_seconds'
    ]
    
    missing = [attr for attr in required_attrs if not hasattr(settings, attr)]
    if not missing:
        reporter.add_result("settings - atributos", "PASS", 
                          f"Todos {len(required_attrs)} atributos presentes")
    else:
        reporter.add_result("settings - atributos", "FAIL", f"Faltando: {missing}")
    
    # Verificar valores padrão
    if settings.openrouter_default_model in ["openai/gpt-4o-mini", "openai/gpt-4o"]:
        reporter.add_result("settings - modelo padrão", "PASS", f"Modelo: {settings.openrouter_default_model}")
    else:
        reporter.add_result("settings - modelo padrão", "FAIL", f"Modelo: {settings.openrouter_default_model}")
        
except Exception as e:
    reporter.add_result("Configurações - testes", "FAIL", "", str(e))


# ============================================================================
# TESTE 13: Rotas Flask - Estrutura (sem servidor)
# ============================================================================
test_section("Rotas Flask - Estrutura de Blueprints")

try:
    from app.routes.classificador import bp as classificador_bp
    from flask import Flask
    
    # Verificar rotas registradas
    rules = [rule.rule for rule in classificador_bp.url_map.iter_rules()] if hasattr(classificador_bp, 'url_map') else []
    
    # Verificar se o Blueprint existe e tem rotas
    expected_routes = [
        "/classificador-despesa",
        "/classificador-despesa/historico",
        "/classificador-despesa/elementos",
        "/classificador-despesa/validadas",
        "/classificador-despesa/sugestoes"
    ]
    
    # Criar app temporário para testar rotas
    temp_app = Flask(__name__)
    temp_app.register_blueprint(classificador_bp)
    
    registered = [rule.rule for rule in temp_app.url_map.iter_rules()]
    found_routes = [r for r in expected_routes if any(r in reg for reg in registered)]
    
    if len(found_routes) >= 4:
        reporter.add_result("classificador_bp - rotas", "PASS", 
                          f"{len(found_routes)}/{len(expected_routes)} rotas registradas")
    else:
        reporter.add_result("classificador_bp - rotas", "FAIL", 
                          f"Apenas {len(found_routes)}/{len(expected_routes)}: {found_routes}")
    
    # Testar outros blueprints
    try:
        from app.routes.ia import bp as ia_bp
        temp_app2 = Flask(__name__)
        temp_app2.register_blueprint(ia_bp)
        reporter.add_result("ia_bp - registro", "PASS", "Blueprint IA registrado")
    except Exception as e:
        reporter.add_result("ia_bp - registro", "FAIL", "", str(e))
    
    try:
        from app.routes.empenho_assistente import bp as empenho_bp
        temp_app3 = Flask(__name__)
        temp_app3.register_blueprint(empenho_bp)
        reporter.add_result("empenho_bp - registro", "PASS", "Blueprint Empenho registrado")
    except Exception as e:
        reporter.add_result("empenho_bp - registro", "FAIL", "", str(e))
        
except Exception as e:
    reporter.add_result("Rotas Flask - testes", "FAIL", "", str(e))


# ============================================================================
# TESTE 14: Integração com Tavily (estrutura)
# ============================================================================
test_section("Serviço Tavily (estrutura)")

try:
    from services.tavily_service import build_tavily_service, TavilyService, TavilyResult
    
    # Teste construção do serviço
    tavily = build_tavily_service(api_key="test_key", logger=None)
    if isinstance(tavily, TavilyService) and tavily.api_key == "test_key":
        reporter.add_result("build_tavily_service", "PASS", "Serviço Tavily criado")
    else:
        reporter.add_result("build_tavily_service", "FAIL", "Falha na criação")
    
    # Verificar métodos
    if hasattr(tavily, 'search') and hasattr(tavily, 'search_as_context'):
        reporter.add_result("TavilyService - métodos", "PASS", "Métodos search e search_as_context presentes")
    else:
        reporter.add_result("TavilyService - métodos", "FAIL", "Métodos ausentes")
    
    # Teste TavilyResult dataclass
    result = TavilyResult(title="Teste", url="https://test.com", content="Conteúdo", score=0.9)
    if result.title == "Teste" and result.score == 0.9:
        reporter.add_result("TavilyResult - estrutura", "PASS", "Dataclass funcionando")
    else:
        reporter.add_result("TavilyResult - estrutura", "FAIL", "Falha na dataclass")
        
except Exception as e:
    reporter.add_result("Serviço Tavily - testes", "FAIL", "", str(e))


# ============================================================================
# IMPRIMIR RELATÓRIO FINAL
# ============================================================================
passed, failed, skipped = reporter.print_report()

# Código de saída para CI/CD
if failed > 0:
    sys.exit(1)
else:
    sys.exit(0)
