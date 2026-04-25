"""initial_complete_schema_with_constraints

Migration inicial para bancos JÁ EXISTENTES em produção.

Esta migration NÃO cria tabelas (já existem no banco).
Ela apenas registra o ponto de partida para futuras migrations.

Para bancos NOVOS (sem tabelas), use: apply_constraints.py --verify

Revisão: 7efb54210000
Data: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7efb54210000'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Para bancos existentes: apenas registra o ponto de partida.
    As tabelas já existem, então não fazemos nada aqui.
    
    Esta abordagem permite usar Alembic para migrations futuras
    sem precisar recriar o esquema existente.
    """
    # Verificar se tabelas já existem
    conn = op.get_bind()
    tables = conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='credores'")
    ).fetchone()
    
    if tables:
        # Banco já existe - não faz nada, apenas registra
        pass
    else:
        # Banco novo - poderia criar tabelas aqui
        # Para agora, deixamos server.py criar via init_db()
        pass


def downgrade() -> None:
    """
    Downgrade não faz nada pois não criamos tabelas.
    """
    pass
