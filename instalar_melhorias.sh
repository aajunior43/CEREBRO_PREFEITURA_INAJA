#!/bin/bash
# ============================================================
# Script de Instalacao Rapida das Melhorias
# Sistema de Empenhos - Prefeitura de Inaja
# ============================================================

set -e  # Parar em caso de erro

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "============================================================"
echo "  INSTALACAO RAPIDA DE MELHORIAS"
echo "  Sistema de Empenhos - Prefeitura de Inaja"
echo "============================================================"
echo ""

# Verificar se Python esta instalado
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERRO]${NC} Python nao encontrado. Instale Python 3.8+ primeiro."
    exit 1
fi

echo -e "${BLUE}[1/6]${NC} Verificando ambiente..."
echo ""

# Verificar se o banco existe
if [ ! -f "empenhos.db" ]; then
    echo -e "${YELLOW}[AVISO]${NC} Banco de dados nao encontrado. Execute o servidor primeiro."
    echo "         python3 server.py"
    exit 1
fi

echo -e "${BLUE}[2/6]${NC} Criando backup de seguranca..."
python3 backup_db.py
echo -e "${GREEN}       Backup criado com sucesso!${NC}"
echo ""

echo -e "${BLUE}[3/6]${NC} Adicionando indices criticos..."
python3 add_critical_indexes.py
echo -e "${GREEN}       Indices adicionados com sucesso!${NC}"
echo ""

echo -e "${BLUE}[4/6]${NC} Configurando arquivo .env..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}       Arquivo .env criado a partir do .env.example${NC}"
        echo -e "${YELLOW}       IMPORTANTE: Edite o .env com suas configuracoes!${NC}"
        echo ""
    else
        echo -e "${YELLOW}[AVISO]${NC} .env.example nao encontrado. Pule esta etapa."
    fi
else
    echo "       .env ja existe. Pulando..."
    echo ""
fi

echo -e "${BLUE}[5/6]${NC} Verificando indices instalados..."
python3 add_critical_indexes.py --verify
echo ""

echo -e "${BLUE}[6/6]${NC} Executando benchmark de performance..."
python3 add_critical_indexes.py --benchmark
echo ""

echo "============================================================"
echo -e "${GREEN}  INSTALACAO CONCLUIDA COM SUCESSO!${NC}"
echo "============================================================"
echo ""
echo "Proximos passos:"
echo "  1. Edite o arquivo .env com suas configuracoes"
echo "  2. Reinicie o servidor: python3 server.py"
echo "  3. Acesse: http://localhost:5000/health"
echo "  4. Leia: RESUMO_EXECUTIVO.md"
echo ""
echo "Documentacao completa:"
echo "  - MELHORIAS_SUGERIDAS.md"
echo "  - PLANO_ACAO_MELHORIAS.md"
echo "  - RESUMO_EXECUTIVO.md"
echo ""
echo "============================================================"
