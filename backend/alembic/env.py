# pyright: reportMissingImports=false, reportUnknownVariableType=false

from __future__ import annotations

from logging.config import fileConfig

from alembic import context  # type: ignore[import-not-found]


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _get_database_url() -> str:
    # Keep env loading consistent with API/worker entrypoints.
    from quantdog.config.settings import get_settings, load_env, validate_required_settings
    from quantdog.infra.sqlalchemy import normalize_database_url_for_sqlalchemy

    load_env()
    settings = get_settings()
    validate_required_settings(settings)
    assert settings.database_url is not None
    return normalize_database_url_for_sqlalchemy(settings.database_url)


target_metadata = None


def run_migrations_offline() -> None:
    url = _get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Import inside function to avoid import-time dependency.
    import sqlalchemy  # type: ignore[import-not-found]
    from sqlalchemy import pool  # type: ignore[import-not-found]

    url = _get_database_url()
    config.set_main_option("sqlalchemy.url", url)

    connectable = sqlalchemy.engine_from_config(
        config.get_section(config.config_ini_section, {}) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
