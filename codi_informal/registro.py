"""Registro local de pagos. No guarda CLABEs ni el cuerpo crudo del webhook."""

import sqlite3
import threading
from datetime import datetime, timezone

_CANDADO = threading.Lock()


def abrir(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        create table if not exists pagos (
            transaction_id text primary key,
            tipo text not null,
            amount text not null,
            concept text,
            num_ref text,
            date_paid integer,
            canal text,
            puesto text,
            webhook_id text,
            created_at text not null
        )
        """
    )
    conn.commit()
    return conn


def registrar_pago(conn: sqlite3.Connection, evento: dict, webhook_id: str | None = None) -> bool:
    tipo = evento.get("type")
    if tipo not in ("codi.pn.payment_received", "codi.qr.payment_received"):
        return False
    transaction_id = evento.get("transactionId")
    if not transaction_id:
        raise ValueError("falta transactionId")
    externo = _externo(evento.get("metadata"))
    with _CANDADO:
        return _insertar(conn, evento, webhook_id, transaction_id, tipo, externo)


def _insertar(conn, evento, webhook_id, transaction_id, tipo, externo) -> bool:
    cursor = conn.execute(
        """
        insert or ignore into pagos (
            transaction_id, tipo, amount, concept, num_ref, date_paid,
            canal, puesto, webhook_id, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(transaction_id),
            tipo,
            str(evento.get("amount")),
            evento.get("concept"),
            evento.get("numRef"),
            evento.get("datePaid"),
            _texto(externo.get("canal")),
            _texto(externo.get("puesto")),
            webhook_id,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return cursor.rowcount == 1


def listar(conn: sqlite3.Connection, limite: int = 10) -> list[dict]:
    with _CANDADO:
        filas = conn.execute(
        """
        select transaction_id, tipo, amount, concept, date_paid
        from pagos
        order by created_at desc
        limit ?
        """,
        (limite,),
    ).fetchall()
    return [dict(fila) for fila in filas]


def aviso(fila: dict) -> str:
    concepto = fila.get("concept") or "sin concepto"
    return f"Entró un pago de ${fila['amount']} ({concepto}). Ya quedó en el registro."


def _externo(metadata) -> dict:
    if not isinstance(metadata, dict):
        return {}
    externo = metadata.get("externalMetadata")
    if not isinstance(externo, dict):
        return {}
    return externo


def _texto(valor) -> str | None:
    if valor is None:
        return None
    return str(valor)
