from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database import db_listar_tarefas
from bot.ui import _format_task_item
from bot.telegram_safe import safe_edit_message_text

ITEMS_PER_PAGE = 5

async def cmd_ver_tarefas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_tarefas_page(update, context, page=0)

async def show_tarefas_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    # Fetch all tasks and sort them
    tarefas = await db_listar_tarefas()
    
    total_pages = (len(tarefas) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    if total_pages == 0: total_pages = 1
    
    # Slice
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_tasks = tarefas[start_idx:end_idx]
    
    lines = [f'📋 <b>Tarefas do Kanban</b> (Página {page + 1}/{total_pages})\n']
    if not page_tasks:
        lines.append('<i>Nenhuma tarefa encontrada.</i>')
    else:
        for t in page_tasks:
            lines.append(_format_task_item(t, show_status=True))
            
    # Keyboards for pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton('⬅️ Anterior', callback_data=f'page_tarefas_{page - 1}'))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton('Próximo ➡️', callback_data=f'page_tarefas_{page + 1}'))
        
    kb = []
    if nav_buttons:
        kb.append(nav_buttons)
    kb.append([InlineKeyboardButton('🔙 Menu', callback_data='cmd_menu')])
    
    markup = InlineKeyboardMarkup(kb)
    text = '\n'.join(lines)
    
    if update.callback_query:
        await safe_edit_message_text(update.callback_query, text, reply_markup=markup, parse_mode='HTML')
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode='HTML')

async def handle_pagination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data.startswith('page_tarefas_'):
        page = int(data.split('_')[-1])
        await show_tarefas_page(update, context, page)
