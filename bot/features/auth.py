from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from bot.database import db_get_user, db_add_user, db_update_user_status
from bot.config import TELEGRAM_CHAT_ID

async def is_authorized_async(user_id: int) -> bool:
    if not TELEGRAM_CHAT_ID: return True
    allowed = {cid.strip() for cid in str(TELEGRAM_CHAT_ID).split(',') if cid.strip()}
    if str(user_id) in allowed: return True
    
    user = await db_get_user(str(user_id))
    if user and user['status'] in ('approved', 'admin'):
        return True
    return False

async def handle_login_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    name = update.effective_user.full_name
    
    if await is_authorized_async(update.effective_user.id):
        await update.message.reply_text("Você já possui acesso ao sistema. Digite /start para o menu.")
        return
        
    user = await db_get_user(user_id)
    if user:
        if user['status'] == 'pending':
            await update.message.reply_text("⏳ Sua solicitação ainda está pendente de aprovação.")
        elif user['status'] == 'rejected':
            await update.message.reply_text("⛔️ Sua solicitação foi rejeitada pelo administrador.")
        return
        
    await db_add_user(user_id, name)
    await update.message.reply_text("✅ <b>Solicitação Enviada!</b>\n\nSua chave de acesso foi enviada aos administradores. Aguarde a aprovação.", parse_mode='HTML')
    
    # Notificar admins
    if TELEGRAM_CHAT_ID:
        admin_ids = [cid.strip() for cid in str(TELEGRAM_CHAT_ID).split(',') if cid.strip()]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton('✅ Aprovar', callback_data=f'auth_approve_{user_id}'),
             InlineKeyboardButton('❌ Rejeitar', callback_data=f'auth_reject_{user_id}')]
        ])
        for a_id in admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=a_id, 
                    text=f"🔐 <b>Nova Solicitação de Acesso</b>\n\nUsuário: {name}\nID: <code>{user_id}</code>",
                    reply_markup=kb,
                    parse_mode='HTML'
                )
            except Exception: pass

async def handle_auth_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Retorna True se tratou o callback."""
    data = update.callback_query.data
    if not data.startswith('auth_'): return False
    
    user_id = update.effective_user.id
    # Apenas admin mestre pode aprovar
    allowed = {cid.strip() for cid in str(TELEGRAM_CHAT_ID).split(',') if cid.strip()}
    if str(user_id) not in allowed:
        await update.callback_query.answer("Sem permissão.", show_alert=True)
        return True
        
    parts = data.split('_')
    action = parts[1]
    target_id = parts[2]
    
    if action == 'approve':
        await db_update_user_status(target_id, 'approved')
        await update.callback_query.edit_message_text(f"✅ Usuário {target_id} <b>aprovado</b>.", parse_mode='HTML')
        try:
            await context.bot.send_message(chat_id=target_id, text="🎉 <b>Seu acesso foi APROVADO!</b>\n\nDigite /start para acessar seu painel.", parse_mode='HTML')
        except Exception: pass
    elif action == 'reject':
        await db_update_user_status(target_id, 'rejected')
        await update.callback_query.edit_message_text(f"❌ Usuário {target_id} <b>rejeitado</b>.", parse_mode='HTML')
        
    return True
