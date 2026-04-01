from __future__ import annotations

import asyncio
import datetime as _dt
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.ui import (
    keyboard_main,
    menu_text,
    keyboard_priority,
    keyboard_financeiro,
    keyboard_skip_or_cancel,
)
from bot.database import (
    db_listar_tarefas,
    db_criar_tarefa,
    db_buscar_protocolos,
    db_buscar_despesas,
    db_analise_financeira,
    db_logs_recentes,
)
from bot.config import SERVER_URL, logger, remember_chat_id
from bot.features.auth import (
    is_authorized_async,
    handle_login_request,
    handle_auth_callback,
)
from bot.telegram_safe import safe_answer_callback, safe_edit_message_text


def _remember_update_chat(update: Update):
    try:
        if update and update.effective_chat:
            remember_chat_id(update.effective_chat.id)
    except Exception:
        pass


def _safe_html(text: str) -> str:
    return (
        str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _fmt_currency(value):
    try:
        return f"R$ {float(value or 0):,.2f}"
    except Exception:
        return "R$ 0,00"


def _finance_message(resumo: dict, ano: int, mes: int) -> str:
    return (
        f"📊 <b>Painel Financeiro {mes:02d}/{ano}</b>\n\n"
        f"• Credores ativos: <b>{resumo['total_credores']}</b>\n"
        f"• Previsto: <b>{_fmt_currency(resumo['total_previsto'])}</b>\n"
        f"• Empenhado: <b>{_fmt_currency(resumo['total_empenhado'])}</b>\n"
        f"• Pendente: <b>{_fmt_currency(resumo['total_pendente'])}</b>\n"
        f"• % empenhado: <b>{resumo['pct_empenhado']:.1f}%</b>\n\n"
        f"<i>Use os botões abaixo para navegar entre meses.</i>"
    )


def _public_link(path: str) -> str:
    try:
        from bot.main import get_public_base_url

        base = get_public_base_url()
    except Exception:
        base = "http://localhost:5000"
    return f"{base}{path}"


async def _send_feature_link(query, title: str, path: str, details: str = ""):
    text = (
        f'🔗 <b>{title}</b>\n\n<a href="{_public_link(path)}">Abrir {title.lower()}</a>'
    )
    if details:
        text += f"\n\n{details}"
    text += "\n\n<i>Se estiver fora da rede local, abra pelo link externo gerado no dev.bat.</i>"
    await query.message.reply_text(
        text, parse_mode="HTML", disable_web_page_preview=True
    )


async def _reply_chunks(message, text: str, parse_mode: str = "HTML"):
    limit = 3500
    chunks = []
    current = []
    size = 0
    for line in text.splitlines():
        add = len(line) + 1
        if current and size + add > limit:
            chunks.append("\n".join(current))
            current = [line]
            size = add
        else:
            current.append(line)
            size += add
    if current:
        chunks.append("\n".join(current))
    for chunk in chunks:
        await message.reply_text(
            chunk, parse_mode=parse_mode, disable_web_page_preview=True
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _remember_update_chat(update)
    if not await is_authorized_async(update.effective_user.id):
        await handle_login_request(update, context)
        return

    todo = len(await db_listar_tarefas("todo"))
    prog = len(await db_listar_tarefas("in-progress"))
    done = len(await db_listar_tarefas("done"))

    await update.message.reply_text(
        text=menu_text(todo, prog, done),
        reply_markup=keyboard_main(),
        parse_mode="HTML",
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _remember_update_chat(update)
    context.user_data.clear()
    await update.message.reply_text("❌ Operação cancelada.")
    await start(update, context)


async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /link - Envia o link de acesso externo se disponível."""
    _remember_update_chat(update)
    if not await is_authorized_async(update.effective_user.id):
        return

    from bot.cloudflare_tunnel import get_tunnel_url

    url = get_tunnel_url()
    if url:
        message = (
            f"🌐 <b>Link de Acesso Externo</b>\n\n"
            f'🔗 <a href="{url}">{url}</a>\n\n'
            f"📋 <b>Funcionalidades disponíveis:</b>\n"
            f"• Kanban de Tarefas\n"
            f"• Auditor de Notas Fiscais\n"
            f"• Calendário Financeiro\n"
            f"• Gerador de Empenhos\n"
            f"• E muito mais...\n\n"
            f"⚠️ <i>Este link é temporário e será válido enquanto o servidor estiver rodando.</i>"
        )
        await update.message.reply_text(
            message, parse_mode="HTML", disable_web_page_preview=True
        )
    else:
        await update.message.reply_text(
            "ℹ️ Nenhum link de acesso externo disponível.\n\n"
            "Para gerar um link externo, inicie o sistema com <code>dev.bat</code>.",
            parse_mode="HTML",
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _remember_update_chat(update)
    query = update.callback_query
    await safe_answer_callback(query)

    user_id = update.effective_user.id
    if not await is_authorized_async(user_id):
        if await handle_auth_callback(update, context):
            return
        return

    if await handle_auth_callback(update, context):
        return

    data = query.data
    if data == "ignore":
        return

    if data == "cmd_cancelar":
        context.user_data.clear()
        await safe_edit_message_text(query, "❌ Operação cancelada.")
        return

    if data == "cmd_menu":
        context.user_data.clear()
        todo = len(await db_listar_tarefas("todo"))
        prog = len(await db_listar_tarefas("in-progress"))
        done = len(await db_listar_tarefas("done"))
        await safe_edit_message_text(
            query,
            menu_text(todo, prog, done),
            reply_markup=keyboard_main(),
            parse_mode="HTML",
        )
        return

    logger.info(f"Callback received: {data}")

    from bot.features.auditor import start_auditor_flow, generate_empenho_from_auditor
    from bot.features.kanban import (
        cmd_ver_tarefas,
        handle_pagination_callback,
        handle_task_move,
        handle_task_status_update,
    )

    if data == "cmd_auditor_nf":
        await start_auditor_flow(update, context)
        return
    if data == "cmd_empenho_from_auditor":
        await generate_empenho_from_auditor(update, context)
        return
    if data == "cmd_ver_tarefas":
        await cmd_ver_tarefas(update, context)
        return
    if data.startswith("page_tarefas_"):
        await handle_pagination_callback(update, context)
        return
    if data.startswith("move_"):
        await handle_task_move(update, context)
        return
    if data.startswith("status_update_"):
        await handle_task_status_update(update, context)
        return
    if (
        data in {"prio_high", "prio_medium", "prio_low"}
        and context.user_data.get("step") == "task_new_priority"
    ):
        priority = {"prio_high": "high", "prio_medium": "medium", "prio_low": "low"}[
            data
        ]
        title = context.user_data.get("new_task_title", "").strip()
        desc = context.user_data.get("new_task_description", "").strip()
        if not title:
            context.user_data.clear()
            await query.message.reply_text(
                "⚠️ O título da tarefa expirou. Inicie novamente em /start."
            )
            return
        task = await db_criar_tarefa(title, desc, "todo", priority)
        context.user_data.clear()
        await query.message.reply_text(
            f"✅ <b>Tarefa criada</b>\n\n"
            f"📝 {_safe_html(task.get('title'))}\n"
            f"⚡ Prioridade: {_safe_html(priority)}",
            parse_mode="HTML",
            reply_markup=keyboard_main(),
        )
        return
    if data.startswith("fin_"):
        try:
            _p = data.split("_")
            if _p[1] == "emp":
                ano, mes = int(_p[2]), int(_p[3])
                resumo = await db_analise_financeira(ano, mes)
                todos = resumo.get("empenhados", [])
                if not todos:
                    await query.message.reply_text(
                        f"📋 <b>Empenhados {mes:02d}/{ano}</b>\n\nNenhum credor empenhado.",
                        parse_mode="HTML",
                        reply_markup=keyboard_financeiro(ano, mes),
                    )
                    return
                linhas = [f"📋 <b>Empenhados {mes:02d}/{ano}</b>\n"]
                for item in todos[:20]:
                    linhas.append(
                        f"• {_safe_html(item.get('nome', '-'))} - <b>{_fmt_currency(item.get('valor'))}</b>"
                    )
                await _reply_chunks(query.message, "\n".join(linhas), parse_mode="HTML")
                return
            if _p[1] == "pend":
                ano, mes = int(_p[2]), int(_p[3])
                resumo = await db_analise_financeira(ano, mes)
                todos = resumo.get("pendentes", [])
                if not todos:
                    await query.message.reply_text(
                        f"⏳ <b>Pendentes {mes:02d}/{ano}</b>\n\nNenhum credor pendente.",
                        parse_mode="HTML",
                        reply_markup=keyboard_financeiro(ano, mes),
                    )
                    return
                linhas = [f"⏳ <b>Pendentes {mes:02d}/{ano}</b>\n"]
                for item in todos[:20]:
                    linhas.append(
                        f"• {_safe_html(item.get('nome', '-'))} - <b>{_fmt_currency(item.get('valor'))}</b>"
                    )
                await _reply_chunks(query.message, "\n".join(linhas), parse_mode="HTML")
                return
            ano, mes = int(_p[1]), int(_p[2])
            resumo = await db_analise_financeira(ano, mes)
            await query.message.reply_text(
                _finance_message(resumo, ano, mes),
                parse_mode="HTML",
                reply_markup=keyboard_financeiro(ano, mes),
                disable_web_page_preview=True,
            )
            return
        except Exception as e:
            await query.message.reply_text(f"⚠️ Erro ao abrir o painel financeiro: {e}")
            return

    if data == "cmd_nova_tarefa":
        context.user_data.clear()
        context.user_data["step"] = "task_new_title"
        await query.message.reply_text(
            "➕ <b>Nova Tarefa</b>\n\nEnvie o <b>título</b> da tarefa.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Cancelar", callback_data="cmd_cancelar")]]
            ),
        )
        return

    if data == "desc_skip" and context.user_data.get("step") == "task_new_desc":
        context.user_data["new_task_description"] = ""
        context.user_data["step"] = "task_new_priority"
        await query.message.reply_text(
            "Descrição pulada. Selecione a <b>prioridade</b> da tarefa:",
            parse_mode="HTML",
            reply_markup=keyboard_priority(),
        )
        return

    if data == "cmd_buscar_despesas":
        context.user_data.clear()
        context.user_data["step"] = "search_despesas"
        await query.message.reply_text(
            "🔎 <b>Buscar Despesas</b>\n\nEnvie um termo para pesquisar nas despesas.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Cancelar", callback_data="cmd_cancelar")]]
            ),
        )
        return

    if data == "cmd_buscar_protocolos":
        context.user_data.clear()
        context.user_data["step"] = "search_protocolos"
        await query.message.reply_text(
            "🔎 <b>Buscar Protocolo / Ofício</b>\n\nEnvie um termo para pesquisa.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Cancelar", callback_data="cmd_cancelar")]]
            ),
        )
        return

    if data == "cmd_financeiro":
        context.user_data.clear()
        hoje = _dt.date.today()
        resumo = await db_analise_financeira(hoje.year, hoje.month)
        await query.message.reply_text(
            _finance_message(resumo, hoje.year, hoje.month),
            parse_mode="HTML",
            reply_markup=keyboard_financeiro(hoje.year, hoje.month),
            disable_web_page_preview=True,
        )
        return

    if data == "cmd_log":
        logs = await db_logs_recentes(10)
        if not logs:
            await query.message.reply_text(
                "🗒 <b>Logs recentes</b>\n\nNenhum log encontrado.", parse_mode="HTML"
            )
            return
        lines = ["🗒 <b>Logs recentes</b>\n"]
        for log in logs:
            acao = _safe_html(log.get("acao", "-"))
            nome = _safe_html(log.get("credor_nome", "-"))
            data_log = _safe_html(log.get("data", "-"))
            detalhes = _safe_html(log.get("detalhes", ""))
            lines.append(
                f"• <b>{acao}</b> - {nome}\n  <code>{data_log}</code>\n  {detalhes}"
            )
        await _reply_chunks(query.message, "\n\n".join(lines), parse_mode="HTML")
        return

    if data == "cmd_consulta_cnpj":
        context.user_data.clear()
        context.user_data["step"] = "cnpj_busca"
        await query.message.reply_text(
            "🏢 <b>Consulta de CNPJ</b>\n\nEnvie o CNPJ com 14 dígitos.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Cancelar", callback_data="cmd_cancelar")]]
            ),
        )
        return

    if data == "cmd_extrato_bancario":
        await _send_feature_link(
            query,
            "Analisador Financeiro / Extratos Bancários",
            "/pages/tarifas-bancarias.html",
            "Envie um PDF de extrato na tela web para análise.",
        )
        return

    if data == "cmd_calc_diarias":
        await _send_feature_link(
            query,
            "Calculadora de Diárias",
            "/pages/calculadora-diarias.html",
            "Ferramenta web pronta para cálculo de diárias.",
        )
        return

    if data == "cmd_extrator_pdf":
        await _send_feature_link(
            query,
            "Extrator de PDF",
            "/pages/pdf.html",
            "Use a interface web para juntar, dividir e processar PDFs.",
        )
        return

    if data == "cmd_renomear_arquivo":
        await _send_feature_link(
            query,
            "Renomeador com IA",
            "/pages/renomear.html",
            "Ferramenta web completa para renomear documentos.",
        )
        return

    if data == "cmd_resumir":
        await _send_feature_link(
            query,
            "Centro de Documentos",
            "/pages/documentos.html",
            "Aí ficam os fluxos de documentos e arquivos do sistema.",
        )
        return

    if data == "cmd_minuta":
        await _send_feature_link(
            query,
            "Protocolo / Minutas",
            "/pages/protocolo.html",
            "Use a página de protocolos para gerar e organizar minutas.",
        )
        return

    if data == "cmd_gerar_rpa":
        await _send_feature_link(
            query,
            "Gerador de RPA",
            "/pages/rpa.html",
            "A página web de RPA já está pronta para uso.",
        )
        return

    if data == "cmd_gerar_empenho":
        await _send_feature_link(
            query,
            "Assistente de Empenho",
            "/pages/assistente-empenho.html",
            "Ferramenta web para gerar empenhos com apoio da IA.",
        )
        return

    if data == "cmd_nova_aquisicao":
        await _send_feature_link(
            query,
            "Nova Aquisição / Fornecimento",
            "/pages/fornecimento.html",
            "Use esta tela para solicitar materiais, serviços e compras.",
        )
        return

    if data == "cmd_relatorio":
        await _send_feature_link(
            query,
            "Relatório Mensal",
            "/pages/despesa-relatorios.html",
            "Compara períodos e gera análise orçamentária.",
        )
        return

    if data == "cmd_calc_prazos":
        await _send_feature_link(
            query,
            "Prazos e Notificações",
            "/pages/prazos.html",
            "Controle vencimentos, resoluções e alertas de prazo.",
        )
        return

    if data == "cmd_calendario":
        await _send_feature_link(
            query,
            "Calendário de Pagamentos",
            "/pages/calendario.html",
            "Acompanhe datas críticas, pagamentos e marcos do mês.",
        )
        return

    try:
        await query.message.reply_text(
            f"ℹ️ O botão <b>{data}</b> foi recebido, mas não tem ação direta no chat.\n\n"
            f"Use o menu principal ou a interface web correspondente para essa função.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Erro no callback {data}: {e}")
        await query.message.reply_text(f"⚠️ Erro ao processar comando: {str(e)}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _remember_update_chat(update)
    if not await is_authorized_async(update.effective_user.id):
        return

    step = context.user_data.get("step")
    text = update.message.text
    logger.info(f"Text received: {text[:50]} | Step: {step}")

    if step == "task_new_title":
        context.user_data["new_task_title"] = text.strip()
        context.user_data["step"] = "task_new_desc"
        await update.message.reply_text(
            "Agora envie a <b>descrição</b> da tarefa ou digite <code>-</code> para deixar em branco.",
            parse_mode="HTML",
            reply_markup=keyboard_skip_or_cancel(),
        )
        return

    if step == "task_new_desc":
        context.user_data["new_task_description"] = (
            "" if text.strip() == "-" else text.strip()
        )
        context.user_data["step"] = "task_new_priority"
        await update.message.reply_text(
            "Descrição registrada. Agora selecione a <b>prioridade</b> da tarefa:",
            parse_mode="HTML",
            reply_markup=keyboard_priority(),
        )
        return

    if step == "task_new_priority":
        title = context.user_data.get("new_task_title", "").strip()
        desc = context.user_data.get("new_task_description", "").strip()
        prio = text.strip().lower()
        if prio not in {"high", "medium", "low"}:
            await update.message.reply_text(
                "Selecione uma prioridade válida: alta, média ou baixa.",
                parse_mode="HTML",
                reply_markup=keyboard_priority(),
            )
            return
        task = await db_criar_tarefa(title, desc, "todo", prio)
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ <b>Tarefa criada</b>\n\n"
            f"📝 {_safe_html(task.get('title'))}\n"
            f"⚡ Prioridade: {_safe_html(prio)}",
            parse_mode="HTML",
            reply_markup=keyboard_main(),
        )
        return

    if step == "search_despesas":
        rows = await db_buscar_despesas(text.strip())
        context.user_data.clear()
        if not rows:
            await update.message.reply_text(
                "Nenhuma despesa encontrada para esse termo."
            )
            return
        lines = ["🔎 <b>Resultados em Despesas</b>\n"]
        for row in rows[:10]:
            dados = str(row.get("dados", ""))
            lines.append(f"• <code>{_safe_html(dados[:180])}</code>")
        await _reply_chunks(update.message, "\n\n".join(lines), parse_mode="HTML")
        return

    if step == "search_protocolos":
        rows = await db_buscar_protocolos(text.strip())
        context.user_data.clear()
        if not rows:
            await update.message.reply_text(
                "Nenhum protocolo encontrado para esse termo."
            )
            return
        lines = ["🔎 <b>Resultados em Protocolos</b>\n"]
        for row in rows[:10]:
            lines.append(
                f"• <b>{_safe_html(row.get('numero', '-'))}</b> - {_safe_html(row.get('assunto', '-'))}\n"
                f"  <code>{_safe_html(row.get('data_protocolo', '-'))}</code>"
            )
        await _reply_chunks(update.message, "\n\n".join(lines), parse_mode="HTML")
        return

    if step == "cnpj_busca":
        context.user_data.clear()
        cnpj = "".join(ch for ch in text if ch.isdigit())
        if len(cnpj) != 14:
            await update.message.reply_text("CNPJ inválido. Envie 14 dígitos.")
            return
        await update.message.reply_text("⏳ Consultando CNPJ...")
        try:
            resp = await asyncio.to_thread(
                requests.post,
                f"{SERVER_URL}/api/cnpj/buscar",
                json={"cnpj": cnpj},
                timeout=60,
            )
            data = resp.json()
            if not resp.ok:
                await update.message.reply_text(
                    f"⚠️ {data.get('error', 'Erro ao consultar CNPJ')}"
                )
                return
            msg = (
                f"🏢 <b>{_safe_html(data.get('razao_social') or data.get('nome') or 'CNPJ consultado')}</b>\n\n"
                f"• CNPJ: <code>{_safe_html(data.get('cnpj', cnpj))}</code>\n"
                f"• Situação: <b>{_safe_html(data.get('situacao', '-'))}</b>\n"
                f"• Porte: {_safe_html(data.get('porte', '-'))}\n"
                f"• CNAE principal: {_safe_html(data.get('cnae_principal', '-'))}\n"
                f"• Fonte: {_safe_html(data.get('fonte', '-'))}"
            )
            await update.message.reply_text(msg, parse_mode="HTML")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Falha ao consultar CNPJ: {e}")
        return

    if not step:
        await update.message.reply_text(
            "Escolha uma opção no menu ou digite /start para reiniciar."
        )
        return

    await update.message.reply_text(
        f"ℹ️ Entrada registrada no passo <code>{_safe_html(step)}</code>, mas esse fluxo ainda não tem tratamento específico no bot.",
        parse_mode="HTML",
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _remember_update_chat(update)
    if not await is_authorized_async(update.effective_user.id):
        return

    step = context.user_data.get("step")
    if not step:
        await update.message.reply_text(
            "Por favor, selecione uma ferramenta no menu (/start) primeiro antes de enviar arquivos."
        )
        return

    await update.message.reply_chat_action(action="typing")
    if step == "up_auditor_arquivo":
        from bot.features.auditor import process_auditor_file

        await process_auditor_file(update, context)
        return

    await update.message.reply_text(
        f"ℹ️ Recebi um documento no passo <code>{_safe_html(step)}</code>, "
        f"mas esse fluxo ainda não processa arquivo no chat.\n\n"
        f"Abra a ferramenta web correspondente no menu para concluir a operação.",
        parse_mode="HTML",
    )


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _remember_update_chat(update)
    if not await is_authorized_async(update.effective_user.id):
        return
    from bot.features.voice import process_voice_note

    await process_voice_note(update, context)
