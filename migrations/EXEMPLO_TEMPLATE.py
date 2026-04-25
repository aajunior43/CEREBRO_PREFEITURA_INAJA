"""Template de Exemplo para Novas Migrations

Este arquivo mostra como criar migrations para diferentes operações.
Copie o trecho necessário para sua nova migration.

Uso:
  1. Execute: migration_criar.bat "descricao"
  2. Copie os exemplos abaixo para o arquivo criado
  3. Execute: migration_rodar.bat

═══════════════════════════════════════════════════════════
EXEMPLO 1: Adicionar coluna com constraint
═══════════════════════════════════════════════════════════

def upgrade():
    with op.batch_alter_table('credores') as batch_op:
        batch_op.add_column(sa.Column('telefone', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('ativo', sa.Integer(), server_default='1', nullable=False))
        # Adicionar constraint CHECK
        batch_op.create_check_constraint(
            'ck_credores_ativo_boolean',
            'credores',
            'ativo IN (0, 1)'
        )

def downgrade():
    with op.batch_alter_table('credores') as batch_op:
        batch_op.drop_column('telefone')
        batch_op.drop_column('ativo')


═══════════════════════════════════════════════════════════
EXEMPLO 2: Adicionar índice
═══════════════════════════════════════════════════════════

def upgrade():
    op.create_index('idx_credores_telefone', 'credores', ['telefone'])

def downgrade():
    op.drop_index('idx_credores_telefone')


═══════════════════════════════════════════════════════════
EXEMPLO 3: Adicionar constraint UNIQUE
═══════════════════════════════════════════════════════════

def upgrade():
    with op.batch_alter_table('credores') as batch_op:
        batch_op.create_unique_constraint('uq_credores_email', 'credores', ['email'])

def downgrade():
    with op.batch_alter_table('credores') as batch_op:
        batch_op.drop_constraint('uq_credores_email', type_='unique')


═══════════════════════════════════════════════════════════
EXEMPLO 4: Adicionar Foreign Key
═══════════════════════════════════════════════════════════

def upgrade():
    with op.batch_alter_table('logs') as batch_op:
        batch_op.create_foreign_key(
            'fk_logs_credor',
            'credores',
            ['credor_id'],
            ['id'],
            ondelete='SET NULL'
        )

def downgrade():
    with op.batch_alter_table('logs') as batch_op:
        batch_op.drop_constraint('fk_logs_credor', type_='foreignkey')


═══════════════════════════════════════════════════════════
EXEMPLO 5: Alterar tipo de coluna (SQLite requer recreação)
═══════════════════════════════════════════════════════════

def upgrade():
    with op.batch_alter_table('credores') as batch_op:
        batch_op.alter_column(
            'valor',
            type_=sa.Float(),
            existing_type=sa.Float(),
            nullable=False
        )

def downgrade():
    # Não há downgrade para alteração de tipo
    pass


═══════════════════════════════════════════════════════════
EXEMPLO 6: Adicionar dados padrão (seed)
═══════════════════════════════════════════════════════════

def upgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text("INSERT INTO configuracoes (chave, valor) VALUES ('versao', '2.0')")
    )

def downgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM configuracoes WHERE chave='versao'")
    )


═══════════════════════════════════════════════════════════
EXEMPLO 7: Renomear coluna
═══════════════════════════════════════════════════════════

def upgrade():
    with op.batch_alter_table('credores') as batch_op:
        batch_op.alter_column('descricao', new_column_name='observacao')

def downgrade():
    with op.batch_alter_table('credores') as batch_op:
        batch_op.alter_column('observacao', new_column_name='descricao')


═══════════════════════════════════════════════════════════
EXEMPLO 8: Remover constraint
═══════════════════════════════════════════════════════════

def upgrade():
    with op.batch_alter_table('credores') as batch_op:
        batch_op.drop_constraint('ck_credores_valor_positivo')

def downgrade():
    with op.batch_alter_table('credores') as batch_op:
        batch_op.create_check_constraint(
            'ck_credores_valor_positivo',
            'credores',
            'valor >= 0'
        )


═══════════════════════════════════════════════════════════
EXEMPLO 9: Criar tabela com constraints
═══════════════════════════════════════════════════════════

def upgrade():
    op.create_table(
        'nova_tabela',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nome', sa.Text(), nullable=False),
        sa.Column('valor', sa.Float(), server_default='0', nullable=False),
        sa.Column('ativo', sa.Integer(), server_default='1', nullable=False),
        sa.CheckConstraint('valor >= 0', name='ck_nova_tabela_valor_positivo'),
        sa.CheckConstraint('ativo IN (0, 1)', name='ck_nova_tabela_ativo_boolean'),
        sa.UniqueConstraint('nome', name='uq_nova_tabela_nome'),
    )
    op.create_index('idx_nova_tabela_nome', 'nova_tabela', ['nome'])

def downgrade():
    op.drop_index('idx_nova_tabela_nome')
    op.drop_table('nova_tabela')


═══════════════════════════════════════════════════════════
NOTAS IMPORTANTES:
═══════════════════════════════════════════════════════════

1. SQLite requer batch mode para ALTER TABLE:
   Use sempre: with op.batch_alter_table('tabela') as batch_op:

2. Sempre implemente downgrade() para permitir reversão

3. Teste migrations em banco de dados de teste antes de produção

4. Faça backup do banco antes de rodar migrations:
   python backup_db.py

5. Verifique status:
   migration_status.bat

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'REVISION_ID'
down_revision: Union[str, Sequence[str], None] = 'REVISION_ID_ANTERIOR'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - adicione suas migrations aqui."""
    pass


def downgrade() -> None:
    """Downgrade schema - reverta suas migrations aqui."""
    pass
