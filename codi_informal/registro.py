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
    conn.execute(
        """
        create table if not exists eventos (
            transaction_id text primary key,
            tipo text not null,
            amount text not null,
            concept text,
            num_ref text,
            date_paid integer,
            canal text,
            puesto text,
            bank_account_id text,
            codi_qr_id text,
            webhook_id text,
            created_at text not null
        )
        """
    )
    conn.commit()
    return conn


def crear_operacion(conn, dueno, chat, tipo, amount_cents, concept, bank_account_id=None) -> dict:
    """Guarda la operación en estado 'creando' ANTES de llamar a pey.

    Devuelve None si el dueño ya tiene una operación creando o incierta: revisar y
    reservar van bajo el mismo candado para que dos confirmaciones no manden dos POST.
    """
    with _CANDADO:
        if conn.execute(
            # ponytail: global, el bot tiene un solo dueño y dos identidades (webhook y /mensaje)
            # no deben poder brincarse el bloqueo; por dueño si algún día hay varios
            "select 1 from operaciones where estado in ('creando', 'incierto') limit 1",
        ).fetchone():
            return None
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


def marcar_operacion(conn, op_id, estado, transaction_id=None, qr_id=None) -> list[dict]:
    """Liga el id de pey a la operación y concilia los eventos pendientes de ese id.

    Devuelve los pagos que quedaron registrados en esta llamada.
    """
    with _CANDADO:
        conn.execute(
            "update operaciones set estado=?, pey_transaction_id=coalesce(?, pey_transaction_id),"
            " codi_qr_id=coalesce(?, codi_qr_id) where op_id=?",
            (estado, transaction_id, qr_id, op_id),
        )
        pagados = []
        if transaction_id:
            pagados = _reconciliar_pendientes(conn, op_id, por_qr=False, valor=str(transaction_id))
        elif qr_id:
            pagados = _reconciliar_pendientes(conn, op_id, por_qr=True, valor=str(qr_id))
        conn.commit()
        return pagados


def _reconciliar_pendientes(conn, op_id, por_qr: bool, valor: str) -> list[dict]:
    fila = conn.execute("select * from operaciones where op_id=?", (op_id,)).fetchone()
    if fila is None:
        return []
    if por_qr:
        pendientes = conn.execute("select * from eventos where codi_qr_id=?", (valor,)).fetchall()
    else:
        pendientes = conn.execute("select * from eventos where transaction_id=?", (valor,)).fetchall()
    pagados = []
    for pendiente in pendientes:
        transaction_id = str(pendiente["transaction_id"])
        ya = conn.execute("select 1 from pagos where transaction_id=?", (transaction_id,)).fetchone()
        if ya is not None:
            conn.execute("delete from eventos where transaction_id=?", (transaction_id,))
            continue
        datos = {
            "type": pendiente["tipo"],
            "amount": pendiente["amount"],
            "concept": pendiente["concept"],
            "numRef": pendiente["num_ref"],
            "datePaid": pendiente["date_paid"],
            "bankAccountId": pendiente["bank_account_id"],
            "codiQrId": pendiente["codi_qr_id"],
        }
        if not _monto_cuenta_ok(datos, fila):
            conn.execute("update operaciones set estado=? where op_id=?", ("pendiente", op_id))
            continue
        if _recibir(conn, datos, transaction_id, op_id, pendiente["canal"], pendiente["puesto"],
                    pendiente["webhook_id"]):
            pagados.append(datos)
    return pagados


def tiene_incierto(conn, dueno) -> bool:
    """Hay una operación de ese dueño en estado incierto sin reconciliar."""
    with _CANDADO:
        fila = conn.execute(
            "select 1 from operaciones where estado='incierto' limit 1",
        ).fetchone()
    return fila is not None


def _buscar_operacion(conn, evento: dict) -> sqlite3.Row | None:
    """Push se liga por pey_transaction_id, QR por codiQrId."""
    if evento.get("type") == "codi.qr.payment_received":
        qr_id = evento.get("codiQrId")
        if qr_id is None:
            return None
        return conn.execute("select * from operaciones where codi_qr_id=?", (str(qr_id),)).fetchone()
    transaction_id = evento.get("transactionId")
    if transaction_id is None:
        return None
    return conn.execute(
        "select * from operaciones where pey_transaction_id=?", (str(transaction_id),)
    ).fetchone()


def _monto_cuenta_ok(evento: dict, fila: sqlite3.Row) -> bool:
    """Monto y cuenta del evento tienen que coincidir con la operación."""
    try:
        monto = centavos(evento.get("amount"))
    except ValueError:
        monto = None
    cuenta = evento.get("bankAccountId")
    # sin cuenta en el evento o en la operación, es la cuenta ligada a la key
    cuenta_ok = not cuenta or not fila["bank_account_id"] or cuenta == fila["bank_account_id"]
    return monto == fila["amount_cents"] and cuenta_ok


def _guardar_pendiente(conn, evento, webhook_id, transaction_id) -> None:
    """Deja el evento pendiente de conciliación, sin contarlo como recibido."""
    externo = _externo(evento.get("metadata"))
    conn.execute(
        """
        insert or ignore into eventos (
            transaction_id, tipo, amount, concept, num_ref, date_paid,
            canal, puesto, bank_account_id, codi_qr_id, webhook_id, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transaction_id,
            evento.get("type"),
            str(evento.get("amount")),
            evento.get("concept"),
            evento.get("numRef"),
            evento.get("datePaid"),
            _texto(externo.get("canal")),
            _texto(externo.get("puesto")),
            evento.get("bankAccountId"),
            evento.get("codiQrId"),
            webhook_id,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def _insertar_pago(conn, transaction_id, tipo, amount, concept, num_ref, date_paid,
                   canal, puesto, webhook_id) -> bool:
    cursor = conn.execute(
        """
        insert or ignore into pagos (
            transaction_id, tipo, amount, concept, num_ref, date_paid,
            canal, puesto, webhook_id, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transaction_id,
            tipo,
            amount,
            concept,
            num_ref,
            date_paid,
            canal,
            puesto,
            webhook_id,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    return cursor.rowcount == 1


def _recibir(conn, datos, transaction_id, op_id, canal, puesto, webhook_id) -> bool:
    """Guarda el pago, quita el evento pendiente y marca la operación pagada."""
    nuevo = _insertar_pago(
        conn,
        transaction_id,
        tipo=datos.get("type"),
        amount=str(datos.get("amount")),
        concept=datos.get("concept"),
        num_ref=datos.get("numRef"),
        date_paid=datos.get("datePaid"),
        canal=canal,
        puesto=puesto,
        webhook_id=webhook_id,
    )
    conn.execute("delete from eventos where transaction_id=?", (transaction_id,))
    if nuevo:
        conn.execute("update operaciones set estado=? where op_id=?", ("pagado", op_id))
    return nuevo


def _procesar(conn, evento, webhook_id, transaction_id) -> bool:
    ya = conn.execute("select 1 from pagos where transaction_id=?", (transaction_id,)).fetchone()
    if ya is not None:
        return False
    fila = _buscar_operacion(conn, evento)
    if fila is None:
        _guardar_pendiente(conn, evento, webhook_id, transaction_id)
        conn.commit()
        return False
    if not _monto_cuenta_ok(evento, fila):
        conn.execute("update operaciones set estado=? where op_id=?", ("pendiente", fila["op_id"]))
        _guardar_pendiente(conn, evento, webhook_id, transaction_id)
        conn.commit()
        return False
    externo = _externo(evento.get("metadata"))
    nuevo = _recibir(
        conn, evento, transaction_id, fila["op_id"],
        _texto(externo.get("canal")), _texto(externo.get("puesto")), webhook_id,
    )
    conn.commit()
    return nuevo


def registrar_pago(conn: sqlite3.Connection, evento: dict, webhook_id: str | None = None) -> bool:
    """Registra solo pagos conciliados con una operación propia.

    Devuelve True únicamente cuando el evento concilió y era nuevo. Eventos
    desconocidos o con monto o cuenta distinta quedan pendientes, sin contar
    como recibidos ni avisar.
    """
    tipo = evento.get("type")
    if tipo not in ("codi.pn.payment_received", "codi.qr.payment_received"):
        return False
    transaction_id = evento.get("transactionId")
    if not transaction_id:
        raise ValueError("falta transactionId")
    with _CANDADO:
        return _procesar(conn, evento, webhook_id, str(transaction_id))


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


def inciertos(conn) -> list[dict]:
    """Operaciones que quedaron en duda y bloquean cobros nuevos de su dueño."""
    with _CANDADO:
        filas = conn.execute(
            "select op_id, tipo, amount_cents, created_at from operaciones"
            " where estado='incierto' order by created_at"
        ).fetchall()
    return [dict(f) for f in filas]


def resolver(conn, op_id, estado) -> bool:
    """El operador cierra un incierto después de revisarlo en pey: 'fallida' si no se creó,
    'creada' si sí. Solo toca operaciones inciertas."""
    if estado not in ("fallida", "creada"):
        return False
    with _CANDADO:
        cur = conn.execute(
            "update operaciones set estado=? where op_id=? and estado='incierto'", (estado, op_id)
        )
        conn.commit()
    return cur.rowcount == 1


if __name__ == "__main__":
    import os
    import sys

    _conn = abrir(os.environ.get("REGISTRO_PATH", "data/registro.sqlite"))
    if sys.argv[1:2] == ["resolver"] and len(sys.argv) == 4:
        print("listo" if resolver(_conn, sys.argv[2], sys.argv[3]) else "no se cambió nada")
    else:
        for _op in inciertos(_conn):
            print(_op["op_id"], _op["tipo"], _op["amount_cents"], _op["created_at"])
