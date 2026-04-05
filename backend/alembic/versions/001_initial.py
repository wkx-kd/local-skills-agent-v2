"""Initial migration - create all tables

Revision ID: 001
Revises:
Create Date: 2024-04-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('username', sa.String(50), unique=True, nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_email', 'users', ['email'])

    # Conversations table
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255), default='新对话'),
        sa.Column('model', sa.String(100), default='qwen3-max'),
        sa.Column('skill_group_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('skill_groups.id', ondelete='SET NULL'), nullable=True),
        sa.Column('summary', sa.String(2000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_conversations_user_id', 'conversations', ['user_id'])

    # Messages table
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', postgresql.JSONB, nullable=False),
        sa.Column('token_count', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_messages_conversation_id', 'messages', ['conversation_id'])

    # Skills table
    op.create_table(
        'skills',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('version', sa.String(20), default='1.0.0'),
        sa.Column('source_type', sa.String(20), nullable=False),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('install_path', sa.String(500), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('installed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_skills_name', 'skills', ['name'])

    # Skill groups table
    op.create_table(
        'skill_groups',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_skill_groups_user_id', 'skill_groups', ['user_id'])

    # Skill group members (association table)
    op.create_table(
        'skill_group_members',
        sa.Column('skill_group_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('skill_groups.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('skill_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('skills.id', ondelete='CASCADE'), primary_key=True),
    )

    # Memories table
    op.create_table(
        'memories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('importance_score', sa.Float, default=0.5),
        sa.Column('access_count', sa.Integer, default=0),
        sa.Column('milvus_id', sa.String(255), nullable=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_memories_user_id', 'memories', ['user_id'])
    op.create_index('ix_memories_type', 'memories', ['type'])

    # Uploaded files table
    op.create_table(
        'uploaded_files',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_type', sa.String(50), nullable=False),
        sa.Column('file_size', sa.Integer, nullable=False),
        sa.Column('storage_path', sa.String(500), nullable=False),
        sa.Column('processing_status', sa.String(20), default='pending'),
        sa.Column('processing_strategy', sa.String(20), nullable=True),
        sa.Column('chunk_count', sa.Integer, default=0),
        sa.Column('text_content', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_uploaded_files_user_id', 'uploaded_files', ['user_id'])
    op.create_index('ix_uploaded_files_conversation_id', 'uploaded_files', ['conversation_id'])


def downgrade() -> None:
    op.drop_table('uploaded_files')
    op.drop_table('memories')
    op.drop_table('skill_group_members')
    op.drop_table('skill_groups')
    op.drop_table('skills')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('users')