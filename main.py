from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from config import get_connection
import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Equipo(BaseModel):
    tipo_equipo: str
    marca: Optional[str] = None
    modelo: Optional[str] = None
    serie: Optional[str] = None
    activo: Optional[str] = None
    estado: Optional[str] = None
    condicion_equipo: Optional[str] = None
    comentario: Optional[str] = None
    fecha_compra: datetime.date
    fecha_asig: Optional[datetime.date] = None
    fecha_mantenimiento: Optional[datetime.date] = None
    usur_ingresa: Optional[str] = None
    foto_equipo: Optional[str] = None

# GET - Todos los equipos
@app.get("/inventario")
def consultar_todos():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM INVENTARIO_IDT ORDER BY ID_EQUIPO")
    columnas = [col[0] for col in cursor.description]
    datos = cursor.fetchall()
    conn.close()
    return {"inventario": [dict(zip(columnas, fila)) for fila in datos]}

# ─────────────────────────────────────────────────────────
# GET - Asignación FIFO con prioridad NUEVO → USADO
# ─────────────────────────────────────────────────────────
@app.get("/inventario/asignar/{tipo_equipo}")
def asignar_equipo(tipo_equipo: str):
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=500, detail="Error de conexión")
    try:
        cursor = conn.cursor()

        # 1. Buscar el equipo NUEVO más antiguo (FIFO sobre NUEVOS)
        cursor.execute("""
            SELECT * FROM INVENTARIO_IDT
            WHERE UPPER(TIPO_EQUIPO) = UPPER(%s)
              AND UPPER(ESTADO) = 'NUEVO'
            ORDER BY FECHA_REGISTRO ASC
            LIMIT 1
        """, (tipo_equipo,))

        columnas = [col[0] for col in cursor.description]
        equipo   = cursor.fetchone()

        if equipo:
            return {
                "metodo_usado": "FIFO - NUEVO",
                "razon":        "Hay equipos NUEVOS. Se asigna el más antiguo en inventario.",
                "equipo":       dict(zip(columnas, equipo))
            }

        # 2. No hay nuevos → buscar el equipo USADO más antiguo (FIFO sobre USADOS)
        cursor.execute("""
            SELECT * FROM INVENTARIO_IDT
            WHERE UPPER(TIPO_EQUIPO) = UPPER(%s)
              AND UPPER(ESTADO) = 'USADO'
            ORDER BY FECHA_REGISTRO ASC
            LIMIT 1
        """, (tipo_equipo,))

        columnas = [col[0] for col in cursor.description]
        equipo   = cursor.fetchone()

        if equipo:
            return {
                "metodo_usado": "FIFO - USADO",
                "razon":        "No hay equipos NUEVOS. Se asigna el USADO más antiguo en inventario.",
                "equipo":       dict(zip(columnas, equipo))
            }

        # 3. No hay ninguno disponible
        raise HTTPException(
            status_code=404,
            detail=f"No hay equipos disponibles del tipo '{tipo_equipo}'"
        )

    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    finally:
        conn.close()

# GET - Por ID
@app.get("/inventario/{id_equipo}")
def buscar_por_id(id_equipo: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM INVENTARIO_IDT WHERE ID_EQUIPO = %s", (id_equipo,))
    columnas = [col[0] for col in cursor.description]
    fila = cursor.fetchone()
    conn.close()
    if not fila:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return dict(zip(columnas, fila))

# POST - Registrar equipo
@app.post("/inventario")
def registrar_equipo(e: Equipo):
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=500, detail="Error de conexión")
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO INVENTARIO_IDT (
                TIPO_EQUIPO, MARCA, MODELO, SERIE, ACTIVO, ESTADO,
                CONDICION_EQUIPO, COMENTARIO, FECHA_COMPRA, FECHA_ASIG,
                FECHA_MANTENIMIENTO, USUR_INGRESA, FOTO_EQUIPO
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                e.tipo_equipo, e.marca, e.modelo, e.serie, e.activo, e.estado,
                e.condicion_equipo, e.comentario, e.fecha_compra, e.fecha_asig,
                e.fecha_mantenimiento, e.usur_ingresa, e.foto_equipo
            )
        )
        conn.commit()
        return {"mensaje": "Equipo registrado exitosamente"}
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    finally:
        conn.close()

# PUT - Actualizar equipo
@app.put("/inventario/{id_equipo}")
def actualizar_equipo(id_equipo: int, e: Equipo):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE INVENTARIO_IDT SET
                TIPO_EQUIPO=%s, MARCA=%s, MODELO=%s, SERIE=%s, ACTIVO=%s,
                ESTADO=%s, CONDICION_EQUIPO=%s, COMENTARIO=%s, FECHA_COMPRA=%s,
                FECHA_ASIG=%s, FECHA_MANTENIMIENTO=%s, USUR_INGRESA=%s, FOTO_EQUIPO=%s
            WHERE ID_EQUIPO=%s""",
            (
                e.tipo_equipo, e.marca, e.modelo, e.serie, e.activo, e.estado,
                e.condicion_equipo, e.comentario, e.fecha_compra, e.fecha_asig,
                e.fecha_mantenimiento, e.usur_ingresa, e.foto_equipo, id_equipo
            )
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        return {"status": "actualizado"}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    finally:
        conn.close()

# DELETE - Eliminar equipo
@app.delete("/inventario/{id_equipo}")
def eliminar_equipo(id_equipo: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM INVENTARIO_IDT WHERE ID_EQUIPO = %s", (id_equipo,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        return {"status": "eliminado"}
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    finally:
        conn.close()