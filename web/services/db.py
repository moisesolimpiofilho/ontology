"""Acesso ao PostgreSQL: uma conexão por operação, sempre fechada, com commit/rollback."""
from contextlib import closing, contextmanager

import psycopg2
import psycopg2.extras
from flask import current_app
from psycopg2.extras import Json

__all__ = ["transaction", "fetch_all", "fetch_one", "execute", "Json"]


@contextmanager
def transaction(dsn=None):
    """Cursor (linhas como dict) dentro de uma transação: commit ao sair, rollback em erro."""
    with closing(psycopg2.connect(dsn or current_app.config["PG_DSN"])) as conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def fetch_all(sql, params=()):
    with transaction() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def fetch_one(sql, params=()):
    with transaction() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None


def execute(sql, params=()):
    """Executa e devolve a primeira linha (útil com RETURNING), ou None."""
    with transaction() as cur:
        cur.execute(sql, params)
        try:
            row = cur.fetchone()
        except psycopg2.ProgrammingError:  # comando sem resultado
            return None
        return dict(row) if row else None
