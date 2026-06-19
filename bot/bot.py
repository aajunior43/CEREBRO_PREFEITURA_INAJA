#!/usr/bin/env python3
"""CÉREBRO Bot — Telegram para Prefeitura de Inajá"""

import os, re, json, logging, asyncio
from datetime import datetime
from functools import wraps
from typing import Optional

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes,
)
from telegram.constants import ParseMode

# ── Config ────────────────────────────────────────────────────────────────────
TOKEN      = os.environ.get("TELEGRAM_TOKEN", "")
_raw_ids   = os.environ.get("TELEGRAM_CHAT_ID", "")
ALLOWED    = {int(x) for x in _raw_ids.split(",") if x.strip().isdigit()}
API_BASE   = os.environ.get("API_BASE_URL", "http://cerebro:5000")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── Estados ConversationHandler ───────────────────────────────────────────────
(
    S_LOGIN_USER, S_LOGIN_PASS,
    S_MURAL_TIT, S_MURAL_TXT, S_MURAL_CAT, S_MURAL_PRI,
    S_MURAL_COMMENT,
    S_PRAZO_DESC, S_PRAZO_DATA, S_PRAZO_CAT,
    S_PRAZO_AI,
    S_CREDOR_BUSCA,
    S_EMP_ANO, S_EMP_MES,
    S_TASK_PROMPT,
    S_PROT_ASSUNTO, S_PROT_ORIGEM, S_PROT_TIPO,
    S_RPA_PRESTADOR, S_RPA_SERVICO, S_RPA_VALOR,
    S_CNPJ,
    S_IA_MSG,
    S_CLASSIF_ITEM,
    S_EMP_ASSIST,
    S_FORN_ITEM, S_FORN_QTD, S_FORN_SETOR,
    S_CAL_TITULO, S_CAL_DATA, S_CAL_TIPO,
    S_PDF_ACTION,
    S_DESPESA_IA,
    S_DOC_BUSCA,
) = range(34)

# ── Sessões ───────────────────────────────────────────────────────────────────
_sessions: dict[int, requests.Session] = {}
_users:    dict[int, dict]             = {}

def sess(chat_id: int) -> Optional[requests.Session]:  return _sessions.get(chat_id)
def user(chat_id: int) -> dict:                         return _users.get(chat_id, {})
def logged(chat_id: int) -> bool:                       return chat_id in _sessions

def set_sess(chat_id, s, u):
    _sessions[chat_id] = s
    _users[chat_id]    = u

def del_sess(chat_id):
    _sessions.pop(chat_id, None)
    _users.pop(chat_id, None)

# ── API helpers ───────────────────────────────────────────────────────────────
def _api(chat_id, method, path, **kw):
    s = sess(chat_id)
    if not s:
        return None
    try:
        r = getattr(s, method)(f"{API_BASE}{path}", timeout=90, verify=False, **kw)
        return r
    except Exception as e:
        log.error("API %s %s → %s", method.upper(), path, e)
        return None

def aget(cid, path, **kw): return _api(cid, "get",    path, **kw)
def apost(cid, path, **kw): return _api(cid, "post",   path, **kw)
def aput(cid, path, **kw):  return _api(cid, "put",    path, **kw)
def adel(cid, path, **kw):  return _api(cid, "delete", path, **kw)

def jget(cid, path, **kw):
    r = aget(cid, path, **kw)
    return r.json() if r and r.ok else {}

def jpost(cid, path, **kw):
    r = apost(cid, path, **kw)
    return r.json() if r and r.ok else {}

# ── Utilitários ───────────────────────────────────────────────────────────────
_ESC = re.compile(r'([_*\[\]()~`>#+\-=|{}.!\\])')

def esc(t) -> str:
    return _ESC.sub(r'\\\1', str(t or ""))

def fmt_date(s: str) -> str:
    if not s: return "—"
    try:    return datetime.fromisoformat(s[:10]).strftime("%d/%m/%Y")
    except: return s[:10]

def fmt_money(v) -> str:
    try:    return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except: return str(v) if v else "—"

def trunc(s, n=120) -> str:
    s = (s or "").strip()
    return s[:n] + "…" if len(s) > n else s

def pri_emoji(p: str) -> str:
    return {"urgente":"🔴","alta":"🟠","media":"🟡","baixa":"🟢"}.get((p or "").lower(),"⚪")

def status_emoji(s: str) -> str:
    return {"a_fazer":"📋","em_andamento":"🔄","concluido":"✅","pausado":"⏸️"}.get((s or "").lower(),"❓")

async def run(fn, *a, **kw):
    return await asyncio.to_thread(fn, *a, **kw)

async def send(update: Update, text: str, **kw):
    m = update.effective_message
    # split if too long
    if len(text) > 4000:
        for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
            await m.reply_text(chunk, **kw)
    else:
        await m.reply_text(text, **kw)

# ── Decorators ────────────────────────────────────────────────────────────────
def auth_required(fn):
    @wraps(fn)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE, *a, **kw):
        cid = update.effective_chat.id
        if ALLOWED and cid not in ALLOWED:
            await update.effective_message.reply_text("⛔ Acesso não autorizado.")
            return ConversationHandler.END
        if not logged(cid):
            await update.effective_message.reply_text("🔐 Faça login primeiro: /login")
            return ConversationHandler.END
        return await fn(update, ctx, *a, **kw)
    return wrapper

# ── Teclados ──────────────────────────────────────────────────────────────────
def KB_MENU():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Mural",       callback_data="m:mural"),
         InlineKeyboardButton("⏰ Prazos",      callback_data="m:prazos")],
        [InlineKeyboardButton("👥 Credores",    callback_data="m:credores"),
         InlineKeyboardButton("📄 Empenhos",    callback_data="m:empenhos")],
        [InlineKeyboardButton("✅ Tarefas",     callback_data="m:tarefas"),
         InlineKeyboardButton("📬 Protocolos",  callback_data="m:protocolos")],
        [InlineKeyboardButton("📝 RPA",         callback_data="m:rpa"),
         InlineKeyboardButton("🔍 CNPJ",        callback_data="m:cnpj")],
        [InlineKeyboardButton("🤖 Chat IA",     callback_data="m:ia"),
         InlineKeyboardButton("🏷️ Classificar", callback_data="m:classif")],
        [InlineKeyboardButton("📁 Documentos",  callback_data="m:docs"),
         InlineKeyboardButton("🏪 Fornecimento",callback_data="m:forn")],
        [InlineKeyboardButton("📅 Calendário",  callback_data="m:cal"),
         InlineKeyboardButton("📊 Despesas IA", callback_data="m:despesaia")],
        [InlineKeyboardButton("📑 Assistente Empenho", callback_data="m:empassist")],
        [InlineKeyboardButton("🚪 Sair",        callback_data="auth:logout")],
    ])

def KB_BACK(to="menu"):
    label = "◀️ Menu" if to == "menu" else "◀️ Voltar"
    data  = "nav:menu" if to == "menu" else f"m:{to}"
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=data)]])

def KB_NAV(module: str, new_label="➕ Novo"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(new_label, callback_data=f"{module}:new"),
         InlineKeyboardButton("◀️ Menu",  callback_data="nav:menu")],
    ])

# ════════════════════════════════════════════════════════════════════════════════
# AUTH
# ════════════════════════════════════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if ALLOWED and cid not in ALLOWED:
        await update.message.reply_text("⛔ Acesso não autorizado.")
        return
    if logged(cid):
        u = user(cid)
        await update.message.reply_text(
            f"🏛️ *CÉREBRO Prefeitura de Inajá*\n\nOlá, *{esc(u.get('nome','?'))}*\\!\nUse /menu para navegar\\.",
            parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await update.message.reply_text(
            "🏛️ *CÉREBRO Prefeitura de Inajá*\n\nUse /login para acessar o sistema\\.",
            parse_mode=ParseMode.MARKDOWN_V2)

async def cmd_login(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if ALLOWED and cid not in ALLOWED:
        await update.message.reply_text("⛔ Acesso não autorizado.")
        return ConversationHandler.END
    if logged(cid):
        await update.message.reply_text(f"✅ Já logado como *{esc(user(cid).get('nome'))}*\\. Use /menu\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END
    await update.message.reply_text("🔐 Informe seu *login*:", parse_mode=ParseMode.MARKDOWN_V2)
    return S_LOGIN_USER

async def login_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["_login"] = update.message.text.strip()
    await update.message.reply_text("🔑 Informe sua *senha*:", parse_mode=ParseMode.MARKDOWN_V2)
    return S_LOGIN_PASS

async def login_pass(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid   = update.effective_chat.id
    login = ctx.user_data.pop("_login", "")
    senha = update.message.text.strip()
    try: await update.message.delete()
    except: pass
    msg = await update.effective_chat.send_message("⏳ Autenticando…")
    s = requests.Session()
    try:
        r = await run(s.post, f"{API_BASE}/api/auth/login",
                      json={"login": login, "senha": senha}, timeout=15, verify=False)
        d = r.json()
        if d.get("ok"):
            set_sess(cid, s, d["usuario"])
            await msg.edit_text(
                f"✅ Bem\\-vindo, *{esc(d['usuario']['nome'])}*\\!\n"
                f"Nível: {esc(d['usuario']['nivel'])}\n\nUse /menu para navegar\\.",
                parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await msg.edit_text(f"❌ {d.get('error','Credenciais inválidas')}")
    except Exception as e:
        await msg.edit_text(f"❌ Erro: {e}")
    return ConversationHandler.END

async def cmd_logout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if logged(cid):
        await run(lambda: apost(cid, "/api/auth/sair"))
        del_sess(cid)
    await update.effective_message.reply_text("👋 Sessão encerrada. Use /login para entrar.")

async def cb_logout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    cid = update.effective_chat.id
    if logged(cid):
        await run(lambda: apost(cid, "/api/auth/sair"))
        del_sess(cid)
    await update.callback_query.edit_message_text("👋 Sessão encerrada. Use /login para entrar.")

# ════════════════════════════════════════════════════════════════════════════════
# MENU
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = user(update.effective_chat.id)
    await update.effective_message.reply_text(
        f"🏛️ *Menu Principal*\n👤 {esc(u.get('nome','?'))} \\| {esc(u.get('nivel','?'))}",
        parse_mode=ParseMode.MARKDOWN_V2, reply_markup=KB_MENU())

async def cb_nav_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid = update.effective_chat.id
    if not logged(cid):
        await q.edit_message_text("🔐 Faça login: /login"); return
    u = user(cid)
    await q.edit_message_text(
        f"🏛️ *Menu Principal*\n👤 {esc(u.get('nome','?'))} \\| {esc(u.get('nivel','?'))}",
        parse_mode=ParseMode.MARKDOWN_V2, reply_markup=KB_MENU())

# ════════════════════════════════════════════════════════════════════════════════
# MURAL
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cb_mural(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid = update.effective_chat.id
    data = await run(lambda: jget(cid, "/api/mural", params={"limit":10}))
    items = data.get("items", []) if isinstance(data, dict) else []
    lines = ["📋 *Mural — Últimos Recados*\n"]
    for i in (items or [])[:10]:
        em = pri_emoji(i.get("prioridade",""))
        lines.append(f"{em} *{esc(i.get('titulo','?'))}*  `#{i.get('id')}`")
        lines.append(f"   👤 {esc(i.get('autor','?'))} · {esc(fmt_date(i.get('criado_em','')))}")
        if i.get("texto"): lines.append(f"   _{esc(trunc(i['texto'],80))}_")
        lines.append("")
    if not items: lines.append("_Nenhum recado encontrado_")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Novo Recado", callback_data="mural:new"),
         InlineKeyboardButton("📌 Destaque",    callback_data="mural:destaque")],
        [InlineKeyboardButton("◀️ Menu", callback_data="nav:menu")],
    ])
    await q.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)

async def cb_mural_destaque(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid = update.effective_chat.id
    data = await run(lambda: jget(cid, "/api/mural/destaque"))
    i = data if isinstance(data, dict) and data.get("titulo") else {}
    if i:
        text = (f"📌 *Destaque*\n\n*{esc(i.get('titulo',''))}*\n"
                f"_{esc(trunc(i.get('texto',''),200))}_\n\n"
                f"👤 {esc(i.get('autor','?'))} · {esc(fmt_date(i.get('criado_em','')))} ")
    else:
        text = "📌 Nenhum recado em destaque."
    await q.edit_message_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=KB_BACK("mural"))

async def cb_mural_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("📋 *Novo Recado*\n\nInforme o *título*:", parse_mode=ParseMode.MARKDOWN_V2)
    return S_MURAL_TIT

async def mural_tit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["_mural_tit"] = update.message.text.strip()
    await update.message.reply_text("📝 Informe o *texto* do recado:", parse_mode=ParseMode.MARKDOWN_V2)
    return S_MURAL_TXT

async def mural_txt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["_mural_txt"] = update.message.text.strip()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("aviso",      callback_data="mural_cat:aviso"),
         InlineKeyboardButton("tarefa",     callback_data="mural_cat:tarefa")],
        [InlineKeyboardButton("lembrete",   callback_data="mural_cat:lembrete"),
         InlineKeyboardButton("conquista",  callback_data="mural_cat:conquista")],
    ])
    await update.message.reply_text("🏷️ Categoria:", reply_markup=kb)
    return S_MURAL_CAT

async def mural_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["_mural_cat"] = q.data.split(":")[1]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 baixa",   callback_data="mural_pri:baixa"),
         InlineKeyboardButton("🟡 média",   callback_data="mural_pri:media")],
        [InlineKeyboardButton("🟠 alta",    callback_data="mural_pri:alta"),
         InlineKeyboardButton("🔴 urgente", callback_data="mural_pri:urgente")],
    ])
    await q.edit_message_text("⚡ Prioridade:", reply_markup=kb)
    return S_MURAL_PRI

async def mural_pri(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid = update.effective_chat.id
    u   = user(cid)
    payload = {
        "titulo":     ctx.user_data.pop("_mural_tit",""),
        "texto":      ctx.user_data.pop("_mural_txt",""),
        "categoria":  ctx.user_data.pop("_mural_cat","aviso"),
        "prioridade": q.data.split(":")[1],
        "autor":      u.get("nome","Bot"),
    }
    r = await run(lambda: apost(cid, "/api/mural", json=payload))
    if r and r.ok:
        await q.edit_message_text("✅ Recado publicado no mural!", reply_markup=KB_BACK("mural"))
    else:
        await q.edit_message_text("❌ Erro ao publicar recado.", reply_markup=KB_BACK("mural"))
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════════════════════════
# PRAZOS
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cb_prazos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid = update.effective_chat.id
    data = await run(lambda: jget(cid, "/api/prazos", params={"limit":15,"status":"ativos"}))
    items = data.get("items",[])
    res   = await run(lambda: jget(cid, "/api/prazos/resumo"))
    lines = ["⏰ *Prazos*\n"]
    lines.append(f"🔴 Vencidos: *{esc(str(res.get('vencidos',0)))}*  "
                 f"🟠 Urgentes: *{esc(str(res.get('urgentes',0)))}*  "
                 f"🟡 Próximos: *{esc(str(res.get('proximos',0)))}*\n")
    for i in items[:12]:
        hoje = datetime.now().date()
        try:
            venc = datetime.fromisoformat(i["data_limite"][:10]).date()
            diff = (venc - hoje).days
            if diff < 0:    em = "🔴"
            elif diff <= 7: em = "🟠"
            elif diff <= 30:em = "🟡"
            else:           em = "🟢"
        except: em = "⚪"
        lines.append(f"{em} *{esc(trunc(i.get('titulo','?'),60))}*")
        lines.append(f"   📅 {esc(fmt_date(i.get('data_limite','')))} · {esc(i.get('categoria','?'))}")
    if not items: lines.append("_Nenhum prazo ativo_")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Novo Prazo",    callback_data="prazos:new"),
         InlineKeyboardButton("🤖 Extrair c/ IA", callback_data="prazos:ai")],
        [InlineKeyboardButton("◀️ Menu", callback_data="nav:menu")],
    ])
    await q.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)

async def cb_prazos_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("⏰ *Novo Prazo*\n\nDescreva o prazo:", parse_mode=ParseMode.MARKDOWN_V2)
    return S_PRAZO_DESC

async def prazo_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["_prazo_desc"] = update.message.text.strip()
    await update.message.reply_text("📅 Data limite \\(DD/MM/AAAA\\):", parse_mode=ParseMode.MARKDOWN_V2)
    return S_PRAZO_DATA

async def prazo_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    try:
        dt = datetime.strptime(raw, "%d/%m/%Y").strftime("%Y-%m-%d")
        ctx.user_data["_prazo_data"] = dt
    except:
        await update.message.reply_text("❌ Formato inválido\\. Use DD/MM/AAAA:", parse_mode=ParseMode.MARKDOWN_V2)
        return S_PRAZO_DATA
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("TCE",      callback_data="prazo_cat:TCE"),
         InlineKeyboardButton("Contrato", callback_data="prazo_cat:Contrato")],
        [InlineKeyboardButton("Interno",  callback_data="prazo_cat:Interno"),
         InlineKeyboardButton("Outro",    callback_data="prazo_cat:Outro")],
    ])
    await update.message.reply_text("🏷️ Categoria:", reply_markup=kb)
    return S_PRAZO_CAT

async def prazo_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid = update.effective_chat.id
    payload = {
        "titulo":      ctx.user_data.pop("_prazo_desc",""),
        "data_limite": ctx.user_data.pop("_prazo_data",""),
        "categoria":   q.data.split(":")[1],
    }
    r = await run(lambda: apost(cid, "/api/prazos", json=payload))
    if r and r.ok:
        await q.edit_message_text("✅ Prazo cadastrado!", reply_markup=KB_BACK("prazos"))
    else:
        await q.edit_message_text("❌ Erro ao cadastrar prazo.", reply_markup=KB_BACK("prazos"))
    return ConversationHandler.END

async def cb_prazos_ai(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "🤖 *Extrair Prazo com IA*\n\nCole o texto que contém o prazo \\(ofício, notificação, etc\\.\\):",
        parse_mode=ParseMode.MARKDOWN_V2)
    return S_PRAZO_AI

async def prazo_ai_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    text = update.message.text.strip()
    msg  = await update.message.reply_text("⏳ Analisando com IA…")
    data = await run(lambda: jpost(cid, "/api/prazos/ai/extrair", json={"texto": text}))
    prazos = data.get("prazos", [])
    if not prazos:
        await msg.edit_text("❌ Não foi possível extrair prazos do texto.")
        return ConversationHandler.END
    lines = ["🤖 *Prazos extraídos:*\n"]
    for p in prazos:
        lines.append(f"📌 *{esc(p.get('titulo','?'))}*")
        lines.append(f"   📅 {esc(fmt_date(p.get('data_limite','')))} · {esc(p.get('categoria','?'))}")
        lines.append("")
    lines.append("_Acesse o site para salvar os prazos extraídos\\._")
    await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=KB_BACK("prazos"))
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════════════════════════
# CREDORES
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cb_credores(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "👥 *Credores*\n\nDigite o nome ou CNPJ para buscar:",
        parse_mode=ParseMode.MARKDOWN_V2)
    return S_CREDOR_BUSCA

async def credor_busca(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid   = update.effective_chat.id
    termo = update.message.text.strip()
    data  = await run(lambda: jget(cid, "/api/credores", params={"search": termo, "limit": 10}))
    items = data.get("items",[])
    if not items:
        await update.message.reply_text("❌ Nenhum credor encontrado.", reply_markup=KB_BACK("credores"))
        return ConversationHandler.END
    lines = [f"👥 *Credores — '{esc(termo)}'*\n"]
    for i in items:
        lines.append(f"• *{esc(i.get('nome','?'))}*")
        lines.append(f"  {esc(i.get('departamento','?'))} · {fmt_money(i.get('valor',0))}")
        if i.get("cnpj"): lines.append(f"  CNPJ: `{esc(i['cnpj'])}`")
        if i.get("email"): lines.append(f"  ✉️ {esc(i['email'])}")
        if i.get("validade"): lines.append(f"  📅 Validade: {esc(fmt_date(i['validade']))}")
        lines.append("")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Nova busca", callback_data="m:credores"),
         InlineKeyboardButton("◀️ Menu",       callback_data="nav:menu")],
    ])
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════════════════════════
# EMPENHOS
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cb_empenhos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    now = datetime.now()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📅 {now.strftime('%m/%Y')} (atual)",
                              callback_data=f"emp_mes:{now.year}:{now.month}")],
        [InlineKeyboardButton("🗓️ Escolher mês/ano", callback_data="emp:choose")],
        [InlineKeyboardButton("◀️ Menu", callback_data="nav:menu")],
    ])
    await q.edit_message_text("📄 *Empenhos*\n\nEscolha o período:", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)

async def cb_emp_choose(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("📄 *Empenhos*\n\nInforme o ano \\(ex: 2026\\):", parse_mode=ParseMode.MARKDOWN_V2)
    return S_EMP_ANO

async def emp_ano(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ano = update.message.text.strip()
    if not ano.isdigit():
        await update.message.reply_text("❌ Ano inválido:"); return S_EMP_ANO
    ctx.user_data["_emp_ano"] = int(ano)
    await update.message.reply_text("📅 Informe o mês \\(1\\-12\\):", parse_mode=ParseMode.MARKDOWN_V2)
    return S_EMP_MES

async def emp_mes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    mes = update.message.text.strip()
    if not mes.isdigit() or not 1 <= int(mes) <= 12:
        await update.message.reply_text("❌ Mês inválido:"); return S_EMP_MES
    ctx.user_data["_emp_mes"] = int(mes)
    cid = update.effective_chat.id
    await _show_empenhos(update, ctx, cid, ctx.user_data.pop("_emp_ano"), ctx.user_data.pop("_emp_mes"))
    return ConversationHandler.END

async def cb_emp_mes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, ano, mes = q.data.split(":")
    cid = update.effective_chat.id
    await _show_empenhos(update, ctx, cid, int(ano), int(mes), query=q)

async def _show_empenhos(update, ctx, cid, ano, mes, query=None):
    data  = await run(lambda: jget(cid, f"/api/empenhos/{ano}/{mes}"))
    items = data.get("empenhos", []) if isinstance(data, dict) else []
    total = data.get("total_geral", 0) if isinstance(data, dict) else 0
    lines = [f"📄 *Empenhos — {mes:02d}/{ano}*\n",
             f"Total: *{esc(fmt_money(total))}* \\| {esc(str(len(items)))} registros\n"]
    for i in items[:15]:
        lines.append(f"• *{esc(i.get('numero_empenho','?'))}* — {esc(i.get('credor_nome','?'))}")
        lines.append(f"  {fmt_money(i.get('valor',0))} · {esc(i.get('elemento','?'))}")
    if not items: lines.append("_Nenhum empenho encontrado_")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗓️ Outro período", callback_data="emp:choose"),
         InlineKeyboardButton("◀️ Menu",          callback_data="nav:menu")],
    ])
    txt = "\n".join(lines)
    if query:
        await query.edit_message_text(txt, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)
    else:
        await update.effective_message.reply_text(txt, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)

# ════════════════════════════════════════════════════════════════════════════════
# TAREFAS / KANBAN
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cb_tarefas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid   = update.effective_chat.id
    data  = await run(lambda: jget(cid, "/api/kanban"))
    items = data if isinstance(data, list) else []
    todo  = [i for i in items if i.get("status") == "a_fazer"]
    prog  = [i for i in items if i.get("status") == "em_andamento"]
    done  = [i for i in items if i.get("status") == "concluido"]
    lines = [f"✅ *Tarefas*\n",
             f"📋 A Fazer: *{len(todo)}*  🔄 Em Andamento: *{len(prog)}*  ✅ Concluídas: *{len(done)}*\n"]
    for i in (prog + todo)[:12]:
        lines.append(f"{status_emoji(i.get('status',''))} {pri_emoji(i.get('priority',''))} *{esc(trunc(i.get('title','?'),60))}*")
        if i.get("due"):  lines.append(f"   📅 {esc(fmt_date(i['due']))}")
        if i.get("responsavel"): lines.append(f"   👤 {esc(i['responsavel'])}")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Nova Tarefa",     callback_data="task:new"),
         InlineKeyboardButton("🤖 Criar c/ IA",     callback_data="task:ai")],
        [InlineKeyboardButton("◀️ Menu", callback_data="nav:menu")],
    ])
    await q.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)

async def cb_task_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("✅ *Nova Tarefa*\n\nInforme o título:", parse_mode=ParseMode.MARKDOWN_V2)
    return S_TASK_PROMPT

async def cb_task_ai(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["_task_use_ai"] = True
    await q.edit_message_text("🤖 *Criar Tarefa com IA*\n\nDescreva a tarefa em linguagem natural:", parse_mode=ParseMode.MARKDOWN_V2)
    return S_TASK_PROMPT

async def task_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid   = update.effective_chat.id
    text  = update.message.text.strip()
    use_ai = ctx.user_data.pop("_task_use_ai", False)
    msg   = await update.message.reply_text("⏳ Criando tarefa…")
    if use_ai:
        data = await run(lambda: jpost(cid, "/api/kanban/ai/create-from-text", json={"prompt": text}))
        if data and data.get("title"):
            r = await run(lambda: apost(cid, "/api/kanban", json={
                "title":       data.get("title",""),
                "description": data.get("description",""),
                "priority":    data.get("priority","medium"),
                "status":      data.get("status","a_fazer"),
            }))
            if r and r.ok:
                await msg.edit_text(f"✅ Tarefa criada por IA\\!\n\n*{esc(data.get('title',''))}*\n_{esc(trunc(data.get('description',''),100))}_",
                                    parse_mode=ParseMode.MARKDOWN_V2, reply_markup=KB_BACK("tarefas"))
                return ConversationHandler.END
        await msg.edit_text("❌ IA não conseguiu criar a tarefa.", reply_markup=KB_BACK("tarefas"))
    else:
        r = await run(lambda: apost(cid, "/api/kanban", json={"title": text, "status": "a_fazer", "priority": "medium"}))
        if r and r.ok:
            await msg.edit_text("✅ Tarefa criada\\!", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=KB_BACK("tarefas"))
        else:
            await msg.edit_text("❌ Erro ao criar tarefa.", reply_markup=KB_BACK("tarefas"))
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════════════════════════
# PROTOCOLOS
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cb_protocolos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid  = update.effective_chat.id
    data = await run(lambda: jget(cid, "/api/protocolos", params={"limit":10}))
    num  = await run(lambda: jget(cid, "/api/protocolos/proximo-numero"))
    items = data.get("items",[])
    proximo = num.get("numero","?") if isinstance(num, dict) else "?"
    lines = [f"📬 *Protocolos*\nPróximo nº: *{esc(str(proximo))}*\n"]
    for i in items[:10]:
        lines.append(f"• *Nº {esc(str(i.get('numero','?')))}* — {esc(trunc(i.get('assunto','?'),60))}")
        lines.append(f"  📅 {esc(fmt_date(i.get('data_entrada','')))} · {esc(i.get('tipo','?'))} · {esc(i.get('origem','?'))}")
    if not items: lines.append("_Nenhum protocolo encontrado_")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Novo Protocolo", callback_data="prot:new"),
         InlineKeyboardButton("◀️ Menu",           callback_data="nav:menu")],
    ])
    await q.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)

async def cb_prot_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("📬 *Novo Protocolo*\n\nInforme o assunto:", parse_mode=ParseMode.MARKDOWN_V2)
    return S_PROT_ASSUNTO

async def prot_assunto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["_prot_assunto"] = update.message.text.strip()
    await update.message.reply_text("🏢 Informe a *origem* \\(remetente\\):", parse_mode=ParseMode.MARKDOWN_V2)
    return S_PROT_ORIGEM

async def prot_origem(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["_prot_origem"] = update.message.text.strip()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Ofício",       callback_data="prot_tipo:Oficio"),
         InlineKeyboardButton("Memorando",    callback_data="prot_tipo:Memorando")],
        [InlineKeyboardButton("Requerimento", callback_data="prot_tipo:Requerimento"),
         InlineKeyboardButton("Outro",        callback_data="prot_tipo:Outro")],
    ])
    await update.message.reply_text("📄 Tipo do documento:", reply_markup=kb)
    return S_PROT_TIPO

async def prot_tipo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid = update.effective_chat.id
    payload = {
        "assunto": ctx.user_data.pop("_prot_assunto",""),
        "origem":  ctx.user_data.pop("_prot_origem",""),
        "tipo":    q.data.split(":")[1],
        "data_entrada": datetime.now().strftime("%Y-%m-%d"),
        "status":  "recebido",
    }
    r = await run(lambda: apost(cid, "/api/protocolos", json=payload))
    if r and r.ok:
        d = r.json()
        await q.edit_message_text(
            f"✅ Protocolo *Nº {esc(str(d.get('numero','?')))}* registrado\\!",
            parse_mode=ParseMode.MARKDOWN_V2, reply_markup=KB_BACK("protocolos"))
    else:
        await q.edit_message_text("❌ Erro ao registrar protocolo.", reply_markup=KB_BACK("protocolos"))
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════════════════════════
# RPA
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cb_rpa(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid  = update.effective_chat.id
    data = await run(lambda: jget(cid, "/api/rpas", params={"limit":10}))
    items = data.get("items", data) if isinstance(data, dict) else data if isinstance(data, list) else []
    lines = ["📝 *RPAs — Últimos Recibos*\n"]
    for i in (items or [])[:10]:
        lines.append(f"• *Nº {esc(str(i.get('numeroRPA','?')))}* — {esc(trunc(i.get('nomePrestador','?'),40))}")
        lines.append(f"  💰 {fmt_money(i.get('valorBruto',0))} · {esc(fmt_date(i.get('dataEmissao','')))}")
        lines.append(f"  📌 {esc(trunc(i.get('servicoPrestado',''),60))}")
        lines.append("")
    if not items: lines.append("_Nenhum RPA encontrado_")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Novo RPA",  callback_data="rpa:new"),
         InlineKeyboardButton("◀️ Menu",      callback_data="nav:menu")],
    ])
    await q.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)

async def cb_rpa_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("📝 *Novo RPA*\n\nNome do prestador de serviço:", parse_mode=ParseMode.MARKDOWN_V2)
    return S_RPA_PRESTADOR

async def rpa_prestador(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["_rpa_prest"] = update.message.text.strip()
    await update.message.reply_text("🔧 Serviço prestado:")
    return S_RPA_SERVICO

async def rpa_servico(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["_rpa_serv"] = update.message.text.strip()
    await update.message.reply_text("💰 Valor bruto \\(ex: 1500\\,00\\):", parse_mode=ParseMode.MARKDOWN_V2)
    return S_RPA_VALOR

async def rpa_valor(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    raw  = update.message.text.strip().replace(",",".")
    try:  valor = float(raw)
    except:
        await update.message.reply_text("❌ Valor inválido. Ex: 1500,00"); return S_RPA_VALOR
    payload = {
        "nomePrestador":  ctx.user_data.pop("_rpa_prest",""),
        "servicoPrestado":ctx.user_data.pop("_rpa_serv",""),
        "valorBruto":     valor,
        "dataEmissao":    datetime.now().strftime("%Y-%m-%d"),
    }
    r = await run(lambda: apost(cid, "/api/rpas", json=payload))
    if r and r.ok:
        await update.message.reply_text("✅ RPA registrado\\!", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=KB_BACK("rpa"))
    else:
        await update.message.reply_text("❌ Erro ao registrar RPA.", reply_markup=KB_BACK("rpa"))
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════════════════════════
# CNPJ
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cb_cnpj(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("🔍 *Consulta CNPJ*\n\nInforme o CNPJ:", parse_mode=ParseMode.MARKDOWN_V2)
    return S_CNPJ

async def cnpj_numero(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    cnpj = re.sub(r"\D","", update.message.text.strip())
    msg  = await update.message.reply_text("⏳ Consultando…")
    data = await run(lambda: jpost(cid, "/api/cnpj/buscar", json={"cnpj": cnpj}))
    if not data or data.get("error"):
        await msg.edit_text("❌ CNPJ não encontrado.", reply_markup=KB_BACK("cnpj"))
        return ConversationHandler.END
    e = data.get("estabelecimento", data)
    razao = e.get("razao_social") or data.get("razao_social","?")
    nome  = e.get("nome_fantasia") or data.get("nome_fantasia","")
    sit   = e.get("situacao_cadastral",{})
    if isinstance(sit,dict): sit = sit.get("descricao","?")
    mun   = e.get("municipio",{})
    if isinstance(mun,dict): mun = mun.get("descricao","?")
    lines = [f"🏢 *{esc(razao)}*"]
    if nome: lines.append(f"_{esc(nome)}_")
    lines += [
        f"📋 CNPJ: `{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}`",
        f"📍 {esc(str(mun))}",
        f"✅ Situação: {esc(str(sit))}",
    ]
    ativ = e.get("atividade_principal",{})
    if isinstance(ativ,dict): lines.append(f"🏭 {esc(ativ.get('descricao','?'))}")
    await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=KB_BACK("cnpj"))
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════════════════════════
# CHAT IA
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cb_ia(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data["_ia_history"] = []
    await q.edit_message_text(
        "🤖 *Chat IA*\n\nFaça sua pergunta\\. Digite /menu para sair\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Menu", callback_data="nav:menu")]]))
    return S_IA_MSG

async def ia_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    text = update.message.text.strip()
    if text.startswith("/"):
        return ConversationHandler.END
    hist = ctx.user_data.get("_ia_history",[])
    hist.append({"role":"user","content":text})
    msg = await update.message.reply_text("⏳ Pensando…")
    data = await run(lambda: jpost(cid, "/api/ia/chat", json={"messages": hist, "max_tokens": 1000}))
    choices = data.get("choices",[])
    if choices:
        reply = choices[0].get("message",{}).get("content","")
        hist.append({"role":"assistant","content":reply})
        ctx.user_data["_ia_history"] = hist[-10:]  # keep last 10
        # split long AI responses
        if len(reply) > 3900:
            for chunk in [reply[i:i+3900] for i in range(0,len(reply),3900)]:
                await update.effective_chat.send_message(chunk)
            await msg.delete()
        else:
            await msg.edit_text(reply or "❓ Sem resposta.")
    else:
        await msg.edit_text("❌ Erro na IA: " + str(data.get("error","?")))
    return S_IA_MSG

# ════════════════════════════════════════════════════════════════════════════════
# CLASSIFICADOR DE DESPESA
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cb_classif(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "🏷️ *Classificador de Despesa \\(IA\\)*\n\nDescreva o item ou serviço a classificar:",
        parse_mode=ParseMode.MARKDOWN_V2)
    return S_CLASSIF_ITEM

async def classif_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    item = update.message.text.strip()
    msg  = await update.message.reply_text("⏳ Classificando…")
    data = await run(lambda: jpost(cid, "/api/classificador-despesa", json={"item": item}))
    r    = data.get("resultado",{})
    if not r:
        await msg.edit_text("❌ Não foi possível classificar.", reply_markup=KB_BACK("classif"))
        return ConversationHandler.END
    conf = r.get("confianca",0)
    conf_bar = "🟢" if conf >= 0.8 else ("🟡" if conf >= 0.5 else "🔴")
    lines = [
        f"🏷️ *Classificação de Despesa*\n",
        f"📦 Item: _{esc(trunc(item,80))}_\n",
        f"📋 *Código:* `{esc(r.get('codigo_completo','?'))}`",
        f"📂 Grupo: {esc(r.get('grupo','?'))}",
        f"🔖 Modalidade: {esc(r.get('modalidade','?'))}",
        f"📌 Elemento: {esc(r.get('elemento','?'))}",
        f"🔹 Subelemento: {esc(r.get('subelemento_nome','?'))}",
        f"{conf_bar} Confiança: *{int(conf*100)}%*",
    ]
    if r.get("justificativa"):
        lines.append(f"\n💬 _{esc(trunc(r['justificativa'],200))}_")
    if r.get("ponto_atencao"):
        lines.append(f"\n⚠️ _{esc(trunc(r['ponto_atencao'],150))}_")
    meta = data.get("meta",{})
    lines.append(f"\n🤖 Modelo: `{esc(meta.get('model','?'))}`")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Novo item",  callback_data="m:classif"),
         InlineKeyboardButton("◀️ Menu",       callback_data="nav:menu")],
    ])
    await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════════════════════════
# ASSISTENTE DE EMPENHO
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cb_empassist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "📑 *Assistente de Empenho \\(IA\\)*\n\nCole o texto do empenho para extrair campos:",
        parse_mode=ParseMode.MARKDOWN_V2)
    return S_EMP_ASSIST

async def empassist_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    text = update.message.text.strip()
    msg  = await update.message.reply_text("⏳ Analisando empenho…")
    data = await run(lambda: jpost(cid, "/api/empenho-assistente",
                                   json={"action":"extract_fields","payload":{"texto_original": text}}))
    r = data.get("resultado",{})
    if not r:
        await msg.edit_text("❌ Não foi possível extrair campos.", reply_markup=KB_BACK("empassist"))
        return ConversationHandler.END
    lines = ["📑 *Campos Extraídos do Empenho*\n"]
    field_labels = {
        "credor_nome":"👤 Credor","credor_cnpj":"🏢 CNPJ","valor_total":"💰 Valor",
        "numero_empenho":"🔢 Número","elemento_despesa":"📋 Elemento",
        "descricao":"📝 Descrição","data":"📅 Data","processo":"📂 Processo",
    }
    for k,label in field_labels.items():
        v = r.get(k)
        if v: lines.append(f"{label}: *{esc(str(v))}*")
    meta = data.get("meta",{})
    lines.append(f"\n🤖 `{esc(meta.get('model','?'))}`")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Novo texto", callback_data="m:empassist"),
         InlineKeyboardButton("◀️ Menu",       callback_data="nav:menu")],
    ])
    await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════════════════════════
# DOCUMENTOS
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cb_docs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("📁 *Documentos*\n\nBuscar por nome \\(ou envie \\. para listar todos\\):",
                              parse_mode=ParseMode.MARKDOWN_V2)
    return S_DOC_BUSCA

async def doc_busca(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid   = update.effective_chat.id
    termo = update.message.text.strip()
    params = {"limit": 12}
    if termo != ".": params["search"] = termo
    data  = await run(lambda: jget(cid, "/api/documentos", params=params))
    items = data.get("items", []) if isinstance(data, dict) else []
    lines = [f"📁 *Documentos*" + (f" — '{esc(termo)}'" if termo != "." else "") + "\n"]
    for i in items:
        ext = (i.get("nome_arquivo","") or "").split(".")[-1].upper()
        lines.append(f"• 📄 *{esc(trunc(i.get('nome_exibicao') or i.get('nome_arquivo','?'),60))}*")
        lines.append(f"  `{esc(ext)}` · {esc(fmt_date(i.get('criado_em','')))} · ID:{i.get('id')}")
    if not items: lines.append("_Nenhum documento encontrado_")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Nova busca", callback_data="m:docs"),
         InlineKeyboardButton("◀️ Menu",       callback_data="nav:menu")],
    ])
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════════════════════════
# FORNECIMENTO
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cb_forn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid  = update.effective_chat.id
    data = await run(lambda: jget(cid, "/api/fornecimento/solicitacoes", params={"limit":10}))
    items = data.get("items", []) if isinstance(data, dict) else []
    lines = ["🏪 *Fornecimento — Solicitações*\n"]
    status_em = {"pendente":"⏳","aprovado":"✅","rejeitado":"❌","entregue":"📦"}.get
    for i in items[:10]:
        st = status_em((i.get("status","")).lower(),"⚪")
        lines.append(f"{st} *{esc(trunc(i.get('item','?'),50))}*")
        lines.append(f"   Qtd: {esc(str(i.get('quantidade','?')))} · Setor: {esc(i.get('setor','?'))}")
        lines.append(f"   📅 {esc(fmt_date(i.get('criado_em','')))}")
        lines.append("")
    if not items: lines.append("_Nenhuma solicitação_")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Nova Solicitação", callback_data="forn:new"),
         InlineKeyboardButton("◀️ Menu",             callback_data="nav:menu")],
    ])
    await q.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)

async def cb_forn_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("🏪 *Nova Solicitação*\n\nItem solicitado:", parse_mode=ParseMode.MARKDOWN_V2)
    return S_FORN_ITEM

async def forn_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["_forn_item"] = update.message.text.strip()
    await update.message.reply_text("🔢 Quantidade:")
    return S_FORN_QTD

async def forn_qtd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["_forn_qtd"] = update.message.text.strip()
    await update.message.reply_text("🏢 Setor solicitante:")
    return S_FORN_SETOR

async def forn_setor(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    payload = {
        "item":       ctx.user_data.pop("_forn_item",""),
        "quantidade": ctx.user_data.pop("_forn_qtd",""),
        "setor":      update.message.text.strip(),
        "status":     "pendente",
    }
    r = await run(lambda: apost(cid, "/api/fornecimento/solicitacoes", json=payload))
    if r and r.ok:
        await update.message.reply_text("✅ Solicitação registrada\\!", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=KB_BACK("forn"))
    else:
        await update.message.reply_text("❌ Erro ao registrar.", reply_markup=KB_BACK("forn"))
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════════════════════════
# CALENDÁRIO
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cb_cal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid  = update.effective_chat.id
    now  = datetime.now()
    data = await run(lambda: jget(cid, "/api/calendario",
                                  params={"ano": now.year, "mes": now.month}))
    eventos = data.get("eventos",[]) if isinstance(data,dict) else []
    lines = [f"📅 *Calendário — {now.strftime('%m/%Y')}*\n"]
    for ev in sorted(eventos, key=lambda x: x.get("data",""))[:15]:
        lines.append(f"• 📌 *{esc(trunc(ev.get('titulo','?'),60))}*")
        lines.append(f"   📅 {esc(fmt_date(ev.get('data','')))} · {esc(ev.get('tipo','?'))}")
    if not eventos: lines.append("_Nenhum evento este mês_")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Novo Evento", callback_data="cal:new"),
         InlineKeyboardButton("◀️ Menu",        callback_data="nav:menu")],
    ])
    await q.edit_message_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)

async def cb_cal_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("📅 *Novo Evento*\n\nTítulo do evento:", parse_mode=ParseMode.MARKDOWN_V2)
    return S_CAL_TITULO

async def cal_titulo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["_cal_tit"] = update.message.text.strip()
    await update.message.reply_text("📅 Data \\(DD/MM/AAAA\\):", parse_mode=ParseMode.MARKDOWN_V2)
    return S_CAL_DATA

async def cal_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    try:
        dt = datetime.strptime(raw, "%d/%m/%Y").strftime("%Y-%m-%d")
        ctx.user_data["_cal_data"] = dt
    except:
        await update.message.reply_text("❌ Formato inválido\\. Use DD/MM/AAAA:", parse_mode=ParseMode.MARKDOWN_V2)
        return S_CAL_DATA
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Reunião",     callback_data="cal_tipo:reuniao"),
         InlineKeyboardButton("Prazo",       callback_data="cal_tipo:prazo")],
        [InlineKeyboardButton("Feriado",     callback_data="cal_tipo:feriado"),
         InlineKeyboardButton("Outro",       callback_data="cal_tipo:outro")],
    ])
    await update.message.reply_text("🏷️ Tipo do evento:", reply_markup=kb)
    return S_CAL_TIPO

async def cal_tipo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cid = update.effective_chat.id
    payload = {
        "titulo": ctx.user_data.pop("_cal_tit",""),
        "data":   ctx.user_data.pop("_cal_data",""),
        "tipo":   q.data.split(":")[1],
    }
    r = await run(lambda: apost(cid, "/api/calendario/eventos", json=payload))
    if r and r.ok:
        await q.edit_message_text("✅ Evento registrado\\!", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=KB_BACK("cal"))
    else:
        await q.edit_message_text("❌ Erro ao registrar evento.", reply_markup=KB_BACK("cal"))
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════════════════════════
# DESPESAS IA
# ════════════════════════════════════════════════════════════════════════════════
@auth_required
async def cb_despesaia(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "📊 *Assistente de Despesas \\(IA\\)*\n\nFaça uma pergunta sobre o orçamento\\. /menu para sair\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Menu", callback_data="nav:menu")]]))
    return S_DESPESA_IA

async def despesaia_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid  = update.effective_chat.id
    text = update.message.text.strip()
    if text.startswith("/"): return ConversationHandler.END
    msg  = await update.message.reply_text("⏳ Analisando…")
    data = await run(lambda: jpost(cid, "/api/despesas/ia", json={"action":"chat","pergunta": text}))
    resp = data.get("resultado","")
    if resp:
        if len(resp) > 3900:
            for chunk in [resp[i:i+3900] for i in range(0,len(resp),3900)]:
                await update.effective_chat.send_message(chunk)
            await msg.delete()
        else:
            await msg.edit_text(resp)
    else:
        await msg.edit_text("❌ Sem resposta: " + str(data.get("error","?")))
    return S_DESPESA_IA

# ════════════════════════════════════════════════════════════════════════════════
# HELP
# ════════════════════════════════════════════════════════════════════════════════
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🏛️ *CÉREBRO Bot — Comandos*\n\n"
        "/start — Iniciar\n"
        "/login — Fazer login\n"
        "/logout — Encerrar sessão\n"
        "/menu — Menu principal\n"
        "/help — Esta ajuda\n\n"
        "*Módulos disponíveis via menu:*\n"
        "📋 Mural · ⏰ Prazos · 👥 Credores\n"
        "📄 Empenhos · ✅ Tarefas · 📬 Protocolos\n"
        "📝 RPA · 🔍 CNPJ · 🤖 Chat IA\n"
        "🏷️ Classificar Despesa · 📑 Assistente Empenho\n"
        "📁 Documentos · 🏪 Fornecimento\n"
        "📅 Calendário · 📊 Despesas IA"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)

# ════════════════════════════════════════════════════════════════════════════════
# DISPATCHER DE MÓDULOS (callback m:xxx)
# ════════════════════════════════════════════════════════════════════════════════
_MOD_HANDLERS = {
    "mural":      cb_mural,
    "prazos":     cb_prazos,
    "credores":   cb_credores,
    "empenhos":   cb_empenhos,
    "tarefas":    cb_tarefas,
    "protocolos": cb_protocolos,
    "rpa":        cb_rpa,
    "cnpj":       cb_cnpj,
    "ia":         cb_ia,
    "classif":    cb_classif,
    "docs":       cb_docs,
    "forn":       cb_forn,
    "cal":        cb_cal,
    "despesaia":  cb_despesaia,
    "empassist":  cb_empassist,
}

async def cb_module_dispatch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    mod = q.data.split(":")[1]
    handler = _MOD_HANDLERS.get(mod)
    if handler:
        return await handler(update, ctx)
    await q.answer(f"Módulo '{mod}' não implementado.")

# ════════════════════════════════════════════════════════════════════════════════
# FALLBACKS
# ════════════════════════════════════════════════════════════════════════════════
async def fallback_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("❌ Operação cancelada. Use /menu.")
    ctx.user_data.clear()
    return ConversationHandler.END

async def unknown_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not logged(update.effective_chat.id):
        await update.message.reply_text("Use /login para acessar o sistema.")
    else:
        await update.message.reply_text("Use /menu para navegar.")

# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════
def build_app():
    app = Application.builder().token(TOKEN).build()

    # ── Login conversation ────────────────────────────────────────────────────
    login_conv = ConversationHandler(
        entry_points=[CommandHandler("login", cmd_login)],
        states={
            S_LOGIN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_user)],
            S_LOGIN_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_pass)],
        },
        fallbacks=[CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── Mural conversation ────────────────────────────────────────────────────
    mural_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_mural_new, pattern="^mural:new$")],
        states={
            S_MURAL_TIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, mural_tit)],
            S_MURAL_TXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, mural_txt)],
            S_MURAL_CAT: [CallbackQueryHandler(mural_cat, pattern="^mural_cat:")],
            S_MURAL_PRI: [CallbackQueryHandler(mural_pri, pattern="^mural_pri:")],
        },
        fallbacks=[CommandHandler("menu", cmd_menu), CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── Prazos conversation ───────────────────────────────────────────────────
    prazos_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_prazos_new, pattern="^prazos:new$"),
            CallbackQueryHandler(cb_prazos_ai,  pattern="^prazos:ai$"),
        ],
        states={
            S_PRAZO_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, prazo_desc)],
            S_PRAZO_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, prazo_data)],
            S_PRAZO_CAT:  [CallbackQueryHandler(prazo_cat, pattern="^prazo_cat:")],
            S_PRAZO_AI:   [MessageHandler(filters.TEXT & ~filters.COMMAND, prazo_ai_text)],
        },
        fallbacks=[CommandHandler("menu", cmd_menu), CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── Credores conversation ─────────────────────────────────────────────────
    credores_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_credores, pattern="^m:credores$")],
        states={
            S_CREDOR_BUSCA: [MessageHandler(filters.TEXT & ~filters.COMMAND, credor_busca)],
        },
        fallbacks=[CommandHandler("menu", cmd_menu), CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── Empenhos conversation ─────────────────────────────────────────────────
    emp_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_emp_choose, pattern="^emp:choose$")],
        states={
            S_EMP_ANO: [MessageHandler(filters.TEXT & ~filters.COMMAND, emp_ano)],
            S_EMP_MES: [MessageHandler(filters.TEXT & ~filters.COMMAND, emp_mes)],
        },
        fallbacks=[CommandHandler("menu", cmd_menu), CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── Tarefas conversation ──────────────────────────────────────────────────
    task_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_task_new, pattern="^task:new$"),
            CallbackQueryHandler(cb_task_ai,  pattern="^task:ai$"),
        ],
        states={
            S_TASK_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_prompt)],
        },
        fallbacks=[CommandHandler("menu", cmd_menu), CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── Protocolos conversation ───────────────────────────────────────────────
    prot_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_prot_new, pattern="^prot:new$")],
        states={
            S_PROT_ASSUNTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, prot_assunto)],
            S_PROT_ORIGEM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, prot_origem)],
            S_PROT_TIPO:    [CallbackQueryHandler(prot_tipo, pattern="^prot_tipo:")],
        },
        fallbacks=[CommandHandler("menu", cmd_menu), CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── RPA conversation ──────────────────────────────────────────────────────
    rpa_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_rpa_new, pattern="^rpa:new$")],
        states={
            S_RPA_PRESTADOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, rpa_prestador)],
            S_RPA_SERVICO:   [MessageHandler(filters.TEXT & ~filters.COMMAND, rpa_servico)],
            S_RPA_VALOR:     [MessageHandler(filters.TEXT & ~filters.COMMAND, rpa_valor)],
        },
        fallbacks=[CommandHandler("menu", cmd_menu), CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── CNPJ conversation ─────────────────────────────────────────────────────
    cnpj_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_cnpj, pattern="^m:cnpj$")],
        states={
            S_CNPJ: [MessageHandler(filters.TEXT & ~filters.COMMAND, cnpj_numero)],
        },
        fallbacks=[CommandHandler("menu", cmd_menu), CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── Chat IA conversation ──────────────────────────────────────────────────
    ia_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_ia, pattern="^m:ia$")],
        states={
            S_IA_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, ia_msg)],
        },
        fallbacks=[CommandHandler("menu", cmd_menu), CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── Classificador conversation ────────────────────────────────────────────
    classif_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_classif, pattern="^m:classif$")],
        states={
            S_CLASSIF_ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, classif_item)],
        },
        fallbacks=[CommandHandler("menu", cmd_menu), CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── Assistente Empenho conversation ───────────────────────────────────────
    empassist_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_empassist, pattern="^m:empassist$")],
        states={
            S_EMP_ASSIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, empassist_text)],
        },
        fallbacks=[CommandHandler("menu", cmd_menu), CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── Documentos conversation ───────────────────────────────────────────────
    docs_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_docs, pattern="^m:docs$")],
        states={
            S_DOC_BUSCA: [MessageHandler(filters.TEXT & ~filters.COMMAND, doc_busca)],
        },
        fallbacks=[CommandHandler("menu", cmd_menu), CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── Fornecimento conversation ─────────────────────────────────────────────
    forn_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_forn_new, pattern="^forn:new$")],
        states={
            S_FORN_ITEM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, forn_item)],
            S_FORN_QTD:   [MessageHandler(filters.TEXT & ~filters.COMMAND, forn_qtd)],
            S_FORN_SETOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, forn_setor)],
        },
        fallbacks=[CommandHandler("menu", cmd_menu), CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── Calendário conversation ───────────────────────────────────────────────
    cal_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_cal_new, pattern="^cal:new$")],
        states={
            S_CAL_TITULO: [MessageHandler(filters.TEXT & ~filters.COMMAND, cal_titulo)],
            S_CAL_DATA:   [MessageHandler(filters.TEXT & ~filters.COMMAND, cal_data)],
            S_CAL_TIPO:   [CallbackQueryHandler(cal_tipo, pattern="^cal_tipo:")],
        },
        fallbacks=[CommandHandler("menu", cmd_menu), CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── Despesas IA conversation ──────────────────────────────────────────────
    despesaia_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_despesaia, pattern="^m:despesaia$")],
        states={
            S_DESPESA_IA: [MessageHandler(filters.TEXT & ~filters.COMMAND, despesaia_msg)],
        },
        fallbacks=[CommandHandler("menu", cmd_menu), CommandHandler("cancel", fallback_cancel)],
        per_message=False,
    )

    # ── Register all handlers (conversations first) ───────────────────────────
    for conv in [
        login_conv, mural_conv, prazos_conv, credores_conv, emp_conv,
        task_conv, prot_conv, rpa_conv, cnpj_conv, ia_conv, classif_conv,
        empassist_conv, docs_conv, forn_conv, cal_conv, despesaia_conv,
    ]:
        app.add_handler(conv)

    # ── Simple command handlers ───────────────────────────────────────────────
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("menu",   cmd_menu))
    app.add_handler(CommandHandler("logout", cmd_logout))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("cancel", fallback_cancel))

    # ── Callback handlers ─────────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(cb_nav_menu,       pattern="^nav:menu$"))
    app.add_handler(CallbackQueryHandler(cb_logout,         pattern="^auth:logout$"))
    app.add_handler(CallbackQueryHandler(cb_module_dispatch,pattern="^m:"))
    app.add_handler(CallbackQueryHandler(cb_mural,          pattern="^m:mural$"))
    app.add_handler(CallbackQueryHandler(cb_mural_destaque, pattern="^mural:destaque$"))
    app.add_handler(CallbackQueryHandler(cb_empenhos,       pattern="^m:empenhos$"))
    app.add_handler(CallbackQueryHandler(cb_emp_mes,        pattern="^emp_mes:"))
    app.add_handler(CallbackQueryHandler(cb_prazos,         pattern="^m:prazos$"))
    app.add_handler(CallbackQueryHandler(cb_protocolos,     pattern="^m:protocolos$"))
    app.add_handler(CallbackQueryHandler(cb_rpa,            pattern="^m:rpa$"))
    app.add_handler(CallbackQueryHandler(cb_forn,           pattern="^m:forn$"))
    app.add_handler(CallbackQueryHandler(cb_cal,            pattern="^m:cal$"))
    app.add_handler(CallbackQueryHandler(cb_tarefas,        pattern="^m:tarefas$"))

    # ── Fallback ──────────────────────────────────────────────────────────────
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_text))

    return app


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("TELEGRAM_TOKEN não configurado.")
    log.info("CÉREBRO Bot iniciando…")
    build_app().run_polling(drop_pending_updates=True)
