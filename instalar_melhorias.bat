@echo off
REM ============================================================
REM Script de Instalacao Rapida das Melhorias
REM Sistema de Empenhos - Prefeitura de Inaja
REM ============================================================

echo.
echo ============================================================
echo   INSTALACAO RAPIDA DE MELHORIAS
echo   Sistema de Empenhos - Prefeitura de Inaja
echo ============================================================
echo.

REM Verificar se Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale Python 3.8+ primeiro.
    pause
    exit /b 1
)

echo [1/6] Verificando ambiente...
echo.

REM Verificar se o banco existe
if not exist "empenhos.db" (
    echo [AVISO] Banco de dados nao encontrado. Execute o servidor primeiro.
    echo         python server.py
    pause
    exit /b 1
)

echo [2/6] Criando backup de seguranca...
python backup_db.py
if errorlevel 1 (
    echo [ERRO] Falha ao criar backup. Abortando.
    pause
    exit /b 1
)
echo       Backup criado com sucesso!
echo.

echo [3/6] Adicionando indices criticos...
python add_critical_indexes.py
if errorlevel 1 (
    echo [ERRO] Falha ao adicionar indices.
    pause
    exit /b 1
)
echo       Indices adicionados com sucesso!
echo.

echo [4/6] Configurando arquivo .env...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo       Arquivo .env criado a partir do .env.example
        echo       IMPORTANTE: Edite o .env com suas configuracoes!
        echo.
    ) else (
        echo [AVISO] .env.example nao encontrado. Pule esta etapa.
    )
) else (
    echo       .env ja existe. Pulando...
    echo.
)

echo [5/6] Verificando indices instalados...
python add_critical_indexes.py --verify
echo.

echo [6/6] Executando benchmark de performance...
python add_critical_indexes.py --benchmark
echo.

echo ============================================================
echo   INSTALACAO CONCLUIDA COM SUCESSO!
echo ============================================================
echo.
echo Proximos passos:
echo   1. Edite o arquivo .env com suas configuracoes
echo   2. Reinicie o servidor: python server.py
echo   3. Acesse: http://localhost:5000/health
echo   4. Leia: RESUMO_EXECUTIVO.md
echo.
echo Documentacao completa:
echo   - MELHORIAS_SUGERIDAS.md
echo   - PLANO_ACAO_MELHORIAS.md
echo   - RESUMO_EXECUTIVO.md
echo.
echo ============================================================
pause
