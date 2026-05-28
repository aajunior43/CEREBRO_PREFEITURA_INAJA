@echo off
:: backup_db.bat — Executor do backup para o Windows Task Scheduler
:: Coloque o caminho correto do Python se necessário.

cd /d "%~dp0"

:: Tenta usar 'python' do PATH; ajuste para o caminho completo se necessário
:: Ex: C:\Python313\python.exe backup_db.py
python backup_db.py >> backup_db.log 2>&1

exit /b %ERRORLEVEL%
