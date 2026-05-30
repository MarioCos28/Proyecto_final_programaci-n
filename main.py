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

@app.get("/inventario")
def consultar_todos():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM INVENTARIO_IDT ORDER BY ID_EQUIPO")
    columnas = [col[0] for col in cursor.description]
    datos = cursor.fetchall()
    conn.close()
    return {"inventario": [dict(zip(columnas, fila)) for fila in datos]}

@app.get("/inventario/asignar/{tipo_equipo}")
def asignar_equipo(tipo_equipo: str):
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=500, detail="Error de conexión")
    try:
        cursor = conn.cursor()

        for estado in ("NUEVO", "USADO"):
            cursor.execute("""
                SELECT * FROM INVENTARIO_IDT
                WHERE UPPER(TIPO_EQUIPO) = UPPER(%s)
                  AND UPPER(ESTADO)      = %s
                  AND (FECHA_ASIG IS NULL)          -- solo equipos sin asignar
                ORDER BY FECHA_REGISTRO ASC
                LIMIT 1
            """, (tipo_equipo, estado))

            columnas = [col[0] for col in cursor.description]
            equipo   = cursor.fetchone()

            if equipo:
                return {
                    "metodo_usado": f"FIFO - {estado}",
                    "razon": (
                        "Hay equipos NUEVOS sin asignar. Se sugiere el más antiguo."
                        if estado == "NUEVO"
                        else "No hay equipos NUEVOS. Se sugiere el USADO más antiguo."
                    ),
                    "equipo": dict(zip(columnas, equipo))
                }

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


@app.post("/inventario/confirmar-asignacion/{id_equipo}")
def confirmar_asignacion(id_equipo: int, usur_ingresa: Optional[str] = None):
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=500, detail="Error de conexión")
    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT ID_EQUIPO, FECHA_ASIG FROM INVENTARIO_IDT WHERE ID_EQUIPO = %s",
            (id_equipo,)
        )
        fila = cursor.fetchone()
        if not fila:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
        if fila[1] is not None:
            raise HTTPException(status_code=409, detail="El equipo ya fue asignado anteriormente")

        cursor.execute(
            """UPDATE INVENTARIO_IDT
               SET FECHA_ASIG   = CURRENT_DATE,
                   USUR_INGRESA = COALESCE(%s, USUR_INGRESA)
             WHERE ID_EQUIPO = %s""",
            (usur_ingresa, id_equipo)
        )
        conn.commit()
        return {
            "mensaje":    "Equipo asignado correctamente",
            "id_equipo":  id_equipo,
            "fecha_asig": datetime.date.today().isoformat()
        }

    except HTTPException:
        raise
    except Exception as ex:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(ex))
    finally:
        conn.close()

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

@app.post("/inventario")
def registrar_equipo(e: Equipo):
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=500, detail="Error de conexión")
    try:
        cursor = conn.cursor()

        if e.serie:
            cursor.execute(
                "SELECT ID_EQUIPO FROM INVENTARIO_IDT WHERE UPPER(SERIE) = UPPER(%s)",
                (e.serie,)
            )
            if cursor.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existe un equipo registrado con la serie '{e.serie}'"
                )
        if e.activo:
            cursor.execute(
                "SELECT ID_EQUIPO FROM INVENTARIO_IDT WHERE UPPER(ACTIVO) = UPPER(%s)",
                (e.activo,)
            )
            if cursor.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existe un equipo registrado con el activo '{e.activo}'"
                )

        cursor.execute(
            """INSERT INTO INVENTARIO_IDT (
                TIPO_EQUIPO, MARCA, MODELO, SERIE, ACTIVO, ESTADO,
                CONDICION_EQUIPO, COMENTARIO, FECHA_COMPRA, FECHA_ASIG,
                FECHA_MANTENIMIENTO, USUR_INGRESA, FOTO_EQUIPO
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING ID_EQUIPO""",
            (
                e.tipo_equipo, e.marca, e.modelo, e.serie, e.activo, e.estado,
                e.condicion_equipo, e.comentario, e.fecha_compra, e.fecha_asig,
                e.fecha_mantenimiento, e.usur_ingresa, e.foto_equipo
            )
        )
        nuevo_id = cursor.fetchone()[0]
        conn.commit()
        return {"mensaje": "Equipo registrado exitosamente", "id_equipo": nuevo_id}

    except HTTPException:
        raise
    except Exception as ex:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(ex))
    finally:
        conn.close()

@app.post("/inventario/devolver/{id_equipo}")
def devolver_equipo(
    id_equipo: int,
    fecha_devolucion: Optional[datetime.date] = None 
):
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=500, detail="Error de conexión")
    try:
        cursor = conn.cursor()
 
        cursor.execute(
            "SELECT ID_EQUIPO, FECHA_ASIG FROM INVENTARIO_IDT WHERE ID_EQUIPO = %s",
            (id_equipo,)
        )
        fila = cursor.fetchone()
        if not fila:
            raise HTTPException(status_code=404, detail="Equipo no encontrado")
 
        fecha_real = fecha_devolucion if fecha_devolucion else datetime.date.today()
 
        cursor.execute(
            """UPDATE INVENTARIO_IDT
               SET FECHA_ASIG       = NULL,
                   FECHA_DEVOLUCION = %s
             WHERE ID_EQUIPO = %s""",
            (fecha_real, id_equipo)
        )
        conn.commit()
        return {
            "mensaje":          "Equipo devuelto correctamente",
            "id_equipo":        id_equipo,
            "fecha_devolucion": str(fecha_real)
        }
 
    except HTTPException:
        raise
    except Exception as ex:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(ex))
    finally:
        conn.close()

@app.get("/inventario/asignar-devuelto/{tipo_equipo}")
def asignar_devuelto(tipo_equipo: str):
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=500, detail="Error de conexión")
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM INVENTARIO_IDT
            WHERE UPPER(TIPO_EQUIPO)  = UPPER(%s)
              AND FECHA_DEVOLUCION    IS NOT NULL   -- fue devuelto
              AND FECHA_ASIG          IS NULL        -- no está asignado ahora
            ORDER BY FECHA_DEVOLUCION DESC           -- ← DESC = Pila LIFO
            LIMIT 1
        """, (tipo_equipo,))

        columnas = [col[0] for col in cursor.description]
        equipo   = cursor.fetchone()

        if equipo:
            return {
                "metodo_usado": "LIFO - DEVUELTO",
                "razon":        "Se asigna el último equipo devuelto (Pila).",
                "equipo":       dict(zip(columnas, equipo))
            }

        raise HTTPException(
            status_code=404,
            detail=f"No hay equipos devueltos disponibles del tipo '{tipo_equipo}'"
        )

    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    finally:
        conn.close()

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
