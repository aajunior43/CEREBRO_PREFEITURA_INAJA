# Análise de Funções do Projeto

Este documento lista detalhadamente todas as funções encontradas nos módulos do projeto.

## Módulo: `./_apply_all.py`

### `read(path)`
- **Linha**: 7
- **Descrição**: Sem documentação.

### `write(path, content)`
- **Linha**: 11
- **Descrição**: Sem documentação.

## Módulo: `./audit_code.py`

### `audit(filename)`
- **Linha**: 7
- **Descrição**: Sem documentação.

## Módulo: `./backup_db.py`

### `log(msg)`
- **Linha**: 33
- **Descrição**: Sem documentação.

### `run(cmd, cwd)`
- **Linha**: 44
- **Descrição**: Sem documentação.

### `current_branch()`
- **Linha**: 53
- **Descrição**: Sem documentação.

### `remote_branch_exists()`
- **Linha**: 58
- **Descrição**: Sem documentação.

### `local_branch_exists()`
- **Linha**: 64
- **Descrição**: Sem documentação.

### `create_backup_branch_safe()`
- **Linha**: 69
- **Descrição**: Cria a branch 'backups' SEM fazer checkout no working dir principal.
Usa git plumbing: hash-object + mktree + commit-tree + update-ref.

### `ensure_backup_branch()`
- **Linha**: 135
- **Descrição**: Garante que a branch backups existe localmente e no remoto.

### `setup_worktree()`
- **Linha**: 145
- **Descrição**: Adiciona ou atualiza worktree para a branch backups.

### `wal_checkpoint(db_path)`
- **Linha**: 164
- **Descrição**: Sem documentação.

### `sql_dump(db_path, dest_path)`
- **Linha**: 174
- **Descrição**: Sem documentação.

### `backup()`
- **Linha**: 190
- **Descrição**: Sem documentação.

## Módulo: `./bot/bot.py`

### `sess(chat_id)`
- **Linha**: 53
- **Descrição**: Sem documentação.

### `user(chat_id)`
- **Linha**: 54
- **Descrição**: Sem documentação.

### `logged(chat_id)`
- **Linha**: 55
- **Descrição**: Sem documentação.

### `set_sess(chat_id, s, u)`
- **Linha**: 57
- **Descrição**: Sem documentação.

### `del_sess(chat_id)`
- **Linha**: 61
- **Descrição**: Sem documentação.

### `_api(chat_id, method, path)`
- **Linha**: 66
- **Descrição**: Sem documentação.

### `aget(cid, path)`
- **Linha**: 77
- **Descrição**: Sem documentação.

### `apost(cid, path)`
- **Linha**: 78
- **Descrição**: Sem documentação.

### `aput(cid, path)`
- **Linha**: 79
- **Descrição**: Sem documentação.

### `adel(cid, path)`
- **Linha**: 80
- **Descrição**: Sem documentação.

### `jget(cid, path)`
- **Linha**: 82
- **Descrição**: Sem documentação.

### `jpost(cid, path)`
- **Linha**: 86
- **Descrição**: Sem documentação.

### `esc(t)`
- **Linha**: 93
- **Descrição**: Sem documentação.

### `fmt_date(s)`
- **Linha**: 96
- **Descrição**: Sem documentação.

### `fmt_money(v)`
- **Linha**: 101
- **Descrição**: Sem documentação.

### `trunc(s, n)`
- **Linha**: 105
- **Descrição**: Sem documentação.

### `pri_emoji(p)`
- **Linha**: 109
- **Descrição**: Sem documentação.

### `status_emoji(s)`
- **Linha**: 112
- **Descrição**: Sem documentação.

### `auth_required(fn)`
- **Linha**: 128
- **Descrição**: Sem documentação.

### `KB_MENU()`
- **Linha**: 142
- **Descrição**: Sem documentação.

### `KB_BACK(to)`
- **Linha**: 162
- **Descrição**: Sem documentação.

### `KB_NAV(module, new_label)`
- **Linha**: 167
- **Descrição**: Sem documentação.

### `build_app()`
- **Linha**: 1137
- **Descrição**: Sem documentação.

## Módulo: `./extract_functions.py`

### `get_functions_from_file(filepath)`
- **Linha**: 7
- **Descrição**: Sem documentação.

## Módulo: `./renomer/file_processor.py`

### `extrair_texto(arquivo, max_chars)`
- **Linha**: 28
- **Descrição**: Extrai texto legível de um arquivo bancário.
Suporta PDF, OFX, QIF, TXT.
Retorna None se não conseguir extrair nada útil.

### `_extrair_pdf(arquivo, max_chars)`
- **Linha**: 50
- **Descrição**: Extrai texto de PDF usando pdfplumber (primary) ou PyPDF2 (fallback).

### `_extrair_ofx(arquivo, max_chars)`
- **Linha**: 84
- **Descrição**: Extrai texto de OFX lendo como texto plano (tags XML-like).

### `_extrair_txt(arquivo, max_chars)`
- **Linha**: 97
- **Descrição**: Lê arquivo de texto simples.

### `dependencias_disponiveis()`
- **Linha**: 110
- **Descrição**: Retorna quais bibliotecas de extração estão disponíveis.

## Módulo: `./renomer/organizador_ia.py`

### `OrganizadorIA.__init__(self, diretorio_origem, diretorio_destino, api_key, modelo)`
- **Linha**: 21
- **Descrição**: Sem documentação.

### `OrganizadorIA._analisar_ia(self, arquivo)`
- **Linha**: 38
- **Descrição**: Extrai texto do arquivo (se possível) e chama OpenRouter.
Retorna dict com mes, ano, conta, banco, tipo_conta, confianca.

### `OrganizadorIA.processar_arquivo(self, arquivo, modo_teste)`
- **Linha**: 72
- **Descrição**: Processa arquivo usando IA (com leitura de conteúdo) e fallback local.

### `__init__(self, diretorio_origem, diretorio_destino, api_key, modelo)`
- **Linha**: 21
- **Descrição**: Sem documentação.

### `_analisar_ia(self, arquivo)`
- **Linha**: 38
- **Descrição**: Extrai texto do arquivo (se possível) e chama OpenRouter.
Retorna dict com mes, ano, conta, banco, tipo_conta, confianca.

### `processar_arquivo(self, arquivo, modo_teste)`
- **Linha**: 72
- **Descrição**: Processa arquivo usando IA (com leitura de conteúdo) e fallback local.

## Módulo: `./renomer/organizador_local_avancado.py`

### `OrganizadorLocalAvancado.__init__(self, diretorio_origem, diretorio_destino)`
- **Linha**: 20
- **Descrição**: Inicializa organizador local avançado

### `OrganizadorLocalAvancado.setup_logging(self)`
- **Linha**: 75
- **Descrição**: Configura logging sem poluir configuração global.

### `OrganizadorLocalAvancado.detectar_data(self, texto, caminho_completo)`
- **Linha**: 84
- **Descrição**: Detecta mês e ano no texto usando múltiplos padrões

### `OrganizadorLocalAvancado.detectar_conta(self, texto)`
- **Linha**: 161
- **Descrição**: Detecta número da conta usando múltiplos padrões

### `OrganizadorLocalAvancado.processar_arquivo(self, arquivo, modo_teste)`
- **Linha**: 205
- **Descrição**: Processa um arquivo individual

### `OrganizadorLocalAvancado.organizar_arquivos(self, modo_teste)`
- **Linha**: 273
- **Descrição**: Organiza todos os arquivos

### `__init__(self, diretorio_origem, diretorio_destino)`
- **Linha**: 20
- **Descrição**: Inicializa organizador local avançado

### `setup_logging(self)`
- **Linha**: 75
- **Descrição**: Configura logging sem poluir configuração global.

### `detectar_data(self, texto, caminho_completo)`
- **Linha**: 84
- **Descrição**: Detecta mês e ano no texto usando múltiplos padrões

### `detectar_conta(self, texto)`
- **Linha**: 161
- **Descrição**: Detecta número da conta usando múltiplos padrões

### `processar_arquivo(self, arquivo, modo_teste)`
- **Linha**: 205
- **Descrição**: Processa um arquivo individual

### `organizar_arquivos(self, modo_teste)`
- **Linha**: 273
- **Descrição**: Organiza todos os arquivos

## Módulo: `./renomer/prompts.py`

### `montar_prompt(nome_arquivo, texto_conteudo)`
- **Linha**: 53
- **Descrição**: Monta o prompt para envio à IA.
Se texto_conteudo estiver disponível, usa análise do conteúdo.
Caso contrário, analisa apenas o nome do arquivo.

### `_prompt_com_conteudo(nome_arquivo, texto)`
- **Linha**: 65
- **Descrição**: Sem documentação.

### `_prompt_nome_apenas(nome_arquivo)`
- **Linha**: 93
- **Descrição**: Sem documentação.

### `detectar_banco_no_texto(texto)`
- **Linha**: 110
- **Descrição**: Detecta nome do banco no texto extraído do arquivo.

## Módulo: `./routes/_shared.py`

### `get_db()`
- **Linha**: 9
- **Descrição**: Sem documentação.

### `require_login(fn)`
- **Linha**: 14
- **Descrição**: Decorator: exige sessao autenticada. Protege endpoints que gastam
creditos de IA ou recursos do servidor contra acesso anonimo.

### `registrar_auditoria(conn, tabela, registro_id, operacao, dados_anteriores, dados_novos)`
- **Linha**: 29
- **Descrição**: Insere uma entrada no audit_trail para rastrear criações, edições e exclusões.

### `row_to_dict(row)`
- **Linha**: 51
- **Descrição**: Sem documentação.

### `_get_openrouter_config(conn, api_key_override, model_override)`
- **Linha**: 55
- **Descrição**: Sem documentação.

### `_build_ai_service(api_key, model)`
- **Linha**: 87
- **Descrição**: Sem documentação.

### `_build_ai_facade(api_key, model)`
- **Linha**: 103
- **Descrição**: Sem documentação.

### `_extract_json_block(text)`
- **Linha**: 109
- **Descrição**: Sem documentação.

### `wrapper()`
- **Linha**: 20
- **Descrição**: Sem documentação.

## Módulo: `./routes/auth.py`

### `_hash(s)`
- **Linha**: 13
- **Descrição**: Sem documentação.

### `_verify_password(senha_hash, senha_plana)`
- **Linha**: 17
- **Descrição**: Sem documentação.

### `init_usuarios_table(app)`
- **Linha**: 25
- **Descrição**: Sem documentação.

### `_seed_admin(admin_password, app)`
- **Linha**: 85
- **Descrição**: Sem documentação.

### `init_auth_system(admin_password, app)`
- **Linha**: 130
- **Descrição**: Sem documentação.

### `init_auth_hash(admin_password)`
- **Linha**: 135
- **Descrição**: Sem documentação.

### `_usuario_to_dict(row)`
- **Linha**: 139
- **Descrição**: Sem documentação.

### `login()`
- **Linha**: 156
- **Descrição**: Sem documentação.

### `verificar_auth()`
- **Linha**: 205
- **Descrição**: Sem documentação.

### `logout()`
- **Linha**: 219
- **Descrição**: Sem documentação.

### `auth_adm_legacy()`
- **Linha**: 232
- **Descrição**: Sem documentação.

### `listar_usuarios()`
- **Linha**: 265
- **Descrição**: Sem documentação.

### `criar_usuario()`
- **Linha**: 275
- **Descrição**: Sem documentação.

### `atualizar_usuario(uid)`
- **Linha**: 312
- **Descrição**: Sem documentação.

### `deletar_usuario(uid)`
- **Linha**: 349
- **Descrição**: Sem documentação.

### `alterar_senha()`
- **Linha**: 363
- **Descrição**: Sem documentação.

### `ping()`
- **Linha**: 396
- **Descrição**: Sem documentação.

### `health()`
- **Linha**: 401
- **Descrição**: Sem documentação.

## Módulo: `./routes/calendario.py`

### `_db()`
- **Linha**: 9
- **Descrição**: Sem documentação.

### `calendario_get()`
- **Linha**: 18
- **Descrição**: Sem documentação.

### `calendario_evento_criar()`
- **Linha**: 57
- **Descrição**: Sem documentação.

### `calendario_evento_atualizar(evento_id)`
- **Linha**: 88
- **Descrição**: Sem documentação.

### `calendario_evento_excluir(evento_id)`
- **Linha**: 123
- **Descrição**: Sem documentação.

### `calendario_override_criar()`
- **Linha**: 140
- **Descrição**: Sem documentação.

### `calendario_override_excluir(data)`
- **Linha**: 158
- **Descrição**: Sem documentação.

### `calendario_regras_salvar()`
- **Linha**: 170
- **Descrição**: Sem documentação.

## Módulo: `./routes/classificador.py`

### `classificador_despesa()`
- **Linha**: 12
- **Descrição**: Sem documentação.

### `classificador_historico()`
- **Linha**: 101
- **Descrição**: Sem documentação.

### `classificador_historico_delete(hid)`
- **Linha**: 145
- **Descrição**: Sem documentação.

### `classificador_historico_limpar()`
- **Linha**: 157
- **Descrição**: Sem documentação.

## Módulo: `./routes/cnpj.py`

### `_fmt_moeda(v)`
- **Linha**: 16
- **Descrição**: Sem documentação.

### `_buscar_cnpja(cnpj, api_key)`
- **Linha**: 25
- **Descrição**: Sem documentação.

### `_buscar_receitaws(cnpj)`
- **Linha**: 83
- **Descrição**: Sem documentação.

### `_buscar_brasilapi(cnpj)`
- **Linha**: 120
- **Descrição**: Sem documentação.

### `cnpj_buscar()`
- **Linha**: 174
- **Descrição**: Sem documentação.

## Módulo: `./routes/config.py`

### `config_get()`
- **Linha**: 20
- **Descrição**: Sem documentação.

### `config_set()`
- **Linha**: 34
- **Descrição**: Sem documentação.

### `admin_summary()`
- **Linha**: 53
- **Descrição**: Sem documentação.

### `_parse_aut_keys(value)`
- **Linha**: 70
- **Descrição**: Sem documentação.

## Módulo: `./routes/credores.py`

### `get_db()`
- **Linha**: 25
- **Descrição**: Sem documentação.

### `row_to_dict(row)`
- **Linha**: 31
- **Descrição**: Sem documentação.

### `_should_include_summary(args)`
- **Linha**: 35
- **Descrição**: Sem documentação.

### `_invalidate_summary_cache()`
- **Linha**: 40
- **Descrição**: Sem documentação.

### `_get_summary(conn)`
- **Linha**: 45
- **Descrição**: Sem documentação.

### `get_credores()`
- **Linha**: 66
- **Descrição**: Sem documentação.

### `add_credor()`
- **Linha**: 112
- **Descrição**: Sem documentação.

### `update_credor(cid)`
- **Linha**: 162
- **Descrição**: Sem documentação.

### `delete_credor(cid)`
- **Linha**: 238
- **Descrição**: Sem documentação.

### `listar_deletados()`
- **Linha**: 263
- **Descrição**: Sem documentação.

### `restaurar_credor(cid)`
- **Linha**: 276
- **Descrição**: Sem documentação.

### `duplicate_credor(cid)`
- **Linha**: 318
- **Descrição**: Sem documentação.

## Módulo: `./routes/despesas.py`

### `despesas_listar_importacoes()`
- **Linha**: 17
- **Descrição**: Sem documentação.

### `despesas_importar()`
- **Linha**: 43
- **Descrição**: Sem documentação.

### `despesas_carregar(imp_id)`
- **Linha**: 137
- **Descrição**: Sem documentação.

### `despesas_excluir(imp_id)`
- **Linha**: 186
- **Descrição**: Sem documentação.

### `despesas_resumo(imp_id)`
- **Linha**: 209
- **Descrição**: Sem documentação.

### `despesas_ia()`
- **Linha**: 309
- **Descrição**: Sem documentação.

### `empenhos_csv_importar()`
- **Linha**: 407
- **Descrição**: Sem documentação.

### `empenhos_csv_listar()`
- **Linha**: 449
- **Descrição**: Sem documentação.

### `empenhos_csv_carregar(imp_id)`
- **Linha**: 465
- **Descrição**: Sem documentação.

### `empenhos_csv_excluir(imp_id)`
- **Linha**: 481
- **Descrição**: Sem documentação.

### `despesas_dados_csv()`
- **Linha**: 496
- **Descrição**: Sem documentação.

### `parse_val(v)`
- **Linha**: 227
- **Descrição**: Sem documentação.

### `agrupar(col_key)`
- **Linha**: 244
- **Descrição**: Sem documentação.

### `_fmt_brl(v)`
- **Linha**: 322
- **Descrição**: Sem documentação.

### `_build_ctx_text(ctx)`
- **Linha**: 332
- **Descrição**: Sem documentação.

## Módulo: `./routes/documentos.py`

### `get_db()`
- **Linha**: 25
- **Descrição**: Sem documentação.

### `extrair_texto_pdf(abs_path)`
- **Linha**: 30
- **Descrição**: Sem documentação.

### `indexar_documento(doc_id, abs_path)`
- **Linha**: 47
- **Descrição**: Sem documentação.

### `row_to_dict(row)`
- **Linha**: 84
- **Descrição**: Sem documentação.

### `build_document_storage(categoria, referencia, original_name)`
- **Linha**: 91
- **Descrição**: Sem documentação.

### `persist_document_file(original_name, content, categoria, referencia, descricao, mime_type)`
- **Linha**: 110
- **Descrição**: Sem documentação.

### `documentos_listar()`
- **Linha**: 162
- **Descrição**: Sem documentação.

### `documentos_enviar()`
- **Linha**: 226
- **Descrição**: Sem documentação.

### `documentos_salvar_conteudo()`
- **Linha**: 289
- **Descrição**: Sem documentação.

### `documentos_download(doc_id)`
- **Linha**: 319
- **Descrição**: Sem documentação.

### `documentos_view(doc_id)`
- **Linha**: 345
- **Descrição**: Sem documentação.

### `documentos_excluir(doc_id)`
- **Linha**: 366
- **Descrição**: Sem documentação.

### `_parse_autentique_keys(value)`
- **Linha**: 402
- **Descrição**: Sem documentação.

### `_get_autentique_config(conn, api_key_override)`
- **Linha**: 418
- **Descrição**: Sem documentação.

### `_normalize_phone_br(value)`
- **Linha**: 452
- **Descrição**: Sem documentação.

### `_autentique_guess_status()`
- **Linha**: 461
- **Descrição**: Sem documentação.

### `_autentique_scan_payload(node, trail)`
- **Linha**: 485
- **Descrição**: Sem documentação.

### `_autentique_extract_webhook(payload)`
- **Linha**: 500
- **Descrição**: Sem documentação.

### `_autentique_save_signed_document(download_url, original_name, api_key)`
- **Linha**: 558
- **Descrição**: Sem documentação.

### `autentique_testar()`
- **Linha**: 581
- **Descrição**: Sem documentação.

### `autentique_saldo()`
- **Linha**: 615
- **Descrição**: Sem documentação.

### `autentique_listar_chaves()`
- **Linha**: 664
- **Descrição**: Sem documentação.

### `autentique_enviar_whatsapp()`
- **Linha**: 690
- **Descrição**: Sem documentação.

### `autentique_listar_envios()`
- **Linha**: 816
- **Descrição**: Sem documentação.

### `autentique_excluir_envio(envio_id)`
- **Linha**: 833
- **Descrição**: Sem documentação.

### `autentique_listar_contatos()`
- **Linha**: 849
- **Descrição**: Sem documentação.

### `autentique_salvar_contato()`
- **Linha**: 862
- **Descrição**: Sem documentação.

### `autentique_excluir_contato(contato_id)`
- **Linha**: 901
- **Descrição**: Sem documentação.

### `autentique_download_assinado(envio_id)`
- **Linha**: 919
- **Descrição**: Sem documentação.

### `autentique_view_assinado(envio_id)`
- **Linha**: 948
- **Descrição**: Sem documentação.

### `autentique_sincronizar_envio(envio_id)`
- **Linha**: 971
- **Descrição**: Sem documentação.

### `autentique_webhook()`
- **Linha**: 1062
- **Descrição**: Sem documentação.

### `documentos_atualizar(doc_id)`
- **Linha**: 1162
- **Descrição**: Sem documentação.

### `documentos_sugerir_nome(doc_id)`
- **Linha**: 1205
- **Descrição**: Sem documentação.

### `documentos_obter_thumbnail(doc_id)`
- **Linha**: 1276
- **Descrição**: Sem documentação.

### `documentos_salvar_thumbnail(doc_id)`
- **Linha**: 1288
- **Descrição**: Sem documentação.

### `documentos_sugerir_metadados_csv(doc_id)`
- **Linha**: 1318
- **Descrição**: Sem documentação.

### `_worker()`
- **Linha**: 52
- **Descrição**: Sem documentação.

## Módulo: `./routes/empenho_assistente.py`

### `_clean_value(value)`
- **Linha**: 10
- **Descrição**: Sem documentação.

### `_normalize_empenho_payload(payload)`
- **Linha**: 18
- **Descrição**: Sem documentação.

### `_serialize_json(value)`
- **Linha**: 43
- **Descrição**: Sem documentação.

### `_extract_text_from_result(result)`
- **Linha**: 61
- **Descrição**: Sem documentação.

### `_save_empenho_assistente_history(conn, action, payload, result, meta)`
- **Linha**: 69
- **Descrição**: Sem documentação.

### `empenho_assistente()`
- **Linha**: 121
- **Descrição**: Sem documentação.

### `empenho_assistente_historico()`
- **Linha**: 191
- **Descrição**: Sem documentação.

## Módulo: `./routes/empenhos.py`

### `get_db()`
- **Linha**: 10
- **Descrição**: Sem documentação.

### `get_empenhos(ano, mes)`
- **Linha**: 18
- **Descrição**: Sem documentação.

### `toggle_empenho()`
- **Linha**: 29
- **Descrição**: Sem documentação.

### `empenho_lote()`
- **Linha**: 57
- **Descrição**: Sem documentação.

### `get_historico(cid)`
- **Linha**: 90
- **Descrição**: Sem documentação.

## Módulo: `./routes/expertmoney.py`

### `date_tag()`
- **Linha**: 38
- **Descrição**: Sem documentação.

### `build_ofx_meta(parsed)`
- **Linha**: 42
- **Descrição**: Sem documentação.

### `normalize_acc_number(num)`
- **Linha**: 56
- **Descrição**: Sem documentação.

### `get_tx_date(t)`
- **Linha**: 60
- **Descrição**: Sem documentação.

### `fmt_brl(v)`
- **Linha**: 70
- **Descrição**: Sem documentação.

### `get_em_session_data(session_id)`
- **Linha**: 77
- **Descrição**: Sem documentação.

### `_build_db_records(session_id, account, transactions, investments, all_alerts, stats, acc_files)`
- **Linha**: 130
- **Descrição**: Sem documentação.

### `em_health()`
- **Linha**: 182
- **Descrição**: Sem documentação.

### `em_list_accounts()`
- **Linha**: 199
- **Descrição**: Sem documentação.

### `em_create_account()`
- **Linha**: 210
- **Descrição**: Sem documentação.

### `em_get_account(acc_id)`
- **Linha**: 235
- **Descrição**: Sem documentação.

### `em_update_account(acc_id)`
- **Linha**: 248
- **Descrição**: Sem documentação.

### `em_delete_account(acc_id)`
- **Linha**: 269
- **Descrição**: Sem documentação.

### `em_account_history(acc_id)`
- **Linha**: 283
- **Descrição**: Sem documentação.

### `em_upload()`
- **Linha**: 300
- **Descrição**: Sem documentação.

### `em_local_folders()`
- **Linha**: 344
- **Descrição**: Sem documentação.

### `em_load_local_folder()`
- **Linha**: 369
- **Descrição**: Sem documentação.

### `em_local_zips()`
- **Linha**: 397
- **Descrição**: Sem documentação.

### `em_load_local_zip()`
- **Linha**: 431
- **Descrição**: Sem documentação.

### `em_analyze(session_id)`
- **Linha**: 465
- **Descrição**: Sem documentação.

### `em_analyze_batch()`
- **Linha**: 598
- **Descrição**: Sem documentação.

### `em_get_session(session_id)`
- **Linha**: 685
- **Descrição**: Sem documentação.

### `em_delete_session(session_id)`
- **Linha**: 696
- **Descrição**: Sem documentação.

### `em_compare_sessions(session_id, sid2)`
- **Linha**: 709
- **Descrição**: Sem documentação.

### `em_latest_session()`
- **Linha**: 724
- **Descrição**: Sem documentação.

### `em_stats_global()`
- **Linha**: 745
- **Descrição**: Sem documentação.

### `em_alerts_summary()`
- **Linha**: 778
- **Descrição**: Sem documentação.

### `em_resolve_alert(alert_id)`
- **Linha**: 797
- **Descrição**: Sem documentação.

### `em_unresolve_alert(alert_id)`
- **Linha**: 815
- **Descrição**: Sem documentação.

### `em_update_alert_note(alert_id)`
- **Linha**: 829
- **Descrição**: Sem documentação.

### `em_add_attachment(alert_id)`
- **Linha**: 850
- **Descrição**: Sem documentação.

### `em_get_attachments(alert_id)`
- **Linha**: 875
- **Descrição**: Sem documentação.

### `em_download_attachment(att_id)`
- **Linha**: 886
- **Descrição**: Sem documentação.

### `em_export_excel(session_id)`
- **Linha**: 905
- **Descrição**: Sem documentação.

### `em_export_pdf(session_id)`
- **Linha**: 926
- **Descrição**: Sem documentação.

### `em_export_csv(session_id)`
- **Linha**: 946
- **Descrição**: Sem documentação.

### `em_search()`
- **Linha**: 964
- **Descrição**: Sem documentação.

### `em_cdi()`
- **Linha**: 980
- **Descrição**: Sem documentação.

### `em_audit(account_id)`
- **Linha**: 993
- **Descrição**: Sem documentação.

### `em_get_account_config(account_id)`
- **Linha**: 1023
- **Descrição**: Sem documentação.

### `em_put_account_config(account_id)`
- **Linha**: 1044
- **Descrição**: Sem documentação.

### `em_delete_account_config(account_id, key)`
- **Linha**: 1070
- **Descrição**: Sem documentação.

### `em_email_summary(session_id)`
- **Linha**: 1082
- **Descrição**: Sem documentação.

### `em_cross_analysis()`
- **Linha**: 1104
- **Descrição**: Sem documentação.

### `get_key(x)`
- **Linha**: 361
- **Descrição**: Sem documentação.

### `get_kws(memo)`
- **Linha**: 1139
- **Descrição**: Sem documentação.

### `is_similar(m1, m2)`
- **Linha**: 1142
- **Descrição**: Sem documentação.

## Módulo: `./routes/expertmoney_db.py`

### `get_em_db_connection()`
- **Linha**: 112
- **Descrição**: Sem documentação.

### `init_expertmoney_tables(app)`
- **Linha**: 120
- **Descrição**: Cria tabelas do ExpertMoney no banco do Cerebro.

### `save_em_session(session, alerts, transactions)`
- **Linha**: 134
- **Descrição**: Sem documentação.

### `get_em_session_with_alerts(conn, session_id)`
- **Linha**: 170
- **Descrição**: Sem documentação.

### `get_em_account_history(conn, account_id)`
- **Linha**: 192
- **Descrição**: Sem documentação.

### `load_em_config(conn, account_id, default_config)`
- **Linha**: 199
- **Descrição**: Sem documentação.

## Módulo: `./routes/extratos.py`

### `extratos_modelos_openrouter()`
- **Linha**: 12
- **Descrição**: Sem documentação.

## Módulo: `./routes/fornecimento.py`

### `get_db()`
- **Linha**: 10
- **Descrição**: Sem documentação.

### `safe_float(v)`
- **Linha**: 15
- **Descrição**: Sem documentação.

### `parse_money(s)`
- **Linha**: 22
- **Descrição**: Sem documentação.

### `get_fornecimento_dados()`
- **Linha**: 45
- **Descrição**: Sem documentação.

### `add_fornecimento_dado()`
- **Linha**: 62
- **Descrição**: Sem documentação.

### `del_fornecimento_dado()`
- **Linha**: 82
- **Descrição**: Sem documentação.

### `list_solicitacoes()`
- **Linha**: 101
- **Descrição**: Sem documentação.

### `create_solicitacao()`
- **Linha**: 162
- **Descrição**: Sem documentação.

### `update_solicitacao(id)`
- **Linha**: 244
- **Descrição**: Sem documentação.

### `delete_solicitacao(id)`
- **Linha**: 338
- **Descrição**: Sem documentação.

### `duplicate_solicitacao(id)`
- **Linha**: 358
- **Descrição**: Sem documentação.

## Módulo: `./routes/helpers.py`

### `rate_limited(key, max_hits, window)`
- **Linha**: 22
- **Descrição**: Sem documentação.

### `normalizar_cnpj(cnpj)`
- **Linha**: 34
- **Descrição**: Sem documentação.

### `cnpj_valido(cnpj)`
- **Linha**: 38
- **Descrição**: Sem documentação.

### `credor_payload(data)`
- **Linha**: 57
- **Descrição**: Sem documentação.

### `buscar_credor_duplicado(conn, cnpj)`
- **Linha**: 133
- **Descrição**: Sem documentação.

### `montar_filtros_credores(args)`
- **Linha**: 145
- **Descrição**: Sem documentação.

### `parse_bool(value)`
- **Linha**: 200
- **Descrição**: Sem documentação.

### `slugify(value, fallback)`
- **Linha**: 204
- **Descrição**: Sem documentação.

### `clean_value(value)`
- **Linha**: 211
- **Descrição**: Sem documentação.

### `api_error(message, status, details)`
- **Linha**: 219
- **Descrição**: Sem documentação.

### `has_value(key)`
- **Linha**: 61
- **Descrição**: Sem documentação.

## Módulo: `./routes/ia.py`

### `proxy_ia_chat()`
- **Linha**: 11
- **Descrição**: Sem documentação.

## Módulo: `./routes/kanban.py`

### `get_db()`
- **Linha**: 15
- **Descrição**: Sem documentação.

### `row_to_dict(row)`
- **Linha**: 21
- **Descrição**: Sem documentação.

### `_normalize_status(value)`
- **Linha**: 25
- **Descrição**: Sem documentação.

### `_normalize_priority(value)`
- **Linha**: 44
- **Descrição**: Sem documentação.

### `_sanitize_task(task)`
- **Linha**: 58
- **Descrição**: Sem documentação.

### `_get_openrouter_config(conn, api_key_override, model_override)`
- **Linha**: 67
- **Descrição**: Sem documentação.

### `_build_ai_service(api_key, model)`
- **Linha**: 104
- **Descrição**: Sem documentação.

### `_extract_json_block(text)`
- **Linha**: 121
- **Descrição**: Sem documentação.

### `_kanban_ai_completion(action, user_prompt, task, api_key_override, model_override, status_hint, priority_hint)`
- **Linha**: 142
- **Descrição**: Sem documentação.

### `kanban_listar()`
- **Linha**: 238
- **Descrição**: Sem documentação.

### `kanban_criar()`
- **Linha**: 274
- **Descrição**: Sem documentação.

### `kanban_atualizar(task_id)`
- **Linha**: 322
- **Descrição**: Sem documentação.

### `kanban_excluir(task_id)`
- **Linha**: 372
- **Descrição**: Sem documentação.

### `_handle_ai_result(parsed, error, sanitizer)`
- **Linha**: 392
- **Descrição**: Sem documentação.

### `kanban_ai_create()`
- **Linha**: 403
- **Descrição**: Sem documentação.

### `kanban_ai_improve()`
- **Linha**: 424
- **Descrição**: Sem documentação.

### `kanban_ai_breakdown()`
- **Linha**: 444
- **Descrição**: Sem documentação.

### `kanban_ai_plan()`
- **Linha**: 476
- **Descrição**: Sem documentação.

### `kanban_ai_classify()`
- **Linha**: 520
- **Descrição**: Sem documentação.

### `kanban_ai_stale()`
- **Linha**: 562
- **Descrição**: Sem documentação.

### `kanban_ai_professional_rewrite()`
- **Linha**: 611
- **Descrição**: Sem documentação.

### `list_anexos(task_id)`
- **Linha**: 632
- **Descrição**: Sem documentação.

### `upload_anexo(task_id)`
- **Linha**: 650
- **Descrição**: Sem documentação.

### `anexo_download(task_id, attachment_id)`
- **Linha**: 697
- **Descrição**: Sem documentação.

### `anexo_excluir(task_id, attachment_id)`
- **Linha**: 721
- **Descrição**: Sem documentação.

## Módulo: `./routes/logs.py`

### `get_logs()`
- **Linha**: 11
- **Descrição**: Sem documentação.

### `get_audit_trail()`
- **Linha**: 38
- **Descrição**: Sem documentação.

### `get_server_log()`
- **Linha**: 77
- **Descrição**: Sem documentação.

## Módulo: `./routes/mural.py`

### `_require_auth(fn)`
- **Linha**: 24
- **Descrição**: Sem documentação.

### `_pode_modificar(autor_recado)`
- **Linha**: 34
- **Descrição**: Autor do recado ou administrador podem editar/excluir.

### `_parse_valor(valor_raw)`
- **Linha**: 42
- **Descrição**: Sem documentação.

### `_parse_credor_id(valor_raw)`
- **Linha**: 56
- **Descrição**: Sem documentação.

### `_normalize_choice(value, allowed, default)`
- **Linha**: 66
- **Descrição**: Sem documentação.

### `broadcast_mural_event(event_type, data)`
- **Linha**: 72
- **Descrição**: Sem documentação.

### `mural_listar()`
- **Linha**: 93
- **Descrição**: Sem documentação.

### `mural_criar()`
- **Linha**: 164
- **Descrição**: Sem documentação.

### `mural_atualizar(recado_id)`
- **Linha**: 217
- **Descrição**: Sem documentação.

### `mural_excluir(recado_id)`
- **Linha**: 304
- **Descrição**: Sem documentação.

### `mural_credores_dropdown()`
- **Linha**: 324
- **Descrição**: Sem documentação.

### `mural_anexo_criar(recado_id)`
- **Linha**: 346
- **Descrição**: Sem documentação.

### `mural_anexo_download(recado_id, attachment_id)`
- **Linha**: 394
- **Descrição**: Sem documentação.

### `mural_anexo_excluir(recado_id, attachment_id)`
- **Linha**: 419
- **Descrição**: Sem documentação.

### `mural_events()`
- **Linha**: 437
- **Descrição**: Sem documentação.

### `mural_destaque_get()`
- **Linha**: 478
- **Descrição**: Sem documentação.

### `mural_destaque_set()`
- **Linha**: 490
- **Descrição**: Sem documentação.

### `mural_comentarios_listar(recado_id)`
- **Linha**: 513
- **Descrição**: Sem documentação.

### `mural_comentario_criar(recado_id)`
- **Linha**: 527
- **Descrição**: Sem documentação.

### `wrapper()`
- **Linha**: 26
- **Descrição**: Sem documentação.

### `event_stream()`
- **Linha**: 439
- **Descrição**: Sem documentação.

## Módulo: `./routes/pdf.py`

### `pdf_mesclar()`
- **Linha**: 12
- **Descrição**: Sem documentação.

### `pdf_dividir()`
- **Linha**: 35
- **Descrição**: Sem documentação.

### `pdf_proteger()`
- **Linha**: 95
- **Descrição**: Sem documentação.

## Módulo: `./routes/prazos.py`

### `get_db()`
- **Linha**: 10
- **Descrição**: Sem documentação.

### `prazos_listar()`
- **Linha**: 17
- **Descrição**: Sem documentação.

### `prazos_resumo()`
- **Linha**: 47
- **Descrição**: Sem documentação.

### `prazos_criar()`
- **Linha**: 82
- **Descrição**: Sem documentação.

### `prazos_atualizar(prazo_id)`
- **Linha**: 114
- **Descrição**: Sem documentação.

### `prazos_excluir(prazo_id)`
- **Linha**: 151
- **Descrição**: Sem documentação.

### `prazos_ai_extrair()`
- **Linha**: 165
- **Descrição**: Sem documentação.

## Módulo: `./routes/protocolos.py`

### `get_db()`
- **Linha**: 11
- **Descrição**: Sem documentação.

### `_proximo_numero_protocolo(conn)`
- **Linha**: 16
- **Descrição**: Sem documentação.

### `protocolo_proximo_numero()`
- **Linha**: 34
- **Descrição**: Sem documentação.

### `protocolos_listar()`
- **Linha**: 43
- **Descrição**: Sem documentação.

### `protocolos_criar()`
- **Linha**: 82
- **Descrição**: Sem documentação.

### `protocolos_atualizar(prot_id)`
- **Linha**: 123
- **Descrição**: Sem documentação.

### `protocolos_excluir(prot_id)`
- **Linha**: 171
- **Descrição**: Sem documentação.

### `protocolo_anexos_listar(prot_id)`
- **Linha**: 187
- **Descrição**: Sem documentação.

### `protocolo_anexos_upload(prot_id)`
- **Linha**: 201
- **Descrição**: Sem documentação.

### `protocolo_anexo_download(prot_id, anexo_id)`
- **Linha**: 247
- **Descrição**: Sem documentação.

### `protocolo_anexo_excluir(prot_id, anexo_id)`
- **Linha**: 273
- **Descrição**: Sem documentação.

## Módulo: `./routes/rpas.py`

### `get_db()`
- **Linha**: 9
- **Descrição**: Sem documentação.

### `row_to_dict(row)`
- **Linha**: 14
- **Descrição**: Sem documentação.

### `get_rpas()`
- **Linha**: 20
- **Descrição**: Sem documentação.

### `create_rpa()`
- **Linha**: 44
- **Descrição**: Sem documentação.

### `update_rpa(rpa_id)`
- **Linha**: 86
- **Descrição**: Sem documentação.

### `delete_rpa(rpa_id)`
- **Linha**: 131
- **Descrição**: Sem documentação.

## Módulo: `./scratch/benchmark_perf.py`

### `benchmark()`
- **Linha**: 10
- **Descrição**: Sem documentação.

## Módulo: `./scratch/migrate.py`

### `run_migration()`
- **Linha**: 3
- **Descrição**: Sem documentação.

## Módulo: `./scratch/show_users.py`

### `load_dotenv()`
- **Linha**: 8
- **Descrição**: Sem documentação.

### `show()`
- **Linha**: 16
- **Descrição**: Sem documentação.

## Módulo: `./scratch/test_apis.py`

### `TestAPIsAuthentication.setUpClass(cls)`
- **Linha**: 12
- **Descrição**: Sem documentação.

### `TestAPIsAuthentication.tearDownClass(cls)`
- **Linha**: 27
- **Descrição**: Sem documentação.

### `TestAPIsAuthentication.test_anonymous_access_blocked(self)`
- **Linha**: 37
- **Descrição**: Verifica se acessos anônimos a rotas protegidas retornam 401.

### `TestAPIsAuthentication.test_authenticated_access_allowed(self)`
- **Linha**: 64
- **Descrição**: Verifica se acessos com login ativo são autorizados.

### `setUpClass(cls)`
- **Linha**: 12
- **Descrição**: Sem documentação.

### `tearDownClass(cls)`
- **Linha**: 27
- **Descrição**: Sem documentação.

### `test_anonymous_access_blocked(self)`
- **Linha**: 37
- **Descrição**: Verifica se acessos anônimos a rotas protegidas retornam 401.

### `test_authenticated_access_allowed(self)`
- **Linha**: 64
- **Descrição**: Verifica se acessos com login ativo são autorizados.

## Módulo: `./scratch/test_ia_suggestion.py`

### `load_dotenv()`
- **Linha**: 10
- **Descrição**: Sem documentação.

### `run_test()`
- **Linha**: 18
- **Descrição**: Sem documentação.

## Módulo: `./scripts/benchmark.py`

### `do_request(method, path, data)`
- **Linha**: 16
- **Descrição**: Sem documentação.

### `stats(times)`
- **Linha**: 34
- **Descrição**: Sem documentação.

### `run_sequential(name, iterations, func)`
- **Linha**: 46
- **Descrição**: Sem documentação.

### `run_concurrent(name, workers, requests_per_worker, func)`
- **Linha**: 58
- **Descrição**: Sem documentação.

### `classify(p95)`
- **Linha**: 88
- **Descrição**: Sem documentação.

### `main()`
- **Linha**: 94
- **Descrição**: Sem documentação.

### `worker()`
- **Linha**: 63
- **Descrição**: Sem documentação.

### `write_credor()`
- **Linha**: 126
- **Descrição**: Sem documentação.

### `delete_credor()`
- **Linha**: 138
- **Descrição**: Sem documentação.

## Módulo: `./scripts/exportar_dados.py`

### `main()`
- **Linha**: 26
- **Descrição**: Sem documentação.

## Módulo: `./server.py`

### `_setup_startup_logger()`
- **Linha**: 62
- **Descrição**: Sem documentação.

### `_log_startup(message, level)`
- **Linha**: 112
- **Descrição**: Sem documentação.

### `_term_enabled()`
- **Linha**: 141
- **Descrição**: Sem documentação.

### `_color(text, name)`
- **Linha**: 145
- **Descrição**: Sem documentação.

### `_fmt_bytes(num)`
- **Linha**: 151
- **Descrição**: Sem documentação.

### `_terminal_log(kind, message, color_name)`
- **Linha**: 159
- **Descrição**: Sem documentação.

### `_terminal_request_line(method, path, status_code, elapsed_ms, client_ip)`
- **Linha**: 164
- **Descrição**: Sem documentação.

### `_terminal_section(title)`
- **Linha**: 182
- **Descrição**: Sem documentação.

### `create_app()`
- **Linha**: 188
- **Descrição**: Sem documentação.

### `get_db()`
- **Linha**: 230
- **Descrição**: Sem documentação.

### `_get_db_for_g()`
- **Linha**: 245
- **Descrição**: Sem documentação.

### `close_db(exception)`
- **Linha**: 249
- **Descrição**: Sem documentação.

### `ensure_db_indexes(cur)`
- **Linha**: 258
- **Descrição**: Sem documentação.

### `migrate_db()`
- **Linha**: 320
- **Descrição**: Sem documentação.

### `init_db()`
- **Linha**: 553
- **Descrição**: Sem documentação.

### `_seed_from_data_js(cur)`
- **Linha**: 694
- **Descrição**: Sem documentação.

### `mark_request_start()`
- **Linha**: 727
- **Descrição**: Sem documentação.

### `require_api_auth()`
- **Linha**: 752
- **Descrição**: Sem documentação.

### `add_security_headers(response)`
- **Linha**: 777
- **Descrição**: Sem documentação.

### `compress_response(response)`
- **Linha**: 791
- **Descrição**: Sem documentação.

### `_url_to_static_path(url)`
- **Linha**: 879
- **Descrição**: Sem documentação.

### `_refresh_cached_file(url)`
- **Linha**: 885
- **Descrição**: Sem documentação.

### `_refresh_debug_cached_file(url)`
- **Linha**: 909
- **Descrição**: Sem documentação.

### `_preload_static_files()`
- **Linha**: 922
- **Descrição**: Sem documentação.

### `_serve_cached(url, cache_control)`
- **Linha**: 968
- **Descrição**: Sem documentação.

### `favicon()`
- **Linha**: 1005
- **Descrição**: Sem documentação.

### `index()`
- **Linha**: 1009
- **Descrição**: Sem documentação.

### `static_cached(filename)`
- **Linha**: 1018
- **Descrição**: Sem documentação.

### `static_files(filename)`
- **Linha**: 1035
- **Descrição**: Sem documentação.

### `not_found(e)`
- **Linha**: 1053
- **Descrição**: Sem documentação.

### `handle_exception(e)`
- **Linha**: 1059
- **Descrição**: Sem documentação.

### `check_env(var)`
- **Linha**: 97
- **Descrição**: Sem documentação.

### `migrate_table_foreign_keys(table_name, create_sql, check_key_column, expected_on_delete)`
- **Linha**: 355
- **Descrição**: Sem documentação.

## Módulo: `./services/ai_prompts.py`

### `PromptTemplate.__init__(self, system_template, user_template)`
- **Linha**: 14
- **Descrição**: Sem documentação.

### `PromptTemplate.render(self)`
- **Linha**: 18
- **Descrição**: Sem documentação.

### `render_response_style(style)`
- **Linha**: 214
- **Descrição**: Sem documentação.

### `build_prompt(template_name)`
- **Linha**: 223
- **Descrição**: Sem documentação.

### `limit_text(text, max_chars)`
- **Linha**: 228
- **Descrição**: Sem documentação.

### `_safe_variables(variables)`
- **Linha**: 235
- **Descrição**: Sem documentação.

### `__init__(self, system_template, user_template)`
- **Linha**: 14
- **Descrição**: Sem documentação.

### `render(self)`
- **Linha**: 18
- **Descrição**: Sem documentação.

## Módulo: `./services/ai_tasks.py`

### `AITaskFacade.__init__(self, service)`
- **Linha**: 24
- **Descrição**: Sem documentação.

### `AITaskFacade.template_map(self)`
- **Linha**: 28
- **Descrição**: Sem documentação.

### `AITaskFacade.gerar_texto_empenho(self, dados, acao)`
- **Linha**: 37
- **Descrição**: Sem documentação.

### `AITaskFacade._handle_suggest_options(self, dados)`
- **Linha**: 99
- **Descrição**: Call AI to suggest options for missing fields.

### `AITaskFacade._ctx_lines_for_suggestions(self, dados, missing_fields)`
- **Linha**: 135
- **Descrição**: Build context for suggest_options, focusing on what's missing.

### `AITaskFacade.revisar_empenho(self, dados)`
- **Linha**: 166
- **Descrição**: Sem documentação.

### `AITaskFacade.analisar_documento(self, texto, use_cache)`
- **Linha**: 198
- **Descrição**: Sem documentação.

### `AITaskFacade.categorizar_extrato(self, texto, use_cache)`
- **Linha**: 222
- **Descrição**: Sem documentação.

### `AITaskFacade.classificar_despesa(self, item, use_cache, web_context)`
- **Linha**: 246
- **Descrição**: Sem documentação.

### `AITaskFacade._validate_classificacao(self, item, result)`
- **Linha**: 275
- **Descrição**: Validacao e normalizacao pos-processamento.

### `AITaskFacade._normalize_fields(self, result)`
- **Linha**: 355
- **Descrição**: Normaliza campos que a IA pode ter trocado.

### `AITaskFacade.sugerir_nome_arquivo(self, nome_arquivo, texto, use_cache)`
- **Linha**: 388
- **Descrição**: Sem documentação.

### `AITaskFacade._ctx_lines(self, info)`
- **Linha**: 416
- **Descrição**: Sem documentação.

### `serialize_task_result(result)`
- **Linha**: 448
- **Descrição**: Sem documentação.

### `__init__(self, service)`
- **Linha**: 24
- **Descrição**: Sem documentação.

### `template_map(self)`
- **Linha**: 28
- **Descrição**: Sem documentação.

### `gerar_texto_empenho(self, dados, acao)`
- **Linha**: 37
- **Descrição**: Sem documentação.

### `_handle_suggest_options(self, dados)`
- **Linha**: 99
- **Descrição**: Call AI to suggest options for missing fields.

### `_ctx_lines_for_suggestions(self, dados, missing_fields)`
- **Linha**: 135
- **Descrição**: Build context for suggest_options, focusing on what's missing.

### `revisar_empenho(self, dados)`
- **Linha**: 166
- **Descrição**: Sem documentação.

### `analisar_documento(self, texto, use_cache)`
- **Linha**: 198
- **Descrição**: Sem documentação.

### `categorizar_extrato(self, texto, use_cache)`
- **Linha**: 222
- **Descrição**: Sem documentação.

### `classificar_despesa(self, item, use_cache, web_context)`
- **Linha**: 246
- **Descrição**: Sem documentação.

### `_validate_classificacao(self, item, result)`
- **Linha**: 275
- **Descrição**: Validacao e normalizacao pos-processamento.

### `_normalize_fields(self, result)`
- **Linha**: 355
- **Descrição**: Normaliza campos que a IA pode ter trocado.

### `sugerir_nome_arquivo(self, nome_arquivo, texto, use_cache)`
- **Linha**: 388
- **Descrição**: Sem documentação.

### `_ctx_lines(self, info)`
- **Linha**: 416
- **Descrição**: Sem documentação.

### `clean(value)`
- **Linha**: 137
- **Descrição**: Sem documentação.

### `clean(value)`
- **Linha**: 417
- **Descrição**: Sem documentação.

## Módulo: `./services/empenhos_service.py`

### `listar_empenhos_mes(conn, ano, mes, row_to_dict)`
- **Linha**: 1
- **Descrição**: Sem documentação.

### `persistir_empenho(conn, credor_id, ano, mes, now_str)`
- **Linha**: 9
- **Descrição**: Sem documentação.

### `listar_historico_credor(conn, cid, meses, now_struct)`
- **Linha**: 39
- **Descrição**: Sem documentação.

## Módulo: `./services/extratos_service.py`

### `adaptar_resultado(resultado)`
- **Linha**: 9
- **Descrição**: Sem documentação.

### `validar_origem_destino(origem, destino)`
- **Linha**: 31
- **Descrição**: Sem documentação.

### `coletar_arquivos(origem)`
- **Linha**: 43
- **Descrição**: Sem documentação.

### `processar_extratos(origem, destino, usar_ia, api_key_ia, modelo_ia, modo_teste)`
- **Linha**: 51
- **Descrição**: Sem documentação.

### `listar_subpastas(caminho)`
- **Linha**: 73
- **Descrição**: Sem documentação.

## Módulo: `./services/openrouter_service.py`

### `AIServiceError.__init__(self, message)`
- **Linha**: 21
- **Descrição**: Sem documentação.

### `AIServiceError.to_response(self)`
- **Linha**: 29
- **Descrição**: Sem documentação.

### `TTLCache.__init__(self, ttl_seconds, max_entries)`
- **Linha**: 53
- **Descrição**: Sem documentação.

### `TTLCache.get(self, key)`
- **Linha**: 59
- **Descrição**: Sem documentação.

### `TTLCache.set(self, key, value)`
- **Linha**: 71
- **Descrição**: Sem documentação.

### `OpenRouterService.__init__(self, api_key, default_model, referer, title, logger, timeout_seconds, max_retries, backoff_base, cache_ttl_seconds, default_headers, model_policies)`
- **Linha**: 83
- **Descrição**: Sem documentação.

### `OpenRouterService.chat_by_task(self, task_type, messages)`
- **Linha**: 96
- **Descrição**: Sem documentação.

### `OpenRouterService.chat_completion(self)`
- **Linha**: 106
- **Descrição**: Sem documentação.

### `OpenRouterService.list_models(self)`
- **Linha**: 144
- **Descrição**: Sem documentação.

### `OpenRouterService._call_model(self)`
- **Linha**: 157
- **Descrição**: Sem documentação.

### `OpenRouterService._build_model_chain(self, policy)`
- **Linha**: 196
- **Descrição**: Sem documentação.

### `OpenRouterService._is_model_rate_limited(self, model)`
- **Linha**: 205
- **Descrição**: Sem documentação.

### `OpenRouterService._seconds_until_model_released(self, model)`
- **Linha**: 214
- **Descrição**: Sem documentação.

### `OpenRouterService._mark_model_rate_limited(self, model, exc)`
- **Linha**: 220
- **Descrição**: Sem documentação.

### `OpenRouterService._truncate_messages(self, messages, max_chars)`
- **Linha**: 225
- **Descrição**: Sem documentação.

### `OpenRouterService._build_headers(self)`
- **Linha**: 234
- **Descrição**: Sem documentação.

### `OpenRouterService._validate_api_key(self)`
- **Linha**: 239
- **Descrição**: Sem documentação.

### `OpenRouterService._endpoint_for_model(self, model)`
- **Linha**: 244
- **Descrição**: Sem documentação.

### `OpenRouterService._build_cache_key(self, messages, models, temperature, max_tokens, extra_payload)`
- **Linha**: 247
- **Descrição**: Sem documentação.

### `OpenRouterService._safe_log_payload(self, payload)`
- **Linha**: 251
- **Descrição**: Sem documentação.

### `OpenRouterService._sleep_before_retry(self, attempt, retry_after)`
- **Linha**: 256
- **Descrição**: Sem documentação.

### `OpenRouterService._translate_http_error(self, response)`
- **Linha**: 265
- **Descrição**: Sem documentação.

### `OpenRouterService._translate_request_exception(self, exc)`
- **Linha**: 282
- **Descrição**: Sem documentação.

### `OpenRouterService._collapse_errors(self, errors)`
- **Linha**: 285
- **Descrição**: Sem documentação.

### `OpenRouterService._extract_retry_after_seconds(self, exc)`
- **Linha**: 294
- **Descrição**: Sem documentação.

### `OpenRouterService._extract_retry_after_seconds_from_message(self, message, retry_after)`
- **Linha**: 304
- **Descrição**: Sem documentação.

### `build_default_model_policies(default_model)`
- **Linha**: 325
- **Descrição**: Sem documentação.

### `build_openrouter_service()`
- **Linha**: 339
- **Descrição**: Sem documentação.

### `listar_modelos(api_key, timeout_seconds, referer, title)`
- **Linha**: 343
- **Descrição**: Sem documentação.

### `chat_completion(api_key, model, messages, max_tokens, temperature, referer, title)`
- **Linha**: 347
- **Descrição**: Sem documentação.

### `is_opencode_go_model(model)`
- **Linha**: 353
- **Descrição**: Sem documentação.

### `normalize_provider_model(model)`
- **Linha**: 357
- **Descrição**: Sem documentação.

### `parse_http_error(error)`
- **Linha**: 364
- **Descrição**: Sem documentação.

### `parse_http_error_response(response)`
- **Linha**: 381
- **Descrição**: Sem documentação.

### `extract_openrouter_text(payload)`
- **Linha**: 391
- **Descrição**: Sem documentação.

### `extract_json_block(text)`
- **Linha**: 409
- **Descrição**: Sem documentação.

### `extract_usage(payload)`
- **Linha**: 433
- **Descrição**: Sem documentação.

### `__init__(self, message)`
- **Linha**: 21
- **Descrição**: Sem documentação.

### `to_response(self)`
- **Linha**: 29
- **Descrição**: Sem documentação.

### `__init__(self, ttl_seconds, max_entries)`
- **Linha**: 53
- **Descrição**: Sem documentação.

### `get(self, key)`
- **Linha**: 59
- **Descrição**: Sem documentação.

### `set(self, key, value)`
- **Linha**: 71
- **Descrição**: Sem documentação.

### `__init__(self, api_key, default_model, referer, title, logger, timeout_seconds, max_retries, backoff_base, cache_ttl_seconds, default_headers, model_policies)`
- **Linha**: 83
- **Descrição**: Sem documentação.

### `chat_by_task(self, task_type, messages)`
- **Linha**: 96
- **Descrição**: Sem documentação.

### `chat_completion(self)`
- **Linha**: 106
- **Descrição**: Sem documentação.

### `list_models(self)`
- **Linha**: 144
- **Descrição**: Sem documentação.

### `_call_model(self)`
- **Linha**: 157
- **Descrição**: Sem documentação.

### `_build_model_chain(self, policy)`
- **Linha**: 196
- **Descrição**: Sem documentação.

### `_is_model_rate_limited(self, model)`
- **Linha**: 205
- **Descrição**: Sem documentação.

### `_seconds_until_model_released(self, model)`
- **Linha**: 214
- **Descrição**: Sem documentação.

### `_mark_model_rate_limited(self, model, exc)`
- **Linha**: 220
- **Descrição**: Sem documentação.

### `_truncate_messages(self, messages, max_chars)`
- **Linha**: 225
- **Descrição**: Sem documentação.

### `_build_headers(self)`
- **Linha**: 234
- **Descrição**: Sem documentação.

### `_validate_api_key(self)`
- **Linha**: 239
- **Descrição**: Sem documentação.

### `_endpoint_for_model(self, model)`
- **Linha**: 244
- **Descrição**: Sem documentação.

### `_build_cache_key(self, messages, models, temperature, max_tokens, extra_payload)`
- **Linha**: 247
- **Descrição**: Sem documentação.

### `_safe_log_payload(self, payload)`
- **Linha**: 251
- **Descrição**: Sem documentação.

### `_sleep_before_retry(self, attempt, retry_after)`
- **Linha**: 256
- **Descrição**: Sem documentação.

### `_translate_http_error(self, response)`
- **Linha**: 265
- **Descrição**: Sem documentação.

### `_translate_request_exception(self, exc)`
- **Linha**: 282
- **Descrição**: Sem documentação.

### `_collapse_errors(self, errors)`
- **Linha**: 285
- **Descrição**: Sem documentação.

### `_extract_retry_after_seconds(self, exc)`
- **Linha**: 294
- **Descrição**: Sem documentação.

### `_extract_retry_after_seconds_from_message(self, message, retry_after)`
- **Linha**: 304
- **Descrição**: Sem documentação.

## Módulo: `./services/tavily_service.py`

### `TavilyError.__init__(self, message, status_code)`
- **Linha**: 12
- **Descrição**: Sem documentação.

### `TavilyService.__init__(self, api_key, logger, timeout)`
- **Linha**: 31
- **Descrição**: Sem documentação.

### `TavilyService.search(self, query, max_results, search_depth, include_domains, exclude_domains)`
- **Linha**: 41
- **Descrição**: Executa busca web e retorna resultados formatados.

### `TavilyService.search_as_context(self, query, max_results)`
- **Linha**: 120
- **Descrição**: Busca e retorna texto consolidado para usar como contexto da IA.

### `TavilyService._extract_error(self, resp)`
- **Linha**: 138
- **Descrição**: Sem documentação.

### `build_tavily_service(api_key, logger)`
- **Linha**: 146
- **Descrição**: Sem documentação.

### `__init__(self, message, status_code)`
- **Linha**: 12
- **Descrição**: Sem documentação.

### `__init__(self, api_key, logger, timeout)`
- **Linha**: 31
- **Descrição**: Sem documentação.

### `search(self, query, max_results, search_depth, include_domains, exclude_domains)`
- **Linha**: 41
- **Descrição**: Executa busca web e retorna resultados formatados.

### `search_as_context(self, query, max_results)`
- **Linha**: 120
- **Descrição**: Busca e retorna texto consolidado para usar como contexto da IA.

### `_extract_error(self, resp)`
- **Linha**: 138
- **Descrição**: Sem documentação.

## Módulo: `./src/analyzers/detectors.py`

### `parse_date(d)`
- **Linha**: 19
- **Descrição**: Converte string, datetime ou timestamp para datetime aware (UTC).

### `days_between(a, b)`
- **Linha**: 46
- **Descrição**: Calcula a diferença em dias entre duas datas.

### `fmt_brl(v)`
- **Linha**: 52
- **Descrição**: Formata valor como moeda brasileira (ex: 1.234,56).

### `mk_alert(severity, category, icon, title, description, evidence, related_ids)`
- **Linha**: 56
- **Descrição**: Cria um dicionário padronizado para alertas.

### `is_aplic(t)`
- **Linha**: 70
- **Descrição**: Sem documentação.

### `is_resgate(t)`
- **Linha**: 73
- **Descrição**: Sem documentação.

### `tx_category(t)`
- **Linha**: 76
- **Descrição**: Sem documentação.

### `dedup_window(t)`
- **Linha**: 92
- **Descrição**: Sem documentação.

### `extract_pix_time(memo)`
- **Linha**: 100
- **Descrição**: Sem documentação.

### `normalize_beneficiary(memo)`
- **Linha**: 117
- **Descrição**: Sem documentação.

### `beneficiary_key(memo)`
- **Linha**: 162
- **Descrição**: Sem documentação.

### `tx_month(t)`
- **Linha**: 165
- **Descrição**: Sem documentação.

### `mean_std(values)`
- **Linha**: 169
- **Descrição**: Sem documentação.

### `z_score(value, mean, std)`
- **Linha**: 176
- **Descrição**: Sem documentação.

### `levenshtein(a, b)`
- **Linha**: 179
- **Descrição**: Sem documentação.

### `memo_similarity(a, b)`
- **Linha**: 192
- **Descrição**: Sem documentação.

### `keywords(memo)`
- **Linha**: 208
- **Descrição**: Sem documentação.

### `easter_date(year)`
- **Linha**: 214
- **Descrição**: Sem documentação.

### `brazilian_holidays(year)`
- **Linha**: 233
- **Descrição**: Sem documentação.

### `national_holiday_name(dt_val)`
- **Linha**: 260
- **Descrição**: Sem documentação.

### `detect_duplicates(txns, flagged)`
- **Linha**: 267
- **Descrição**: Sem documentação.

### `detect_returned_transfers(txns, flagged)`
- **Linha**: 309
- **Descrição**: Sem documentação.

### `adaptive_z_threshold(sample_size, cv)`
- **Linha**: 360
- **Descrição**: Sem documentação.

### `detect_atypical(txns, flagged)`
- **Linha**: 370
- **Descrição**: Sem documentação.

### `detect_unapplied_funds(txns, flagged)`
- **Linha**: 414
- **Descrição**: Sem documentação.

### `detect_unusual_rescues(txns, investments, flagged)`
- **Linha**: 461
- **Descrição**: Sem documentação.

### `detect_batch_pix(txns, flagged)`
- **Linha**: 486
- **Descrição**: Sem documentação.

### `detect_ofx_vs_txt_mismatch(txns, investments, flagged)`
- **Linha**: 514
- **Descrição**: Sem documentação.

### `detect_round_amounts(txns, flagged)`
- **Linha**: 567
- **Descrição**: Sem documentação.

### `detect_missing_fnas_month(txns, flagged)`
- **Linha**: 626
- **Descrição**: Sem documentação.

### `detect_alternating_beneficiary(txns, flagged)`
- **Linha**: 702
- **Descrição**: Sem documentação.

### `detect_smurfing(txns, flagged)`
- **Linha**: 735
- **Descrição**: Sem documentação.

### `detect_cash_remnants(txns, investments, flagged)`
- **Linha**: 800
- **Descrição**: Sem documentação.

### `detect_new_high_value_beneficiary(txns, flagged)`
- **Linha**: 840
- **Descrição**: Sem documentação.

### `detect_interrupted_recurring(txns, flagged)`
- **Linha**: 877
- **Descrição**: Sem documentação.

### `detect_circular_transfers(txns, flagged)`
- **Linha**: 931
- **Descrição**: Sem documentação.

### `detect_bank_fee_anomaly(txns, flagged)`
- **Linha**: 986
- **Descrição**: Sem documentação.

### `detect_after_hours_payments(txns, flagged)`
- **Linha**: 1019
- **Descrição**: Sem documentação.

### `detect_ofx_gaps(txns, flagged)`
- **Linha**: 1054
- **Descrição**: Sem documentação.

### `detect_benford_deviation(txns, flagged)`
- **Linha**: 1088
- **Descrição**: Sem documentação.

### `detect_weekend_payments(txns, flagged)`
- **Linha**: 1147
- **Descrição**: Sem documentação.

### `detect_holiday_payments(txns, flagged)`
- **Linha**: 1179
- **Descrição**: Sem documentação.

### `detect_threshold_skirting(txns, flagged)`
- **Linha**: 1206
- **Descrição**: Sem documentação.

### `detect_dormant_account_burst(txns, flagged)`
- **Linha**: 1234
- **Descrição**: Sem documentação.

### `detect_price_creep(txns, flagged)`
- **Linha**: 1288
- **Descrição**: Sem documentação.

### `detect_balance_mismatch(ofx_files)`
- **Linha**: 1356
- **Descrição**: Sem documentação.

### `detect_year_end_rush(txns, flagged)`
- **Linha**: 1410
- **Descrição**: Sem documentação.

### `detect_vendor_concentration(txns, flagged)`
- **Linha**: 1450
- **Descrição**: Sem documentação.

### `detect_rapid_debit_burst(txns, flagged)`
- **Linha**: 1533
- **Descrição**: Sem documentação.

### `detect_inverted_seasonality(txns, flagged)`
- **Linha**: 1607
- **Descrição**: Sem documentação.

### `detect_generic_beneficiary(txns, flagged)`
- **Linha**: 1673
- **Descrição**: Sem documentação.

### `correlate_alerts(alerts)`
- **Linha**: 1703
- **Descrição**: Sem documentação.

### `build_stats(transactions, investments, alerts, all_alerts)`
- **Linha**: 1768
- **Descrição**: Sem documentação.

### `run_analysis(transactions, investments, custom_config, ofx_files)`
- **Linha**: 1940
- **Descrição**: Sem documentação.

### `run_cross_account_analysis(account_results)`
- **Linha**: 1999
- **Descrição**: Sem documentação.

### `mmdd(dt)`
- **Linha**: 249
- **Descrição**: Sem documentação.

### `parse_period(p)`
- **Linha**: 630
- **Descrição**: Sem documentação.

### `get_date(f, key)`
- **Linha**: 1361
- **Descrição**: Sem documentação.

### `parse_period(p)`
- **Linha**: 1780
- **Descrição**: Sem documentação.

### `parse_dmy(d)`
- **Linha**: 1832
- **Descrição**: Sem documentação.

### `alert_recency_weight(alert)`
- **Linha**: 1855
- **Descrição**: Sem documentação.

### `get_day_diff(str_a, str_b)`
- **Linha**: 2009
- **Descrição**: Sem documentação.

### `get_p50(amounts)`
- **Linha**: 2090
- **Descrição**: Sem documentação.

### `sort_key(a)`
- **Linha**: 1746
- **Descrição**: Sem documentação.

## Módulo: `./src/analyzers/search.py`

### `to_iso_date(v)`
- **Linha**: 8
- **Descrição**: Sem documentação.

### `date_only(iso_str)`
- **Linha**: 19
- **Descrição**: Sem documentação.

### `build_summary(results)`
- **Linha**: 24
- **Descrição**: Sem documentação.

### `search_transactions(filters)`
- **Linha**: 55
- **Descrição**: Sem documentação.

### `search_debits(filters)`
- **Linha**: 212
- **Descrição**: Sem documentação.

### `search_credits(filters)`
- **Linha**: 217
- **Descrição**: Sem documentação.

### `find_by_amount(amount, tolerance, extra_filters)`
- **Linha**: 222
- **Descrição**: Sem documentação.

### `find_by_date_range(date_from, date_to, extra_filters)`
- **Linha**: 228
- **Descrição**: Sem documentação.

## Módulo: `./src/exporters/report_exporter.py`

### `fmt_brl(v)`
- **Linha**: 20
- **Descrição**: Sem documentação.

### `fmt_brl_signed(v)`
- **Linha**: 23
- **Descrição**: Sem documentação.

### `build_excel(transactions, investments, alerts, stats)`
- **Linha**: 30
- **Descrição**: Sem documentação.

### `NumberedCanvas.__init__(self)`
- **Linha**: 161
- **Descrição**: Sem documentação.

### `NumberedCanvas.showPage(self)`
- **Linha**: 165
- **Descrição**: Sem documentação.

### `NumberedCanvas.save(self)`
- **Linha**: 169
- **Descrição**: Sem documentação.

### `NumberedCanvas.draw_page_number(self, page_count)`
- **Linha**: 177
- **Descrição**: Sem documentação.

### `build_pdf(transactions, investments, alerts, stats, account)`
- **Linha**: 185
- **Descrição**: Sem documentação.

### `generate_csv_transactions(transactions)`
- **Linha**: 458
- **Descrição**: Sem documentação.

### `__init__(self)`
- **Linha**: 161
- **Descrição**: Sem documentação.

### `showPage(self)`
- **Linha**: 165
- **Descrição**: Sem documentação.

### `save(self)`
- **Linha**: 169
- **Descrição**: Sem documentação.

### `draw_page_number(self, page_count)`
- **Linha**: 177
- **Descrição**: Sem documentação.

## Módulo: `./src/parsers/ofx_parser.py`

### `_extract_tag(text, tag)`
- **Linha**: 34
- **Descrição**: Extrai o valor de uma tag OFX simples (equivalente a extractTag do JS).

### `_parse_ofx_date(s)`
- **Linha**: 40
- **Descrição**: Converte data OFX (YYYYMMDD ou YYYYMMDDHHMMSS[.mmm][+TZ]) em datetime UTC.
Equivalente a parseOFXDate do JS.

### `_period_from_ofx_date(s)`
- **Linha**: 55
- **Descrição**: Converte data OFX em string de período MM/YYYY.

### `_format_date(d)`
- **Linha**: 62
- **Descrição**: Formata datetime em DD/MM/YYYY (equivalente a formatDate do JS).

### `_clean_memo(s)`
- **Linha**: 67
- **Descrição**: Remove caracteres de controle e normaliza espaços no memo.

### `_extract_file_period(filename)`
- **Linha**: 74
- **Descrição**: Extrai período MM/YYYY do nome do arquivo (ex: '01-2025.ofx' → '01/2025').

### `_calculate_median_period(text)`
- **Linha**: 80
- **Descrição**: Calcula o período mediano das datas de transação no bloco OFX.

### `_detect_bank_profile(raw)`
- **Linha**: 95
- **Descrição**: Detecta banco pelo BANKID e determina encoding correto.
Equivalente a detectBankProfile do JS.

### `_extract_stmt_blocks(text)`
- **Linha**: 123
- **Descrição**: Extrai blocos <STMTRS>...</STMTRS> do documento OFX.
Equivalente a extractStmtBlocks do JS.

### `_parse_transactions(text, period, filename, acct_id, seq_offset)`
- **Linha**: 131
- **Descrição**: Extrai todas as transações de um bloco OFX.
Equivalente a parseTransactions do JS — preserva a mesma estrutura de campos.

### `_parse_single_block(text, filename, file_period, seq_offset, bank_profile)`
- **Linha**: 190
- **Descrição**: Parseia um único bloco STMTRS.
Equivalente a parseSingleBlock do JS.

### `parse_ofx(buffer, filename)`
- **Linha**: 232
- **Descrição**: Parseia um arquivo OFX e retorna estrutura de dados padrão.

Suporta:
  - Arquivo com único bloco STMTRS
  - Arquivo com múltiplos blocos STMTRS (multi-conta)
  - Encoding automático (windows-1252 / utf-8)

Retorna:
  {
    filename, period, account, accounts, multiAccount,
    bankId, bankName, currency, dateStart, dateEnd,
    ledgerBalance, ledgerBalanceDate, transactions
  }

### `get(tag)`
- **Linha**: 143
- **Descrição**: Sem documentação.

## Módulo: `./src/parsers/txt_parser.py`

### `_extract_brl_number(line)`
- **Linha**: 42
- **Descrição**: Extrai o primeiro número no formato BRL (1.234,56) de uma linha.
Equivalente a extractBRLNumber do JS.

### `_extract_decimal(line)`
- **Linha**: 53
- **Descrição**: Extrai decimal com vírgula ou ponto (ex: rentabilidade 1,23%).
Equivalente a extractDecimal do JS.

### `_normalize_period(period)`
- **Linha**: 64
- **Descrição**: Converte período textual em chave sortável YYYY-MM.
Ex: "JANEIRO/2025" → "2025-01", "MARÇO/2024" → "2024-03"
Equivalente a normalizePeriod do JS.

### `parse_txt(buffer, filename)`
- **Linha**: 83
- **Descrição**: Parseia um arquivo TXT de extrato de aplicação financeira Banco do Brasil.

Retorna None se o arquivo não for reconhecido como extrato de investimento
(ausência do campo 'Mês/ano referência').

Retorna estrutura:
{
  filename, period, periodSort, account, fund, cnpjFund,
  items, summary, rentability, quotaValues
}

Equivalente a parseTXT do Node.js.

## Módulo: `./tests/test_app_structure.py`

### `_safe_print(message)`
- **Linha**: 18
- **Descrição**: Sem documentação.

### `test_imports()`
- **Linha**: 24
- **Descrição**: Testa todos os imports ativos (server.py + routes/).

### `test_helpers()`
- **Linha**: 65
- **Descrição**: Testa funcoes auxiliares de routes/helpers.py e routes/documentos.py.

### `test_app_factory()`
- **Linha**: 113
- **Descrição**: Testa criacao do app e registro de blueprints.

### `test_db_connection()`
- **Linha**: 149
- **Descrição**: Testa conexao com banco de dados usando banco temporario isolado.

### `test_mural_api_guards()`
- **Linha**: 218
- **Descrição**: Testa protecao e validacao basica das rotas do mural.

### `test_protocolos_api()`
- **Linha**: 271
- **Descrição**: Testa cadastro de protocolos, upload de anexos (PDFs) e download.

### `test_fornecimento_solicitacoes_api()`
- **Linha**: 370
- **Descrição**: Testa cadastro, listagem, edicao, clonagem e exclusao de solicitacoes de fornecimento.

### `test_empenho_assistente_historico_guard()`
- **Linha**: 481
- **Descrição**: Testa se o endpoint de histórico de empenho-assistente exige login.

### `run_all_tests()`
- **Linha**: 515
- **Descrição**: Executa todos os testes (uso direto: python tests/test_app_structure.py).

### `load_tests(loader, tests, pattern)`
- **Linha**: 570
- **Descrição**: Sem documentação.

# Funções JavaScript (Frontend)

## Módulo: `./static/js/ai-cache.js`

### `constructor(maxSize = 50, ttl = 3600000)`
- **Linha**: 5
- **Tipo**: Method

### `generateKey(prompt, model)`
- **Linha**: 11
- **Tipo**: Method

### `hashString(str)`
- **Linha**: 15
- **Tipo**: Method

### `get(prompt, model)`
- **Linha**: 25
- **Tipo**: Method

### `set(prompt, model, response)`
- **Linha**: 40
- **Tipo**: Method

### `clear()`
- **Linha**: 55
- **Tipo**: Method

### `getStats()`
- **Linha**: 59
- **Tipo**: Method

## Módulo: `./static/js/app.js`

### `invalidateFilterCache()`
- **Linha**: 44
- **Tipo**: Function declaration

### `getFilterCacheKey()`
- **Linha**: 49
- **Tipo**: Function declaration

### `apiGet(path, { cache = false } = {})`
- **Linha**: 65
- **Tipo**: Function declaration

### `apiCacheInvalidate(prefix)`
- **Linha**: 80
- **Tipo**: Function declaration

### `apiPost(path, body)`
- **Linha**: 86
- **Tipo**: Function declaration

### `apiPut(path, body)`
- **Linha**: 99
- **Tipo**: Function declaration

### `apiDelete(path)`
- **Linha**: 112
- **Tipo**: Function declaration

### `shouldRequestSummary()`
- **Linha**: 121
- **Tipo**: Function declaration

### `ensureBrasaoB64()`
- **Linha**: 129
- **Tipo**: Function declaration

### `buildCredoresQueryParams({ page = state.page, limit = CREDORES_PAGE_SIZE, includeSummary = false } = {})`
- **Linha**: 155
- **Tipo**: Function declaration

### `loadCredores()`
- **Linha**: 178
- **Tipo**: Function declaration

### `loadAllCredoresForCurrentFilters()`
- **Linha**: 203
- **Tipo**: Function declaration

### `loadMonth()`
- **Linha**: 226
- **Tipo**: Function declaration

### `formatBRL(value)`
- **Linha**: 244
- **Tipo**: Function declaration

### `render()`
- **Linha**: 253
- **Tipo**: Function declaration

### `autosaveGeneratedText(text, options)`
- **Linha**: 265
- **Tipo**: Function declaration

### `ensureMainAppLoaded()`
- **Linha**: 274
- **Tipo**: Function declaration

### `downloadGeneratedBlob(blob, fileName)`
- **Linha**: 300
- **Tipo**: Function declaration

### `renderMonthNav()`
- **Linha**: 313
- **Tipo**: Function declaration

### `filteredCredores()`
- **Linha**: 318
- **Tipo**: Function declaration

### `renderCards()`
- **Linha**: 322
- **Tipo**: Function declaration

### `buildCard(c, done, idx)`
- **Linha**: 344
- **Tipo**: Function declaration

### `copyCredorName(nome, el)`
- **Linha**: 428
- **Tipo**: Function declaration

### `feedbackCopy()`
- **Linha**: 429
- **Tipo**: Arrow function

### `fallbackCopy()`
- **Linha**: 437
- **Tipo**: Arrow function

### `handleCardExpand(cardEl, credorId)`
- **Linha**: 456
- **Tipo**: Function declaration

### `renderStats()`
- **Linha**: 472
- **Tipo**: Function declaration

### `_setStat(id, value, isCurrency)`
- **Linha**: 487
- **Tipo**: Function declaration

### `renderPagination()`
- **Linha**: 556
- **Tipo**: Function declaration

### `_printCSS()`
- **Linha**: 574
- **Tipo**: Function declaration

### `_buildDocPage(c, mesNome, ano, isLast)`
- **Linha**: 785
- **Tipo**: Function declaration

### `exportCSV()`
- **Linha**: 873
- **Tipo**: Function declaration

### `batchEmpenhar()`
- **Linha**: 904
- **Tipo**: Function declaration

### `printCredor(c)`
- **Linha**: 928
- **Tipo**: Function declaration

### `check()`
- **Linha**: 947
- **Tipo**: Function expression

### `downloadPDFCredor(c)`
- **Linha**: 972
- **Tipo**: Function declaration

### `printLote()`
- **Linha**: 1021
- **Tipo**: Function declaration

### `check()`
- **Linha**: 1046
- **Tipo**: Function expression

### `downloadPDFLote()`
- **Linha**: 1071
- **Tipo**: Function declaration

### `onToggle(id, nome)`
- **Linha**: 1126
- **Tipo**: Function declaration

### `getCurrentCredorName()`
- **Linha**: 1153
- **Tipo**: Function declaration

### `openDeleteConfirmModal(credorId = null)`
- **Linha**: 1167
- **Tipo**: Function declaration

### `closeDeleteConfirmModal()`
- **Linha**: 1182
- **Tipo**: Function declaration

### `openModal(id = null)`
- **Linha**: 1187
- **Tipo**: Function declaration

### `closeModal()`
- **Linha**: 1222
- **Tipo**: Function declaration

### `onFormSubmit(e)`
- **Linha**: 1228
- **Tipo**: Function declaration

### `onDeleteCredor(idVal = null)`
- **Linha**: 1295
- **Tipo**: Function declaration

### `duplicateCredor(c)`
- **Linha**: 1317
- **Tipo**: Function declaration

### `isValidCnpj(value)`
- **Linha**: 1337
- **Tipo**: Function declaration

### `setLoading(on)`
- **Linha**: 1356
- **Tipo**: Function declaration

### `showToast(msg, type = 'info')`
- **Linha**: 1362
- **Tipo**: Function declaration

### `attachEvents()`
- **Linha**: 1371
- **Tipo**: Function declaration

### `debouncedLoadCredores(delay = 300)`
- **Linha**: 1437
- **Tipo**: Function declaration

### `renderLogItem(log)`
- **Linha**: 1550
- **Tipo**: Function declaration

### `loadLogs(reset = true)`
- **Linha**: 1581
- **Tipo**: Function declaration

### `closeLixeira()`
- **Linha**: 1719
- **Tipo**: Function declaration

### `openLixeira()`
- **Linha**: 1724
- **Tipo**: Function declaration

### `loadLixeira()`
- **Linha**: 1731
- **Tipo**: Function declaration

### `restaurarCredor(id, btn)`
- **Linha**: 1772
- **Tipo**: Function declaration

### `init()`
- **Linha**: 1791
- **Tipo**: Function declaration

### `initTheme()`
- **Linha**: 1812
- **Tipo**: Function declaration

### `syncThemeLabel()`
- **Linha**: 1824
- **Tipo**: Function declaration

### `initCosmosEffects()`
- **Linha**: 1832
- **Tipo**: Function declaration

### `isCosmosTheme()`
- **Linha**: 1841
- **Tipo**: Function declaration

### `prefersReducedMotion()`
- **Linha**: 1845
- **Tipo**: Function declaration

### `clearTimer()`
- **Linha**: 1849
- **Tipo**: Function declaration

### `createComet()`
- **Linha**: 1856
- **Tipo**: Function declaration

### `scheduleNextComet()`
- **Linha**: 1882
- **Tipo**: Function declaration

### `syncCosmosEffects()`
- **Linha**: 1892
- **Tipo**: Function declaration

### `toggleTheme()`
- **Linha**: 1910
- **Tipo**: Function declaration

### `initAppDOM()`
- **Linha**: 1923
- **Tipo**: Function declaration

### `syncExtraThemeLabels()`
- **Linha**: 1933
- **Tipo**: Arrow function

### `syncThemeButtons()`
- **Linha**: 1951
- **Tipo**: Arrow function

### `openMobileNav()`
- **Linha**: 1999
- **Tipo**: Function declaration

### `closeMobileNav()`
- **Linha**: 2007
- **Tipo**: Function declaration

### `syncSidebarExpandBtn()`
- **Linha**: 2081
- **Tipo**: Function declaration

### `showAdmPanel()`
- **Linha**: 2175
- **Tipo**: Function declaration

### `hideAdmPanel()`
- **Linha**: 2183
- **Tipo**: Function declaration

### `setActiveTab(tabName)`
- **Linha**: 2192
- **Tipo**: Function declaration

### `handleTabClick(tabName, requiresAuth)`
- **Linha**: 2201
- **Tipo**: Function declaration

### `applyGlowingSearchBars()`
- **Linha**: 2285
- **Tipo**: Function declaration

### `initAvatarCheckBadges()`
- **Linha**: 2358
- **Tipo**: Function declaration

### `initSpotlightCards()`
- **Linha**: 2408
- **Tipo**: Function declaration

### `syncPointer(e)`
- **Linha**: 2409
- **Tipo**: Arrow function

## Módulo: `./static/js/assistente-empenho.js`

### `setBusy(isBusy)`
- **Linha**: 54
- **Tipo**: Function declaration

### `showError(message)`
- **Linha**: 62
- **Tipo**: Function declaration

### `showStatus(message)`
- **Linha**: 69
- **Tipo**: Function declaration

### `hideMessages()`
- **Linha**: 76
- **Tipo**: Function declaration

### `addFiles(filesList)`
- **Linha**: 83
- **Tipo**: Function declaration

### `removeFile(index)`
- **Linha**: 93
- **Tipo**: Function declaration

### `clearFiles()`
- **Linha**: 98
- **Tipo**: Function declaration

### `updateFilesUI()`
- **Linha**: 104
- **Tipo**: Function declaration

### `formatSize(size)`
- **Linha**: 121
- **Tipo**: Function declaration

### `payloadFromForm()`
- **Linha**: 128
- **Tipo**: Function declaration

### `renderExtraction(data)`
- **Linha**: 151
- **Tipo**: Function declaration

### `renderChecklist(data)`
- **Linha**: 184
- **Tipo**: Function declaration

### `renderDiff(diff, beforeText, afterText)`
- **Linha**: 199
- **Tipo**: Function declaration

### `renderHistory(items)`
- **Linha**: 223
- **Tipo**: Function declaration

### `hydrateFromHistory(item)`
- **Linha**: 260
- **Tipo**: Function declaration

### `loadHistory()`
- **Linha**: 278
- **Tipo**: Function declaration

### `extractTextFromFile(file)`
- **Linha**: 289
- **Tipo**: Function declaration

### `readCurrentFiles()`
- **Linha**: 324
- **Tipo**: Function declaration

### `ensureTextBase()`
- **Linha**: 345
- **Tipo**: Function declaration

### `callAssistant(action)`
- **Linha**: 350
- **Tipo**: Function declaration

## Módulo: `./static/js/despesa/historico.js`

### `escHtml(s)`
- **Linha**: 204
- **Tipo**: Function declaration

### `formatDate(dt)`
- **Linha**: 208
- **Tipo**: Function declaration

## Módulo: `./static/js/despesa/logic.js`

### `getAvailableOptions(excludeFilter = null)`
- **Linha**: 36
- **Tipo**: Function declaration

### `handleChipRemove(type, filter)`
- **Linha**: 126
- **Tipo**: Function declaration

### `escapeValue(value)`
- **Linha**: 364
- **Tipo**: Arrow function

## Módulo: `./static/js/despesa/main.js`

### `handleFile(file)`
- **Linha**: 14
- **Tipo**: Function declaration

### `cleanup()`
- **Linha**: 68
- **Tipo**: Arrow function

### `setViewMode(mode)`
- **Linha**: 122
- **Tipo**: Function declaration

### `updateAccordionDefaults()`
- **Linha**: 149
- **Tipo**: Function declaration

### `updatePeriodoAtivoLabel(importacao)`
- **Linha**: 168
- **Tipo**: Function declaration

### `autoLoadLatestImport()`
- **Linha**: 174
- **Tipo**: Function declaration

### `autoLoadCSV()`
- **Linha**: 195
- **Tipo**: Function declaration

## Módulo: `./static/js/despesa/ui.js`

### `showDetails(row)`
- **Linha**: 56
- **Tipo**: Function declaration

### `close()`
- **Linha**: 95
- **Tipo**: Arrow function

### `cleanup()`
- **Linha**: 119
- **Tipo**: Arrow function

### `escHandler(e)`
- **Linha**: 129
- **Tipo**: Function expression

### `addChip(label, type, filter)`
- **Linha**: 147
- **Tipo**: Arrow function

### `fieldRow(col)`
- **Linha**: 385
- **Tipo**: Function declaration

## Módulo: `./static/js/document-autosave.js`

### `saveBlob(blob, options = {})`
- **Linha**: 2
- **Tipo**: Function declaration

### `saveText(text, options = {})`
- **Linha**: 20
- **Tipo**: Function declaration

### `downloadBlob(blob, fileName)`
- **Linha**: 25
- **Tipo**: Function declaration

## Módulo: `./static/js/expertmoney-app.js`

### `scanLocalFolders()`
- **Linha**: 10
- **Tipo**: Function declaration

### `loadLocalFolder(folderName)`
- **Linha**: 46
- **Tipo**: Function declaration

### `runBatchAnalysis()`
- **Linha**: 73
- **Tipo**: Function declaration

### `scanLocalZips()`
- **Linha**: 108
- **Tipo**: Function declaration

### `loadLocalZip(filename)`
- **Linha**: 160
- **Tipo**: Function declaration

### `loadLatestSessionOnStart()`
- **Linha**: 196
- **Tipo**: Function declaration

### `toast(msg, type='info', dur=3500, action=null)`
- **Linha**: 260
- **Tipo**: Function declaration

### `setNav(el)`
- **Linha**: 279
- **Tipo**: Function declaration

### `handleDrop(e)`
- **Linha**: 298
- **Tipo**: Function declaration

### `handleFiles(files)`
- **Linha**: 304
- **Tipo**: Function declaration

### `renderFileList(files)`
- **Linha**: 335
- **Tipo**: Function declaration

### `runAnalysis()`
- **Linha**: 349
- **Tipo**: Function declaration

### `setSidebarAccountSort(mode)`
- **Linha**: 414
- **Tipo**: Function declaration

### `_sortAccounts(accounts, mode)`
- **Linha**: 419
- **Tipo**: Function declaration

### `filterSidebarAccounts(query)`
- **Linha**: 428
- **Tipo**: Function declaration

### `_renderSidebarMenu(menu, accounts, activeAccountId)`
- **Linha**: 438
- **Tipo**: Function declaration

### `updateActiveAccountsMenu(activeAccountId)`
- **Linha**: 458
- **Tipo**: Function declaration

### `renderFocusedAccountControl(account)`
- **Linha**: 479
- **Tipo**: Function declaration

### `handleAccountFocusChange(accountId, openNow = false)`
- **Linha**: 508
- **Tipo**: Function declaration

### `openFocusedAccount(selectId = 'account-focus-select')`
- **Linha**: 520
- **Tipo**: Function declaration

### `clearFocusedAccount()`
- **Linha**: 526
- **Tipo**: Function declaration

### `toggleAccountSwitcher(e)`
- **Linha**: 534
- **Tipo**: Function declaration

### `closeAccountSwitcher()`
- **Linha**: 548
- **Tipo**: Function declaration

### `filterSwitcherList(query)`
- **Linha**: 562
- **Tipo**: Function declaration

### `renderSwitcherList(accounts)`
- **Linha**: 570
- **Tipo**: Function declaration

### `renderHeaderAccountInfo(account)`
- **Linha**: 580
- **Tipo**: Function declaration

### `renderActiveContext()`
- **Linha**: 587
- **Tipo**: Function declaration

### `_highlightActiveAccount(accountId)`
- **Linha**: 626
- **Tipo**: Function declaration

### `selectAccount(accountId)`
- **Linha**: 631
- **Tipo**: Function declaration

### `toggleSidebar()`
- **Linha**: 696
- **Tipo**: Function declaration

### `closeSidebar()`
- **Linha**: 700
- **Tipo**: Function declaration

### `clearAll()`
- **Linha**: 705
- **Tipo**: Function declaration

### `buildDashboard()`
- **Linha**: 731
- **Tipo**: Function declaration

### `drillKpi(type)`
- **Linha**: 775
- **Tipo**: Function declaration

### `buildCharts()`
- **Linha**: 798
- **Tipo**: Function declaration

### `showChart(id)`
- **Linha**: 803
- **Tipo**: Function declaration

### `inv(state.stats?.monthlyInvestments||[]).sort((a, b)`
- **Linha**: 810
- **Tipo**: Arrow function

### `buildTransactionsTable()`
- **Linha**: 881
- **Tipo**: Function declaration

### `sortBy(col)`
- **Linha**: 892
- **Tipo**: Function declaration

### `renderPage()`
- **Linha**: 898
- **Tipo**: Function declaration

### `renderTxSummary(rows)`
- **Linha**: 955
- **Tipo**: Function declaration

### `goPage(p)`
- **Linha**: 975
- **Tipo**: Function declaration

### `buildInvestmentSection()`
- **Linha**: 978
- **Tipo**: Function declaration

### `filterAlerts()`
- **Linha**: 1016
- **Tipo**: Function declaration

### `buildAlertsSection()`
- **Linha**: 1021
- **Tipo**: Function declaration

### `buildBeneficiaries()`
- **Linha**: 1080
- **Tipo**: Function declaration

### `loadAccounts()`
- **Linha**: 1099
- **Tipo**: Function declaration

### `renderAccounts()`
- **Linha**: 1108
- **Tipo**: Function declaration

### `openAccountModal()`
- **Linha**: 1150
- **Tipo**: Function declaration

### `closeAccountModal()`
- **Linha**: 1151
- **Tipo**: Function declaration

### `openConfigModal(accountId, accountName)`
- **Linha**: 1229
- **Tipo**: Function declaration

### `closeConfigModal()`
- **Linha**: 1236
- **Tipo**: Function declaration

### `loadAccountConfig()`
- **Linha**: 1238
- **Tipo**: Function declaration

### `saveConfigKey(key)`
- **Linha**: 1273
- **Tipo**: Function declaration

### `resetConfigKey(key)`
- **Linha**: 1289
- **Tipo**: Function declaration

### `saveAccount()`
- **Linha**: 1299
- **Tipo**: Function declaration

### `deleteAccount(id)`
- **Linha**: 1316
- **Tipo**: Function declaration

### `loadHistory()`
- **Linha**: 1324
- **Tipo**: Function declaration

### `openResolveModal(alertId, title)`
- **Linha**: 1364
- **Tipo**: Function declaration

### `closeResolveModal()`
- **Linha**: 1371
- **Tipo**: Function declaration

### `confirmResolve()`
- **Linha**: 1373
- **Tipo**: Function declaration

### `unresolveAlert(alertId)`
- **Linha**: 1392
- **Tipo**: Function declaration

### `openNoteEditor(alertId, currentNote)`
- **Linha**: 1402
- **Tipo**: Function declaration

### `closeNoteEditor(alertId)`
- **Linha**: 1418
- **Tipo**: Function declaration

### `saveNote(alertId)`
- **Linha**: 1422
- **Tipo**: Function declaration

### `initSearchSection()`
- **Linha**: 1450
- **Tipo**: Function declaration

### `applyPreset(name)`
- **Linha**: 1467
- **Tipo**: Function declaration

### `cancelSearch()`
- **Linha**: 1505
- **Tipo**: Function declaration

### `runSearch()`
- **Linha**: 1514
- **Tipo**: Function declaration

### `clearSearch(resetContainer = true)`
- **Linha**: 1594
- **Tipo**: Function declaration

### `highlightMatch(text, query)`
- **Linha**: 1613
- **Tipo**: Function declaration

### `renderSearchResults(results, summary)`
- **Linha**: 1620
- **Tipo**: Function declaration

### `_renderSrchPage(results, summary)`
- **Linha**: 1643
- **Tipo**: Function declaration

### `_srchPagination(pages)`
- **Linha**: 1704
- **Tipo**: Function declaration

### `goSrchPage(p)`
- **Linha**: 1719
- **Tipo**: Function declaration

### `expandSearchRow(row, idx)`
- **Linha**: 1725
- **Tipo**: Function declaration

### `exportSearchCSV()`
- **Linha**: 1733
- **Tipo**: Function declaration

### `exportExcel()`
- **Linha**: 1759
- **Tipo**: Function declaration

### `exportPDF()`
- **Linha**: 1763
- **Tipo**: Function declaration

### `fmtM(v)`
- **Linha**: 1769
- **Tipo**: Function declaration

### `fmtBytes(b)`
- **Linha**: 1770
- **Tipo**: Function declaration

### `escHtml(s)`
- **Linha**: 1771
- **Tipo**: Function declaration

### `sleep(ms)`
- **Linha**: 1772
- **Tipo**: Function declaration

### `formatDateBR(iso)`
- **Linha**: 1773
- **Tipo**: Function declaration

### `showLoader(msg, pct=0, step=0, totalSteps=0)`
- **Linha**: 1780
- **Tipo**: Function declaration

### `updateLoader(msg, step=0, totalSteps=0)`
- **Linha**: 1797
- **Tipo**: Function declaration

### `hideLoader()`
- **Linha**: 1801
- **Tipo**: Function declaration

### `setProgress(pct)`
- **Linha**: 1806
- **Tipo**: Function declaration

### `setStatusBadge(type, text)`
- **Linha**: 1810
- **Tipo**: Function declaration

### `lineOpts(y1, y2)`
- **Linha**: 1816
- **Tipo**: Function declaration

### `barOpts()`
- **Linha**: 1825
- **Tipo**: Function declaration

### `fmtK(v)`
- **Linha**: 1832
- **Tipo**: Function declaration

### `updateAlertBadges()`
- **Linha**: 1834
- **Tipo**: Function declaration

### `loadCrossAnalysis()`
- **Linha**: 1869
- **Tipo**: Function declaration

### `setCrossTab(tabName)`
- **Linha**: 2067
- **Tipo**: Function declaration

### `exportCSV()`
- **Linha**: 2075
- **Tipo**: Function declaration

### `buildDailyBalanceChart()`
- **Linha**: 2081
- **Tipo**: Function declaration

### `buildWeekdayHeatmap()`
- **Linha**: 2107
- **Tipo**: Function declaration

### `buildRiskScoreBar()`
- **Linha**: 2134
- **Tipo**: Function declaration

### `buildFundEvolutionChart()`
- **Linha**: 2154
- **Tipo**: Function declaration

### `inv(state.stats?.monthlyInvestments || []).sort((a, b)`
- **Linha**: 2155
- **Tipo**: Arrow function

### `clearTxFilters()`
- **Linha**: 2177
- **Tipo**: Function declaration

### `filterTransactions()`
- **Linha**: 2188
- **Tipo**: Function declaration

### `loadCompareSessions()`
- **Linha**: 2216
- **Tipo**: Function declaration

### `runComparison()`
- **Linha**: 2238
- **Tipo**: Function declaration

### `loadCompareCurrentDelta()`
- **Linha**: 2252
- **Tipo**: Function declaration

### `renderComparisonResult(d, container, baseLabel)`
- **Linha**: 2264
- **Tipo**: Function declaration

### `initAuditTrail()`
- **Linha**: 2302
- **Tipo**: Function declaration

### `loadAuditTrail(accountId)`
- **Linha**: 2318
- **Tipo**: Function declaration

### `openAttachModal(alertId, title)`
- **Linha**: 2345
- **Tipo**: Function declaration

### `closeAttachModal()`
- **Linha**: 2353
- **Tipo**: Function declaration

### `uploadAttachment()`
- **Linha**: 2355
- **Tipo**: Function declaration

### `loadAttachmentList(alertId)`
- **Linha**: 2373
- **Tipo**: Function declaration

### `generateEmailSummary()`
- **Linha**: 2390
- **Tipo**: Function declaration

### `closeEmailModal()`
- **Linha**: 2401
- **Tipo**: Function declaration

### `copyEmailBody()`
- **Linha**: 2402
- **Tipo**: Function declaration

### `injectAttachButtons()`
- **Linha**: 2410
- **Tipo**: Function declaration

## Módulo: `./static/js/ia-chat-widget.js`

### `escapeHtml(value)`
- **Linha**: 4
- **Tipo**: Function declaration

### `renderMarkdownLite(text)`
- **Linha**: 13
- **Tipo**: Function declaration

### `ensureStylesLoaded()`
- **Linha**: 28
- **Tipo**: Function declaration

### `createEl(tag, className, html)`
- **Linha**: 37
- **Tipo**: Function declaration

### `normalizeActions(actions)`
- **Linha**: 44
- **Tipo**: Function declaration

### `create(config)`
- **Linha**: 49
- **Tipo**: Method

### `open()`
- **Linha**: 126
- **Tipo**: Function declaration

### `close()`
- **Linha**: 132
- **Tipo**: Function declaration

### `getActionMeta(id)`
- **Linha**: 137
- **Tipo**: Function declaration

### `setAction(id)`
- **Linha**: 141
- **Tipo**: Function declaration

### `showError(message, visible)`
- **Linha**: 151
- **Tipo**: Function declaration

### `run(question)`
- **Linha**: 156
- **Tipo**: Function declaration

## Módulo: `./static/js/shared-header.js`

### `isActive(href)`
- **Linha**: 14
- **Tipo**: Function declaration

### `activeClass(href)`
- **Linha**: 17
- **Tipo**: Function declaration

### `initTheme()`
- **Linha**: 26
- **Tipo**: Function declaration

### `toggleTheme()`
- **Linha**: 37
- **Tipo**: Function declaration

### `syncThemeBtn()`
- **Linha**: 50
- **Tipo**: Function declaration

### `initCosmosEffects()`
- **Linha**: 59
- **Tipo**: Function declaration

### `isCosmosTheme()`
- **Linha**: 67
- **Tipo**: Function declaration

### `prefersReducedMotion()`
- **Linha**: 71
- **Tipo**: Function declaration

### `clearTimer()`
- **Linha**: 75
- **Tipo**: Function declaration

### `createComet()`
- **Linha**: 82
- **Tipo**: Function declaration

### `scheduleNextComet()`
- **Linha**: 108
- **Tipo**: Function declaration

### `syncCosmosEffects()`
- **Linha**: 118
- **Tipo**: Function declaration

### `buildGroupItems(items)`
- **Linha**: 170
- **Tipo**: Function declaration

### `buildMobileItems(items)`
- **Linha**: 180
- **Tipo**: Function declaration

### `initDOM()`
- **Linha**: 287
- **Tipo**: Function declaration

### `contextBuilder()`
- **Linha**: 708
- **Tipo**: Method

### `contextBuilder()`
- **Linha**: 730
- **Tipo**: Method

### `ensureIaWidgetScript()`
- **Linha**: 737
- **Tipo**: Function declaration

### `buildGenericIaContext()`
- **Linha**: 759
- **Tipo**: Function declaration

### `runGenericIaRequest(pageConfig, action, question)`
- **Linha**: 771
- **Tipo**: Function declaration

### `initGenericIaWidget()`
- **Linha**: 821
- **Tipo**: Function declaration

### `openMobile()`
- **Linha**: 846
- **Tipo**: Function declaration

### `closeMobile()`
- **Linha**: 852
- **Tipo**: Function declaration

### `syncThemeButtons()`
- **Linha**: 898
- **Tipo**: Arrow function

### `callIaFree(messages, { temperature = 0.2, max_tokens = 1200 } = {})`
- **Linha**: 948
- **Tipo**: Function declaration

### `applyGlowingSearchBars()`
- **Linha**: 969
- **Tipo**: Function declaration

### `initAvatarCheckBadges()`
- **Linha**: 1040
- **Tipo**: Function declaration
