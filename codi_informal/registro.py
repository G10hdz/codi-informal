"""Registro local de pagos. No guarda CLABEs ni el cuerpo crudo del webhook."""

import secrets
import sqlite3
import threading
from datetime import datetime, timezone

from codi_informal.pey import centavos

_CANDADO = threading.RLock()


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
    conn.execute(
        """
        create table if not exists operaciones (
            op_id text primary key,
            dueno text not null,
            chat text not null,
            tipo text not null,
            amount_cents integer not null,
            concept text,
            num_ref text unique,
            bank_account_id text,
            estado text not null,
            pey_transaction_id text,
            codi_qr_id text,
            created_at text not null
        )
        """
    )
    conn.commit()
    return conn


def crear_operacion(conn, dueno, chat, tipo, amount_cents, concept, bank_account_id=None) -> dict:
    """Guarda la operación en estado 'creando' ANTES de llamar a pey."""
    with _CANDADO:
        for _ in range(10):
            op_id = secrets.token_hex(8)
            num_ref = f"{secrets.randbelow(10**7):07d}"
            try:
                conn.execute(
                    "insert into operaciones (op_id, dueno, chat, tipo, amount_cents, concept,"
                    " num_ref, bank_account_id, estado, created_at) values (?,?,?,?,?,?,?,?,?,?)",
                    (op_id, dueno, chat, tipo, amount_cents, concept, num_ref,
                     bank_account_id or None, "creando", datetime.now(timezone.utc).isoformat()),
                )
            except sqlite3.IntegrityError:
                continue
            conn.commit()
            return {"op_id": op_id, "num_ref": num_ref}
    raise RuntimeError("no se pudo reservar la operación")


def marcar_operacion(conn, op_id, estado, transaction_id=None, qr_id=None) -> None:
    with _CANDADO:
        conn.execute(
            "update operaciones set estado=?, pey_transaction_id=coalesce(?, pey_transaction_id),"
            " codi_qr_id=coalesce(?, codi_qr_id) where op_id=?",
            (estado, transaction_id, qr_id, op_id),
        )
        conn.commit()


def _conciliar(conn, evento: dict, transaction_id: str) -> None:
    """Push se liga por transactionId, QR por codiQrId. Monto y cuenta tienen que coincidir."""
    if evento.get("type") == "codi.qr.payment_received":
        qr_id = evento.get("codiQrId")
        fila = conn.execute("select * from operaciones where codi_qr_id=?", (str(qr_id),)).fetchone() if qr_id else None
    else:
        fila = conn.execute("select * from operaciones where pey_transaction_id=?", (transaction_id,)).fetchone()
    if fila is None:
        return
    try:
        monto = centavos(evento.get("amount"))
    except ValueError:
        monto = None
    cuenta = evento.get("bankAccountId")
    # sin cuenta en el evento o en la operación, es la cuenta ligada a la key
    cuenta_ok = not cuenta or not fila["bank_account_id"] or cuenta == fila["bank_account_id"]
    estado = "pagado" if monto == fila["amount_cents"] and cuenta_ok else "pendiente"
    conn.execute("update operaciones set estado=? where op_id=?", (estado, fila["op_id"]))


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
    nuevo = cursor.rowcount == 1
    if nuevo:
        _conciliar(conn, evento, str(transaction_id))
    conn.commit()
    return nuevo


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
