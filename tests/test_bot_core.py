import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


class DummyMessage:
    def __init__(self):
        self.reply_text = AsyncMock()
        self.edit_message_text = AsyncMock()
        self.reply_chat_action = AsyncMock()


class DummyCallbackQuery:
    def __init__(self, data: str):
        self.data = data
        self.message = DummyMessage()
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()


class DummyUpdate:
    def __init__(self, data: str):
        self.callback_query = DummyCallbackQuery(data)
        self.effective_user = type("User", (), {"id": 123, "full_name": "Teste"})
        self.effective_chat = type("Chat", (), {"id": 321})


class DummyContext:
    def __init__(self):
        self.user_data = {}


class BotCoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_target_chat_ids_normalizes_default_and_telegram_prefix(self):
        cfg_path = Path(__file__).resolve().parent / "_bot_config_env_test.txt"
        ids = []
        try:
            cfg_path.write_text("telegram:111\n222\n", encoding="utf-8")

            import bot.config as cfg
            with patch.object(cfg, "CHAT_TARGETS_FILE", cfg_path), patch.object(cfg, "TELEGRAM_CHAT_ID", ""):
                ids = cfg.get_target_chat_ids()
        finally:
            cfg_path.unlink(missing_ok=True)

        self.assertIn("942288759", ids)
        self.assertIn("111", ids)
        self.assertIn("222", ids)

    async def test_finance_callback_routes_to_real_panel(self):
        from bot import handlers

        update = DummyUpdate("cmd_financeiro")
        context = DummyContext()

        fake_summary = {
            "total_credores": 10,
            "total_previsto": 1000,
            "total_empenhado": 400,
            "total_pendente": 600,
            "pct_empenhado": 40.0,
            "empenhados": [],
            "pendentes": [],
        }

        with patch.object(handlers, "is_authorized_async", AsyncMock(return_value=True)), \
             patch.object(handlers, "handle_auth_callback", AsyncMock(return_value=False)), \
             patch.object(handlers, "db_analise_financeira", AsyncMock(return_value=fake_summary)):
            await handlers.handle_callback(update, context)

        self.assertGreaterEqual(update.callback_query.message.reply_text.await_count, 1)
        sent_text = update.callback_query.message.reply_text.await_args.args[0]
        self.assertIn("Painel Financeiro", sent_text)

    async def test_new_task_flow_creates_task(self):
        from bot import handlers

        update = DummyUpdate("prio_medium")
        context = DummyContext()
        context.user_data.update({
            "step": "task_new_priority",
            "new_task_title": "Teste",
            "new_task_description": "Descricao",
        })

        fake_task = {"title": "Teste", "description": "Descricao", "priority": "medium"}

        with patch.object(handlers, "is_authorized_async", AsyncMock(return_value=True)), \
             patch.object(handlers, "handle_auth_callback", AsyncMock(return_value=False)), \
             patch.object(handlers, "db_criar_tarefa", AsyncMock(return_value=fake_task)):
            await handlers.handle_callback(update, context)

        self.assertEqual(context.user_data, {})
        sent_text = update.callback_query.message.reply_text.await_args.args[0]
        self.assertIn("Tarefa criada", sent_text)


if __name__ == "__main__":
    unittest.main()
