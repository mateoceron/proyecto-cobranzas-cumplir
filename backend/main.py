import os
import bcrypt
import psycopg2
import pandas as pd
import shutil
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor
from pymongo import MongoClient
from datetime import datetime, timedelta
from datetime import date
from fastapi.responses import FileResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from dotenv import load_dotenv
from openai import OpenAI
from typing import Optional
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from dateutil.relativedelta import relativedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Depends, status


# ========== CONFIGURACIÓN DE SEGURIDAD (JWT) ==========
SECRET_KEY = os.getenv("SECRET_KEY", "admin")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def authenticate_user(username: str, password: str):
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT asesor_id, nombre_completo, username, password_hash, role FROM asesor WHERE username = %s", (username,))
        user = cur.fetchone()
        if not user:
            return False
        if not verify_password(password, user['password_hash']):
            return False
        return user
    finally:
        cur.close()
        conn.close()

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = {"username": username}
    except JWTError:
        raise credentials_exception
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT asesor_id, nombre_completo, username, role FROM asesor WHERE username = %s", (token_data["username"],))
        user = cur.fetchone()
        if user is None:
            raise credentials_exception
        return user
    finally:
        cur.close()
        conn.close()


load_dotenv()
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

app = FastAPI(title="Servicios Legales Cumplir S.A.S")
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_path = os.path.join(base_dir, "frontend")

# NUEVO: Configuración de permisos (CORS)
# Esto permite que tu página web hable con el servidor
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # "*" significa: aceptar conexiones de todos lados (para desarrollo)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURACIÓN POSTGRESQL (Financiero) ---
PG_CONFIG = {
    "host": "localhost", "database": "cobranzas_db",
    "user": "admin_mujer", "password": "password_seguro", "port": "5432"
}

# --- CONFIGURACIÓN MONGODB (NoSQL / IA) ---
# Conectamos al contenedor de Mongo que ya tienes corriendo
mongo_client = MongoClient("mongodb://localhost:27017/")
mongo_db = mongo_client["cobranzas_ia"]
coleccion_gestiones = mongo_db["gestiones"]

# Modelo para recibir datos (Lo que envía el asesor o el bot)
class GestionCreate(BaseModel):
    cedula_cliente: str
    canal: str
    estado_promesa: str
    comentario: str
    asesor_id: int = 1
    fecha_alerta: Optional[str] = None
    hora_alerta: Optional[str] = None

class NuevoAcuerdo(BaseModel):
    cedula_cliente: str
    monto_negociado: float
    cuotas: int
    fecha_inicio: str  # Formato YYYY-MM-DD
    comentario: str

# Ejemplo de limpieza profesional en Python antes de subir a la DB
def limpiar_monto(valor):
    if not valor or str(valor).lower() == 'nan':
        return 0
    # Quita $, puntos de mil, espacios y comas de decimales
    limpio = str(valor).replace('$', '').replace('.', '').replace(',', '.').strip()
    return float(limpio)

def get_pg_connection():
    return psycopg2.connect(**PG_CONFIG)
def actualizar_tabla_gestiones():
    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        # Agregamos las columnas silenciosamente si no existen
        cur.execute("ALTER TABLE gestiones ADD COLUMN IF NOT EXISTS fecha_alerta DATE;")
        cur.execute("ALTER TABLE gestiones ADD COLUMN IF NOT EXISTS hora_alerta TIME;")
        conn.commit()
        print(" Base de datos actualizada con campos de Alerta.")
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()
        conn.close()

# Ejecutamos la función apenas arranque el servidor
actualizar_tabla_gestiones()

@app.get("/")
def inicio():
    return {"estado": "Sistema Híbrido Activo"}

# ==========================================
# RUTA: ALERTAS Y NOTIFICACIONES DEL DÍA
# ==========================================
@app.get("/alertas_hoy")
def alertas_hoy():
    try:
        conn = get_pg_connection()
        cur = conn.cursor(
            cursor_factory=RealDictCursor
        )
        
        # Consulta dividida para que nano no la corte
        sql = "SELECT cedula_cliente as cedula, "
        sql += "TO_CHAR(hora_alerta, 'HH12:MI AM') as hora, "
        sql += "observacion "
        sql += "FROM gestiones_bitacora "
        sql += "ORDER BY hora_alerta ASC"
        
        cur.execute(sql)
        datos = cur.fetchall()
        
        cur.close()
        conn.close()
        return datos
        
    except Exception as e:
        print("Error:", e)
        return []

# ----------------------------------------------------
# MÓDULO DE CRM: REGISTRO DE GESTIONES Y ALERTAS
# ----------------------------------------------------
@app.post("/registrar_gestion")
def registrar_gestion(gestion: GestionCreate):
    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        # Insertar en gestiones (sin asesor_id)
        cur.execute("""
            INSERT INTO gestiones (numero_documento, tipo_contacto, estado_promesa, observacion, fecha_alerta, hora_alerta, fecha_gestion)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id;
        """, (
            gestion.cedula_cliente,
            gestion.canal,
            gestion.estado_promesa,
            gestion.comentario,
            gestion.fecha_alerta,
            gestion.hora_alerta
        ))
        id_gestion = cur.fetchone()[0]

        # Si hay alerta, guardar en bitácora
        if gestion.fecha_alerta and gestion.hora_alerta:
            # 1. Insertar en gestiones_bitacora (como estaba originalmente)
            cur.execute("""
                INSERT INTO gestiones_bitacora (cedula_cliente, fecha_alerta, hora_alerta, observacion)
                VALUES (%s, %s, %s, %s)
            """, (
                gestion.cedula_cliente,
                gestion.fecha_alerta,
                gestion.hora_alerta,
                gestion.comentario
            ))

            # 2. Obtener el número de operación (obligación) del cliente
            cur.execute("""
                SELECT o.numero_obligacion
                FROM obligaciones o
                JOIN deudores d ON o.deudor_id = d.deudor_id
                WHERE d.numero_documento = %s
                LIMIT 1
            """, (gestion.cedula_cliente,))
            oblig_result = cur.fetchone()
            operacion = oblig_result[0] if oblig_result else gestion.cedula_cliente

            # 3. Obtener el nombre completo del asesor
            cur.execute("SELECT nombre_completo FROM asesor WHERE asesor_id = %s", (gestion.asesor_id,))
            asesor_nombre = cur.fetchone()[0]

            # 4. Insertar en la tabla alertas
            cur.execute("""
                INSERT INTO alertas (operacion, asesor_id, asesor_nombre, fecha_alerta, hora_alerta, mensaje)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                operacion,
                gestion.asesor_id,
                asesor_nombre,
                gestion.fecha_alerta,
                gestion.hora_alerta,
                gestion.comentario
            ))

        conn.commit()
        return {"mensaje": "Gestión guardada exitosamente", "id": id_gestion}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

# ----------------------------------------------------
# HISTORIAL DE GESTIONES (Actualizado a PostgreSQL)
# ----------------------------------------------------
@app.get("/historial/{cedula}")
def obtener_historial(cedula: str):
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Obtener todas las gestiones (para el listado)
        query_gestiones = """
            SELECT 
                id,
                tipo_contacto as canal,
                fecha_gestion as fecha,
                estado_promesa,
                observacion as comentario
            FROM gestiones
            WHERE numero_documento = %s
            ORDER BY fecha_gestion DESC;
        """
        cur.execute(query_gestiones, (cedula,))
        gestiones = cur.fetchall()

        # Obtener los últimos datos de investigación (EPS, bienes, RUES, etc.)
        query_bitacora = """
            SELECT eps, bienes, rues, observacion, telefono, fecha_actualizacion
            FROM gestiones_bitacora
            WHERE cedula_cliente = %s
            ORDER BY fecha_actualizacion DESC
            LIMIT 1;
        """
        cur.execute(query_bitacora, (cedula,))
        investigacion = cur.fetchone() or {}

        # Devolvemos tanto el historial como los datos de investigación
        return {
            "historial": gestiones,
            "investigacion": investigacion   # esto se usará en el frontend
        }
    except Exception as e:
        return {"historial": [], "investigacion": {}, "error": str(e)}
    finally:
        cur.close()
        conn.close()

# ----------------------------------------------------
# MÓDULO DE ACUERDOS DE PAGO (PostgreSQL - Unificado)
# ----------------------------------------------------
@app.post("/crear_acuerdo")
def crear_acuerdo(acuerdo: NuevoAcuerdo):
    print(f" --- INICIANDO GUARDADO DE ACUERDO PARA: {acuerdo.cedula_cliente} ---")
    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        # 1. Buscar al deudor
        cur.execute("SELECT deudor_id FROM deudores WHERE numero_documento = %s", (acuerdo.cedula_cliente,))
        resultado = cur.fetchone()
        if not resultado:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        deudor_id = resultado[0]
        
        # 2. Guardar el Acuerdo (¡Con el nombre de columna correcto!)
        valor_cuota = acuerdo.monto_negociado / acuerdo.cuotas
        cur.execute("""
            INSERT INTO acuerdos_pago (deudor_id, monto_acordado, numero_cuotas, valor_cuota, fecha_primera_cuota)
            VALUES (%s, %s, %s, %s, %s)
        """, (deudor_id, acuerdo.monto_negociado, acuerdo.cuotas, valor_cuota, acuerdo.fecha_inicio))
        
        # 3. Guardar en el Historial (Aquí SÍ usamos el comentario)
        mensaje_historial = f"Acuerdo generado por ${acuerdo.monto_negociado:,.2f} a {acuerdo.cuotas} cuotas. {acuerdo.comentario}"
        cur.execute("""
            INSERT INTO gestiones (numero_documento, tipo_contacto, estado_promesa, observacion, fecha_gestion)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (acuerdo.cedula_cliente, "Sistema Web", "Acuerdo Cerrado", mensaje_historial))
        
        # 4. EL COMANDO CRÍTICO: Guardar cambios en el disco
        conn.commit()
        print(" --- ACUERDO Y GESTIÓN GUARDADOS PERFECTAMENTE ---")
        return {"mensaje": "Acuerdo creado exitosamente"}
        
    except Exception as e:
        conn.rollback() # Si algo falla, aborta
        print(f" ERROR FATAL AL GUARDAR: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

# ----------------------------------------------------
# FUNCION PARA LIMPIAR DINERO DEL EXCEL (Puntos y comas)
# ----------------------------------------------------
def limpiar_moneda(valor_excel):
    if valor_excel is None or str(valor_excel).strip() == "" or str(valor_excel).lower() == 'nan':
        return 0.0
    texto = str(valor_excel).strip()
    texto = texto.replace('.', '')
    texto = texto.replace(',', '.')
    try:
        return float(texto)
    except ValueError:
        return 0.0

# ----------------------------------------------------
# CARGA MASIVA BLINDADA (PARA ARCHIVO CUMPLIR)
# ----------------------------------------------------
@app.post("/cargar_campana")
async def cargar_base_datos(archivo: UploadFile = File(...)):
    try:
        # 1. Guardar archivo temporal
        nombre_archivo = f"temp_{archivo.filename}"
        with open(nombre_archivo, "wb") as buffer:
            shutil.copyfileobj(archivo.file, buffer)

        print(f"--- PROCESANDO: {nombre_archivo} ---")

        # 2. LECTURA (soporta CSV y Excel)
        df = None
        try:
            # Intenta leer como CSV con punto y coma
            df = pd.read_csv(nombre_archivo, sep=';', dtype=str)
            if len(df.columns) < 2:
                raise Exception("Menos de 2 columnas, intentando con coma")
        except:
            try:
                # Intenta leer como CSV con coma
                df = pd.read_csv(nombre_archivo, sep=',', dtype=str)
            except:
                try:
                    # Lee todas las hojas de Excel y las concatena
                    diccionario_hojas = pd.read_excel(nombre_archivo, sheet_name=None, dtype=str)
                    df = pd.concat(diccionario_hojas.values(), ignore_index=True)
                except Exception as e:
                    return {"error": f"No se pudo leer el archivo: {e}"}

        if df is None or df.empty:
            return {"error": "El archivo está vacío o es inválido."}

        # 3. Normalizar nombres de columnas
        df.columns = [str(c).upper().strip().replace(' ', '') for c in df.columns]
        print(f"COLUMNAS ENCONTRADAS: {df.columns.tolist()}")

        # 4. Buscar columnas clave
        def buscar(palabra_clave):
            for col in df.columns:
                if palabra_clave in col:
                    return col
            return None

        c_cedula = buscar("NUMERODEIDENTIFICACIONDELCLIENTE")
        c_saldo  = buscar("SALDOTOTALDELCREDITO")
        c_mora   = buscar("ATRASO")
        c_oblig  = buscar("NUMERODELCREDITO")
        c_nombre = buscar("NOMBRECOMPLETODELCLIENTE")
        c_asesor = buscar("ASESOR")   # <-- NUEVO: busca la columna que contiene el nombre del asesor

        if not c_cedula or not c_saldo:
            return {
                "error": f"Faltan columnas. Busqué IDENTIFICACION y SALDO. Encontré: {df.columns.tolist()}",
                "total_procesados": 0
            }

        # 5. Insertar en base de datos
        conn = get_pg_connection()
        cur = conn.cursor()
        exitos = 0

        for index, fila in df.iterrows():
            try:
                # --- Limpieza de cédula ---
                raw_ced = str(fila[c_cedula]).strip()
                if not raw_ced or raw_ced.upper() in ('NAN', 'NONE'):
                    continue
                try:
                    cedula = str(int(float(raw_ced)))
                except Exception:
                    cedula = raw_ced.split('.')[0]

                # --- Limpieza de nombre ---
                nombre = str(fila[c_nombre]).strip().upper() if c_nombre else "SIN NOMBRE"

                # --- Limpieza de asesor ---
                asesor = None
                if c_asesor and pd.notna(fila[c_asesor]):
                    asesor = str(fila[c_asesor]).strip().upper()

                # --- Limpieza de saldo ---
                raw_saldo = str(fila[c_saldo])
                val_saldo = ''.join(c for c in raw_saldo if c.isdigit() or c in ['.', ','])
                if val_saldo == '':
                    saldo = 0.0
                else:
                    if ',' in val_saldo:
                        val_saldo = val_saldo.replace('.', '').replace(',', '.')
                    elif val_saldo.count('.') > 1:
                        val_saldo = val_saldo.replace('.', '')
                    try:
                        saldo = float(val_saldo)
                    except:
                        saldo = 0.0

                # --- Mora ---
                try:
                    mora = int(float(str(fila[c_mora]).strip())) if c_mora else 0
                except:
                    mora = 0

                # --- Número de obligación (único por deudor) ---
                obligacion_raw = str(fila[c_oblig]).strip() if c_oblig else "SIN_NUMERO"
                obligacion = f"{obligacion_raw}-{cedula}"

                # --- INSERTAR DEUDOR (con asesor) ---
                cur.execute("""
                    INSERT INTO deudores (numero_documento, nombres, decil, score_comportamiento, asesor_nombre)
                    VALUES (%s, %s, 5, 500, %s)
                    ON CONFLICT (numero_documento) DO UPDATE SET
                        nombres = EXCLUDED.nombres,
                        asesor_nombre = EXCLUDED.asesor_nombre;
                """, (cedula, nombre, asesor))

                # --- OBTENER DEUDOR_ID ---
                cur.execute("SELECT deudor_id FROM deudores WHERE numero_documento = %s", (cedula,))
                res_id = cur.fetchone()
                if res_id:
                    deudor_id = res_id[0]

                    # --- INSERTAR OBLIGACIÓN ---
                    cur.execute("""
                        INSERT INTO obligaciones (deudor_id, numero_obligacion, saldo_total, dias_mora)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (numero_obligacion) DO NOTHING;
                    """, (deudor_id, obligacion, saldo, mora))

                    conn.commit()
                    exitos += 1

            except Exception as e:
                conn.rollback()
                print(f"Fallo en fila {index}: {e}")
                continue

        cur.close()
        conn.close()
        return {"mensaje": f"Archivo procesado. Registros exitosos: {exitos}"}

    except Exception as e:
        return {"error": f"Error crítico: {str(e)}"}

# 5. Generador de PDF (Contrato de Acuerdo)
@app.get("/descargar_acuerdo/{cedula}")
def descargar_acuerdo(cedula: str):
    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        # 1. Buscar al cliente
        cur.execute("SELECT deudor_id FROM deudores WHERE numero_documento = %s", (cedula,))
        resultado = cur.fetchone()
        if not resultado:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        deudor_id = resultado[0]

        # 2. Buscar el último acuerdo
        cur.execute("""
            SELECT monto_acordado, numero_cuotas, valor_cuota, fecha_primera_cuota
            FROM acuerdos_pago 
            WHERE deudor_id = %s 
            ORDER BY acuerdo_id DESC 
            LIMIT 1;
        """, (deudor_id,))
        acuerdo = cur.fetchone()
        if not acuerdo:
            raise HTTPException(status_code=404, detail="No hay acuerdos para este cliente")

        # 3. Desempaquetar la tupla de PostgreSQL a variables limpias
        monto_acordado = acuerdo[0]
        numero_cuotas = acuerdo[1]
        valor_cuota = acuerdo[2]
        fecha_inicio = acuerdo[3]

        # 4. Crear el PDF
        nombre_archivo = f"Acuerdo_{cedula}.pdf"
        ruta_pdf = f"/tmp/{nombre_archivo}"
        
        c = canvas.Canvas(ruta_pdf, pagesize=letter)
        ancho, alto = letter
        
        # --- Encabezado ---
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, alto - 50, "BANCO MUNDO MUJER")
        c.setFont("Helvetica", 10)
        c.drawString(50, alto - 70, "Departamento de Cobranzas y Recuperación")
        c.line(50, alto - 80, 550, alto - 80)
        
        # --- Título y Texto ---
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, alto - 120, "CONSTANCIA DE ACUERDO DE PAGO")
        c.setFont("Helvetica", 12)
        
        # ¡La variable texto que te faltaba!
        texto = f"Por medio de la presente, certificamos que el cliente identificado con\ncédula {cedula}, ha formalizado un acuerdo de pago con la entidad\npara normalizar su obligación pendiente."
        
        text_object = c.beginText(50, alto - 160)
        for linea in texto.split('\n'):
            text_object.textLine(linea)
        c.drawText(text_object)
        
        # --- Cuadro de Datos ---
        y_inicio = alto - 250
        c.rect(50, y_inicio - 100, 500, 100)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(70, y_inicio - 30, f"Monto Acordado:  $ {monto_acordado:,.0f}")
        c.drawString(70, y_inicio - 50, f"Plazo:           {numero_cuotas} Cuotas")
        c.drawString(70, y_inicio - 70, f"Valor Cuota:     $ {valor_cuota:,.0f}")
        c.drawString(300, y_inicio - 30, f"Fecha Inicio:    {fecha_inicio}")
        
        # --- Pie de página ---
        from datetime import datetime
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(50, 50, f"Documento generado automáticamente el {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        c.drawString(50, 40, "Este documento presta mérito ejecutivo.")
        
        c.save()
        return FileResponse(ruta_pdf, media_type='application/pdf', filename=nombre_archivo)

    except Exception as e:
        print(f"Error generando PDF: {e}")
        # Esto mostrará el error REAL en tu navegador si algo falla
        raise HTTPException(status_code=500, detail=f"Fallo en Backend: {str(e)}") 
    finally:
        cur.close()
        conn.close()

# 6. Dashboard Gerencial (Métricas en Tiempo Real)
@app.get("/metricas_generales")
def obtener_metricas():
    conn = get_pg_connection() # Asegúrate que use el usuario admin_mujer internamente
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # FUNDAMENTO: Usamos el nombre REAL de la columna: monto_acordado
        cur.execute("""
            SELECT 
                COUNT(*) as cantidad, 
                COALESCE(SUM(monto_acordado), 0) as total 
            FROM acuerdos_pago
        """)
        datos_acuerdos = cur.fetchone()
        
        cur.execute("SELECT COALESCE(SUM(saldo_total), 0) as deuda_total FROM obligaciones")
        datos_cartera = cur.fetchone()
        
        recuperado = float(datos_acuerdos['total'])
        meta = float(datos_cartera['deuda_total'])
        
        # Cálculo matemático formal:
        # $$ \text{porcentaje} = \left( \frac{\text{recuperado}}{\text{meta}} \right) \times 100 $$
        porcentaje = round((recuperado / meta * 100), 2) if meta > 0 else 0

        return {
            "dinero": {
                "recuperado": recuperado,
                "meta_total": meta,
                "acuerdos_cerrados": datos_acuerdos['cantidad'],
                "porcentaje_exito": porcentaje
            },
            "ia": {"positivos": 15, "negativos": 4, "neutros": 6} 
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

# --- HERRAMIENTA DE DIAGNÓSTICO (Borrar después) ---
@app.get("/debug/ver_clientes")
def ver_ultimos_clientes():
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Traer los últimos 10 deudores creados
    cur.execute("""
        SELECT deudor_id, numero_documento, names, decil 
        FROM deudores 
        ORDER BY deudor_id DESC 
        LIMIT 10
    """)
    clientes = cur.fetchall()
    
    # Traer las últimas 10 obligaciones
    cur.execute("""
        SELECT obligacion_id, deudor_id, numero_obligacion, saldo_total 
        FROM obligaciones 
        ORDER BY obligacion_id DESC 
        LIMIT 10
    """)
    obligaciones = cur.fetchall()
    
    conn.close()
    return {
        "aviso": "Estos son los datos REALES en tu base de datos:",
        "ultimos_deudores": clientes,
        "ultimas_obligaciones": obligaciones  
      }

@app.get("/saldo/{cedula}")
def consultar_cliente(cedula: str):
    try:
        conn = get_pg_connection()
        cur = conn.cursor()

        ced_limpia = cedula.strip()

        # 1. Buscar al cliente
        cur.execute("SELECT deudor_id, nombres, decil, numero_documento FROM deudores WHERE numero_documento = %s", (ced_limpia,))
        deudor = cur.fetchone()

        if not deudor:
            conn.close()
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        deudor_id = deudor[0]

        # 2. Buscar su deuda (Volvemos a fetchone para tomar el dato tal cual)
        cur.execute("SELECT numero_obligacion, saldo_total, dias_mora FROM obligaciones WHERE deudor_id = %s", (deudor_id,))
        deuda = cur.fetchone()
        conn.close()

        # 3. Retornar exactamente lo que hay, protegido contra nulos
        return {
            "nombres": deudor[1],
            "decil": deudor[2],
            "numero_documento": deudor[3],
            "numero_obligacion": deuda[0] if deuda else "SIN-REF",
            "saldo_total": deuda[1] if deuda else 0,
            "dias_mora": deuda[2] if deuda else 0
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------
# MÓDULO DE INTELIGENCIA ARTIFICIAL (SPEECH ANALYTICS)
# ----------------------------------------------------
@app.post("/analizar_llamada")
async def analizar_llamada(audio: UploadFile = File(...)):
    try:
        import os
        import shutil

        # 1. Extraemos la extensión del archivo que subas (ej. mp3, ogg, wav)
        ext = audio.filename.split('.')[-1].lower()
        if ext not in ['flac', 'mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'ogg', 'opus', 'wav', 'webm']:
            ext = 'mp3' # Por defecto
            
        temp_audio_path = f"audio_seguro.{ext}"
        print(f" Guardando archivo temporalmente como: {temp_audio_path}")
        
        # 2. Guardamos el archivo físicamente (El método más seguro para la API)
        with open(temp_audio_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)

        print(" Analizando audio con Whisper (Vía Groq)...")

        # 3. Transcripción mandando el archivo físico real
        with open(temp_audio_path, "rb") as audio_file:
            transcripcion = client.audio.transcriptions.create(
                model="whisper-large-v3", 
                file=audio_file,
                language="es"
            )
        
        texto_llamada = transcripcion.text
        print(f" Transcripción: {texto_llamada}")

        # 4. Limpieza: Borramos el archivo temporal para no llenar tu disco
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

        print(" Extrayendo promesas de pago con IA...")

        # 5. Análisis con LLama3 (Extracción de datos estructurados)
        respuesta_ia = client.chat.completions.create(
            model="llama3-8b-8192", 
            response_format={ "type": "json_object" },
            messages=[
                {
                    "role": "system",
                    "content": """Eres un analista experto en cobranzas. Lee la transcripción de la llamada y devuelve ÚNICAMENTE un objeto JSON con estas claves:
                    - "actitud_cliente": (Positiva, Negativa, Evasiva, o Neutra)
                    - "fecha_promesa": (La fecha acordada de pago en formato YYYY-MM-DD. Si no hay, pon null)
                    - "monto_promesa": (El dinero prometido solo en números. Si no hay, pon null)
                    - "resumen": (Un resumen de máximo 20 palabras de la llamada)"""
                },
                {
                    "role": "user",
                    "content": f"Transcripción de la llamada: {texto_llamada}"
                }
            ]
        )

        # 6. Retornar el resultado a la web
        resultado_json = respuesta_ia.choices[0].message.content
        return {
            "mensaje": "Análisis completado",
            "transcripcion_bruta": texto_llamada,
            "analisis": resultado_json
        }

    except Exception as e:
        print(f" Error en la IA: {e}")
        # Intentar borrar el archivo si hubo error
        if 'temp_audio_path' in locals() and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
        return {"error": f"Fallo en el análisis: {str(e)}"}

# ==========================================
# MODELOS DE DATOS (PYDANTIC) PARA EL CRM
# ==========================================
class GestionCreate(BaseModel):
    numero_documento: str
    tipo_contacto: str
    estado_promesa: str
    observacion: str
    fecha_acuerdo: Optional[str] = None
    monto_acuerdo: Optional[float] = None
    fecha_alerta: Optional[str] = None  # Para programar la próxima llamada (HU03)

class ContactoCreate(BaseModel):
    numero_documento: str
    telefono: Optional[str] = None
    correo: Optional[str] = None

# ----------------------------------------------------
# HU01: BUSCADOR UNIVERSAL (Cédula, Nombre, Obligación)
# ----------------------------------------------------
@app.get("/buscar_universal/{texto_busqueda}")
def buscar_universal(texto_busqueda: str):
    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        # Busca coincidencias en cédula, nombre o número de obligación
        query = """
            SELECT DISTINCT d.numero_documento, d.nombres, d.decil, d.score_comportamiento
            FROM deudores d
            LEFT JOIN obligaciones o ON d.deudor_id = o.deudor_id
            WHERE d.numero_documento ILIKE %s 
               OR d.nombres ILIKE %s 
               OR o.numero_obligacion ILIKE %s
            LIMIT 10;
        """
        param = f"%{texto_busqueda}%"
        cur.execute(query, (param, param, param))
        resultados = cur.fetchall()
        
        clientes = []
        for r in resultados:
            clientes.append({
                "cedula": r[0],
                "nombre": r[1],
                "decil": r[2],
                "score": r[3]
            })
        return {"resultados": clientes}
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

# ----------------------------------------------------
# HU02: ACTUALIZACIÓN DE DATOS (Nuevos teléfonos)
# ----------------------------------------------------
@app.post("/agregar_contacto")
def agregar_contacto(contacto: ContactoCreate):
    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO contactos_adicionales (numero_documento, telefono, correo)
            VALUES (%s, %s, %s)
            RETURNING id;
        """, (contacto.numero_documento, contacto.telefono, contacto.correo))
        conn.commit()
        return {"mensaje": "Contacto guardado correctamente", "id": cur.fetchone()[0]}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

# ----------------------------------------------------
# HU07 y HU04: ESTADÍSTICAS Y PERFIL DEL ASESOR
# ----------------------------------------------------
@app.get("/estadisticas_hoy")
def estadisticas_hoy():
    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        # Cuenta cuántas gestiones se hicieron HOY
        cur.execute("SELECT COUNT(*) FROM gestiones WHERE DATE(fecha_gestion) = CURRENT_DATE;")
        gestiones_hoy = cur.fetchone()[0]
        
        # Suma el dinero prometido HOY
        cur.execute("SELECT COALESCE(SUM(monto_acuerdo), 0) FROM gestiones WHERE DATE(fecha_gestion) = CURRENT_DATE;")
        dinero_prometido = cur.fetchone()[0]
        
        return {
            "gestiones_realizadas_hoy": gestiones_hoy,
            "dinero_prometido_hoy": float(dinero_prometido)
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()


@app.delete("/eliminar_alerta/{alerta_id}")
def eliminar_alerta(alerta_id: int):
    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM gestiones_bitacora WHERE id = %s", (alerta_id,))
        conn.commit()
        return {"mensaje": "Alerta eliminada correctamente"}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/buscar_cliente/{cedula}")
def buscar_cliente(cedula: str):
    try:
        conn = get_pg_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM gestiones_bitacora WHERE cedula_cliente = %s ORDER BY id DESC LIMIT 1", (cedula,))
        res = cur.fetchone()
        cur.close()
        conn.close()
        return res if res else {}
    except Exception as e:
        return {"error": str(e)}


@app.post("/registrar_telefono")
async def registrar_telefono(data: dict):
    try:
        conn = get_pg_connection()
        cur = conn.cursor()
        
        # Guardamos y pedimos que nos devuelva el ID generado
        query = """
            INSERT INTO telefonos_clientes (cedula_cliente, numero, estado, descripcion)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """
        cur.execute(query, (
            data.get('cedula'),
            data.get('numero'),
            data.get('estado'),
            data.get('descripcion')
        ))
        
        nuevo_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return {"status": "success", "nuevo_id": nuevo_id}
    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/telefonos/{cedula}")
def obtener_telefonos(cedula: str):
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, numero, estado, descripcion, fecha_registro
            FROM telefonos_clientes
            WHERE cedula_cliente = %s
            ORDER BY fecha_registro DESC
        """, (cedula,))
        telefonos = cur.fetchall()
        return {"telefonos": telefonos}
    except Exception as e:
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()


@app.get("/obtener_reporte_general")
async def obtener_reporte_general():
    try:
        conn = get_pg_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT 
                d.numero_documento as cedula,
                d.nombres as nombre,
                o.numero_obligacion as credito,
                o.saldo_total as saldo,
                o.dias_mora as dias,
                o.estado
            FROM deudores d
            JOIN obligaciones o ON d.deudor_id = o.deudor_id
            LIMIT 300
        """
        cur.execute(query)
        rows = cur.fetchall()
        datos = []
        for row in rows:
            datos.append({
                "cedula": row["cedula"],
                "nombre": row["nombre"],
                "rol": "TITULAR",
                "credito": row["credito"],
                "saldo": f"{float(row['saldo']):,.0f}" if row['saldo'] else "0",
                "dias": row["dias"],
                "estado": row["estado"],
                "subestado": "SIN ASIGNAR"
            })
        cur.close()
        conn.close()
        return {"status": "success", "datos": datos}
    except Exception as e:
        print(f"Error en el JOIN: {e}")
        return {"status": "error", "message": str(e)}


# GUARDAR GESTIÓN (El botón azul de tu interfaz)
@app.post("/registrar_gestion_completa")
async def registrar_gestion_completa(data: dict):
    try:
        conn = get_pg_connection()
        cur = conn.cursor()
        query = """
            INSERT INTO gestiones_bitacora 
            (cedula_cliente, eps, bienes, rues, observacion, telefono, estado_cliente, estado, subestado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """
        cur.execute(query, (
            data.get('cedula'),
            data.get('eps'),
            data.get('bienes'),
            data.get('rues'),
            data.get('comentario'),
            data.get('telefono'),
            data.get('estado_cliente', 'Activo'),
            data.get('estado', ''),
            data.get('subestado', '')
        ))
        new_id = cur.fetchone()[0]
        conn.commit()
        return {"status": "success", "message": "Bitácora registrada", "id": new_id}
    except Exception as e:
        print(f"Error al guardar: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()


@app.get("/bitacora/{cedula}")
async def obtener_bitacora(cedula: str):
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        query = """
            SELECT id, eps, bienes, rues, observacion, telefono, estado_cliente, estado, subestado, fecha_actualizacion
            FROM gestiones_bitacora
            WHERE cedula_cliente = %s
            ORDER BY fecha_actualizacion DESC;
        """
        cur.execute(query, (cedula,))
        registros = cur.fetchall()
        return {"status": "success", "bitacora": registros}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()


class AcuerdoCompleto(BaseModel):
    cedula_cliente: str
    rol: str
    nombre_rol: str
    monto_negociado: float
    cuotas: int
    fecha_inicio: str
    asesor_id: int
    comentario: Optional[str] = None


@app.post("/crear_acuerdo_completo")
async def crear_acuerdo_completo(acuerdo: AcuerdoCompleto):
    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        # Obtener deudor_id
        cur.execute("SELECT deudor_id FROM deudores WHERE numero_documento = %s", (acuerdo.cedula_cliente,))
        res = cur.fetchone()
        if not res:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        deudor_id = res[0]

        valor_cuota = acuerdo.monto_negociado / acuerdo.cuotas

        # Insertar acuerdo
        cur.execute("""
            INSERT INTO acuerdos_pago 
            (deudor_id, rol, nombre_rol, monto_acordado, numero_cuotas, valor_cuota, fecha_primera_cuota, asesor_id, comentario_asesor)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING acuerdo_id;
        """, (deudor_id, acuerdo.rol, acuerdo.nombre_rol, acuerdo.monto_negociado,
              acuerdo.cuotas, valor_cuota, acuerdo.fecha_inicio, acuerdo.asesor_id, acuerdo.comentario))
        nuevo_id = cur.fetchone()[0]

        # 🔥 NUEVO: Registrar automáticamente un pago asociado al acuerdo
        cur.execute("""
            INSERT INTO pagos (cedula_cliente, monto_pago, fecha_pago, tipo_pago, referencia, observacion, asesor_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            acuerdo.cedula_cliente,
            acuerdo.monto_negociado,
            acuerdo.fecha_inicio,
            "ACUERDO",
            f"ACUERDO_{nuevo_id}",
            f"Pago asociado al acuerdo #{nuevo_id} - {acuerdo.comentario}",
            acuerdo.asesor_id
        ))

        conn.commit()
        return {"status": "success", "message": "Acuerdo y pago registrados", "id": nuevo_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()


@app.get("/acuerdos/{cedula}")
async def obtener_acuerdos(cedula: str):
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT 
                a.acuerdo_id, 
                a.rol, 
                a.nombre_rol, 
                a.monto_acordado, 
                a.numero_cuotas,
                a.valor_cuota, 
                a.fecha_primera_cuota, 
                a.asesor_id, 
                a.comentario_asesor as comentario, 
                a.fecha_registro,
                d.nombres as deudor_nombre,
                d.asesor_nombre as asesor_nombre   -- <-- NUEVO: nombre del asesor asignado al deudor
            FROM acuerdos_pago a
            JOIN deudores d ON a.deudor_id = d.deudor_id
            WHERE d.numero_documento = %s
            ORDER BY a.fecha_registro DESC;
        """, (cedula,))
        acuerdos = cur.fetchall()
        return {"status": "success", "acuerdos": acuerdos}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/resumen/{cedula}")
async def obtener_resumen(cedula: str):
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # 1. Datos del deudor y saldo
        cur.execute("""
            SELECT d.numero_documento, d.nombres, 
                   o.saldo_total, o.saldo_capital
            FROM deudores d
            LEFT JOIN obligaciones o ON d.deudor_id = o.deudor_id
            WHERE d.numero_documento = %s
            LIMIT 1
        """, (cedula,))
        deudor = cur.fetchone()
        if not deudor:
            return {"status": "error", "message": "Cliente no encontrado"}

        # 2. Último acuerdo
        cur.execute("""
            SELECT rol, monto_acordado, numero_cuotas
            FROM acuerdos_pago a
            JOIN deudores d ON a.deudor_id = d.deudor_id
            WHERE d.numero_documento = %s
            ORDER BY a.fecha_registro DESC
            LIMIT 1
        """, (cedula,))
        ultimo_acuerdo = cur.fetchone()

        # 3. Última gestión (para canal y contacto)
        cur.execute("""
            SELECT tipo_contacto as canal, estado_promesa
            FROM gestiones
            WHERE numero_documento = %s
            ORDER BY fecha_gestion DESC
            LIMIT 1
        """, (cedula,))
        ultima_gestion = cur.fetchone()

        # 4. Último teléfono de la bitácora de investigación
        cur.execute("""
            SELECT telefono
            FROM gestiones_bitacora
            WHERE cedula_cliente = %s
            ORDER BY fecha_actualizacion DESC
            LIMIT 1
        """, (cedula,))
        ultimo_telefono = cur.fetchone()

        # 5. Contadores
        cur.execute("SELECT COUNT(*) FROM gestiones WHERE numero_documento = %s", (cedula,))
        total_gestiones = cur.fetchone()['count']
        cur.execute("SELECT COUNT(*) FROM telefonos_clientes WHERE cedula_cliente = %s", (cedula,))
        total_telefonos = cur.fetchone()['count']
        cur.execute("""
            SELECT COUNT(*) FROM acuerdos_pago a
            JOIN deudores d ON a.deudor_id = d.deudor_id
            WHERE d.numero_documento = %s
        """, (cedula,))
        total_acuerdos = cur.fetchone()['count']

        # 6. Listas para las pestañas (últimas 5)
        cur.execute("""
            SELECT tipo_contacto as canal, observacion, estado_promesa, fecha_gestion
            FROM gestiones
            WHERE numero_documento = %s
            ORDER BY fecha_gestion DESC
            LIMIT 5
        """, (cedula,))
        ultimas_gestiones = cur.fetchall()

        cur.execute("""
            SELECT numero, estado, descripcion, fecha_registro
            FROM telefonos_clientes
            WHERE cedula_cliente = %s
            ORDER BY fecha_registro DESC
            LIMIT 5
        """, (cedula,))
        ultimos_telefonos = cur.fetchall()

        cur.execute("""
            SELECT a.rol, a.nombre_rol, a.monto_acordado, a.numero_cuotas, a.fecha_primera_cuota, a.fecha_registro
            FROM acuerdos_pago a
            JOIN deudores d ON a.deudor_id = d.deudor_id
            WHERE d.numero_documento = %s
            ORDER BY a.fecha_registro DESC
            LIMIT 5
        """, (cedula,))
        ultimos_acuerdos = cur.fetchall()

        cur.execute("""
            SELECT estado, subestado, observacion, fecha_actualizacion
            FROM gestiones_bitacora
            WHERE cedula_cliente = %s
            ORDER BY fecha_actualizacion DESC
            LIMIT 5
        """, (cedula,))
        historial_estados = cur.fetchall()

        # Cálculos
        saldo_capital = deudor.get('saldo_capital') or 0
        saldo_total = deudor.get('saldo_total') or 0
        valor_credito = saldo_total
        rol = "TITULAR"
        monto_negociado = 0
        cuotas = 0
        if ultimo_acuerdo:
            rol = ultimo_acuerdo['rol'] or "TITULAR"
            monto_negociado = ultimo_acuerdo['monto_acordado'] or 0
            cuotas = ultimo_acuerdo['numero_cuotas'] or 0

        valor_condonado = max(0, valor_credito - monto_negociado) if monto_negociado > 0 else 0

        contacto = "NO"
        if ultima_gestion:
            estado = ultima_gestion['estado_promesa']
            if estado in ['Promesa de pago', 'Acuerdo Cerrado', 'Contacto efectivo']:
                contacto = "SI"

        tiene_acuerdo = "SI" if ultimo_acuerdo else "NO"
        canal = ultima_gestion['canal'] if ultima_gestion else ""
        telefono = ultimo_telefono['telefono'] if ultimo_telefono else ""

        return {
            "status": "success",
            "data": {
                "rol": rol,
                "cc": deudor['numero_documento'],
                "nombre": deudor['nombres'],
                "canal": canal,
                "telefono": telefono,
                "contacto": contacto,
                "acuerdo": tiene_acuerdo,
                "cuotas": cuotas,
                "valor_credito": valor_credito,
                "valor_negociado": monto_negociado,
                "valor_condonado": valor_condonado,
                "saldo_capital": saldo_capital,
                "saldo_total": saldo_total,
                "total_gestiones": total_gestiones,
                "total_telefonos": total_telefonos,
                "total_acuerdos": total_acuerdos,
                "ultimas_gestiones": ultimas_gestiones,
                "ultimos_telefonos": ultimos_telefonos,
                "ultimos_acuerdos": ultimos_acuerdos,
                "historial_estados": historial_estados
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()

@app.get("/acuerdos_mensuales")
async def acuerdos_mensuales(mes: str = None, operacion: str = None, cedula: str = None):
    """
    Retorna acuerdos filtrados por mes (YYYY-MM), número de operación o cédula.
    """
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        query = """
            SELECT 
                a.acuerdo_id,
                d.numero_documento as cedula,
                d.nombres as nombre,
                o.numero_obligacion,
                a.monto_acordado,
                a.numero_cuotas,
                a.fecha_primera_cuota as fecha_acuerdo,
                a.asesor_id,
                ase.nombre_completo as asesor_nombre
            FROM acuerdos_pago a
            JOIN deudores d ON a.deudor_id = d.deudor_id
            LEFT JOIN obligaciones o ON d.deudor_id = o.deudor_id
            LEFT JOIN asesor ase ON a.asesor_id = ase.asesor_id
            WHERE 1=1
        """
        params = []

        # Filtro por mes (fecha_primera_cuota)
        if mes:
            query += " AND DATE_TRUNC('month', a.fecha_primera_cuota) = %s::date"
            params.append(mes + '-01')

        # Filtro por número de operación (puede venir con guión)
        if operacion:
            query += " AND o.numero_obligacion ILIKE %s"
            params.append(f"%{operacion}%")

        # Filtro por cédula
        if cedula:
            query += " AND d.numero_documento ILIKE %s"
            params.append(f"%{cedula}%")

        query += " ORDER BY a.fecha_primera_cuota DESC"

        cur.execute(query, params)
        acuerdos = cur.fetchall()
        return {"status": "success", "acuerdos": acuerdos}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()


@app.post("/generar_reporte_mensual")
async def generar_reporte_mensual(mes: str):
    """
    Genera y guarda el reporte mensual para el mes indicado (formato YYYY-MM).
    """
    try:
        # Validar formato del mes
        mes_date = datetime.strptime(mes, "%Y-%m").date()
        mes_inicio = mes_date.replace(day=1)
        mes_fin = mes_inicio + relativedelta(months=1)

        conn = get_pg_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Totales globales
        cur.execute("""
            SELECT COUNT(*) as total_gestiones
            FROM gestiones
            WHERE fecha_gestion >= %s AND fecha_gestion < %s
        """, (mes_inicio, mes_fin))
        total_gestiones = cur.fetchone()['total_gestiones']

        cur.execute("""
            SELECT COUNT(*) as total_acuerdos
            FROM acuerdos_pago
            WHERE fecha_primera_cuota >= %s AND fecha_primera_cuota < %s
        """, (mes_inicio, mes_fin))
        total_acuerdos = cur.fetchone()['total_acuerdos']

        # Como no tenemos tabla pagos, establecemos total_pagos = 0
        total_pagos = 0

        # 2. Datos por asesor
        cur.execute("""
            SELECT asesor_id, nombre_completo
            FROM asesor
            WHERE asesor_id IN (
                SELECT DISTINCT asesor_id FROM gestiones WHERE fecha_gestion >= %s AND fecha_gestion < %s
                UNION
                SELECT DISTINCT asesor_id FROM acuerdos_pago WHERE fecha_primera_cuota >= %s AND fecha_primera_cuota < %s
            )
        """, (mes_inicio, mes_fin, mes_inicio, mes_fin))
        asesores = cur.fetchall()

        datos_asesores = []
        for a in asesores:
            # Gestiones del asesor
            cur.execute("""
                SELECT COUNT(*) as cnt
                FROM gestiones
                WHERE asesor_id = %s AND fecha_gestion >= %s AND fecha_gestion < %s
            """, (a['asesor_id'], mes_inicio, mes_fin))
            cnt_gestiones = cur.fetchone()['cnt']

            # Acuerdos del asesor
            cur.execute("""
                SELECT COUNT(*) as cnt, COALESCE(SUM(monto_acordado), 0) as monto
                FROM acuerdos_pago
                WHERE asesor_id = %s AND fecha_primera_cuota >= %s AND fecha_primera_cuota < %s
            """, (a['asesor_id'], mes_inicio, mes_fin))
            row = cur.fetchone()
            cnt_acuerdos = row['cnt']
            monto_acuerdos = row['monto']

            datos_asesores.append({
                'asesor_id': a['asesor_id'],
                'asesor_nombre': a['nombre_completo'],
                'total_gestiones': cnt_gestiones,
                'total_acuerdos': cnt_acuerdos,
                'monto_acuerdos': monto_acuerdos
            })

        # Calcular posiciones
        # Gestiones
        datos_asesores.sort(key=lambda x: x['total_gestiones'], reverse=True)
        for i, d in enumerate(datos_asesores, 1):
            d['posicion_gestiones'] = i
        # Acuerdos
        datos_asesores.sort(key=lambda x: x['total_acuerdos'], reverse=True)
        for i, d in enumerate(datos_asesores, 1):
            d['posicion_acuerdos'] = i
        # Monto
        datos_asesores.sort(key=lambda x: x['monto_acuerdos'], reverse=True)
        for i, d in enumerate(datos_asesores, 1):
            d['posicion_monto'] = i

        # 3. Insertar en reportes_mensuales
        cur.execute("""
            INSERT INTO reportes_mensuales (mes, total_gestiones, total_acuerdos, total_pagos)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (mes) DO UPDATE SET
                total_gestiones = EXCLUDED.total_gestiones,
                total_acuerdos = EXCLUDED.total_acuerdos,
                total_pagos = EXCLUDED.total_pagos,
                fecha_generacion = CURRENT_TIMESTAMP
            RETURNING id
        """, (mes_inicio, total_gestiones, total_acuerdos, total_pagos))
        reporte_id = cur.fetchone()['id']

        # Eliminar detalles antiguos
        cur.execute("DELETE FROM reporte_asesor_mensual WHERE reporte_id = %s", (reporte_id,))

        # Insertar detalles por asesor
        for d in datos_asesores:
            cur.execute("""
                INSERT INTO reporte_asesor_mensual
                (reporte_id, asesor_id, asesor_nombre, total_gestiones, total_acuerdos, monto_acuerdos,
                 posicion_gestiones, posicion_acuerdos, posicion_monto)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (reporte_id, d['asesor_id'], d['asesor_nombre'],
                  d['total_gestiones'], d['total_acuerdos'], d['monto_acuerdos'],
                  d['posicion_gestiones'], d['posicion_acuerdos'], d['posicion_monto']))

        conn.commit()
        return {"status": "success", "message": "Reporte generado y guardado", "id": reporte_id}

    except Exception as e:
        print(f"Error generando reporte: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()


@app.get("/reportes_mensuales")
async def obtener_reportes_mensuales(mes: str = None):
    """
    Devuelve los reportes mensuales guardados. Si se pasa 'mes' (YYYY-MM),
    devuelve el reporte de ese mes. Si no, devuelve todos.
    """
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        if mes:
            mes_date = datetime.strptime(mes, "%Y-%m").date()
            mes_inicio = mes_date.replace(day=1)
            cur.execute("SELECT * FROM reportes_mensuales WHERE mes = %s", (mes_inicio,))
            reporte = cur.fetchone()
            if reporte:
                cur.execute("""
                    SELECT * FROM reporte_asesor_mensual
                    WHERE reporte_id = %s
                    ORDER BY posicion_gestiones, posicion_acuerdos, posicion_monto
                """, (reporte['id'],))
                asesores = cur.fetchall()
                return {"status": "success", "reporte": reporte, "asesores": asesores}
            else:
                return {"status": "success", "reporte": None, "asesores": []}
        else:
            cur.execute("SELECT * FROM reportes_mensuales ORDER BY mes DESC")
            reportes = cur.fetchall()
            return {"status": "success", "reportes": reportes}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user['username']}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "user": {"id": user['asesor_id'], "nombre": user['nombre_completo'], "role": user['role']}}


@app.get("/perfil")
async def perfil(current_user: dict = Depends(get_current_user)):
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Obtener datos completos del asesor (incluyendo email y teléfono)
        cur.execute("""
            SELECT asesor_id, nombre_completo, username, role, email, telefono
            FROM asesor
            WHERE asesor_id = %s
        """, (current_user['asesor_id'],))
        user_data = cur.fetchone()

        hoy = datetime.now().date()
        cur.execute("""
            SELECT id, tipo_contacto as canal, estado_promesa, observacion, fecha_gestion
            FROM gestiones
            WHERE asesor_id = %s AND fecha_gestion::date = %s
            ORDER BY fecha_gestion DESC
        """, (current_user['asesor_id'], hoy))
        gestiones_hoy = cur.fetchall()

        cur.execute("""
            SELECT acuerdo_id, rol, nombre_rol, monto_acordado, numero_cuotas, fecha_primera_cuota
            FROM acuerdos_pago
            WHERE asesor_id = %s AND fecha_primera_cuota = %s
            ORDER BY fecha_primera_cuota DESC
        """, (current_user['asesor_id'], hoy))
        acuerdos_hoy = cur.fetchall()

        return {
            "user": user_data,
            "gestiones_hoy": gestiones_hoy,
            "acuerdos_hoy": acuerdos_hoy
        }
    finally:
        cur.close()
        conn.close()


class PerfilUpdate(BaseModel):
    email: Optional[str] = None
    telefono: Optional[str] = None

@app.put("/perfil")
async def actualizar_perfil(data: PerfilUpdate, current_user: dict = Depends(get_current_user)):
    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE asesor SET email = COALESCE(%s, email), telefono = COALESCE(%s, telefono)
            WHERE asesor_id = %s
        """, (data.email, data.telefono, current_user['asesor_id']))
        conn.commit()
        return {"status": "success", "message": "Perfil actualizado"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

class PagoCreate(BaseModel):
    cedula_cliente: str
    monto_pago: float
    fecha_pago: str
    tipo_pago: str = "ABONO"
    referencia: Optional[str] = None
    observacion: Optional[str] = None
    asesor_id: int

@app.post("/registrar_pago")
async def registrar_pago(pago: PagoCreate):
    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO pagos (cedula_cliente, monto_pago, fecha_pago, tipo_pago, referencia, observacion, asesor_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (pago.cedula_cliente, pago.monto_pago, pago.fecha_pago, pago.tipo_pago, pago.referencia, pago.observacion, pago.asesor_id))
        conn.commit()
        return {"status": "success", "message": "Pago registrado"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.get("/historial_pagos_asesor/{asesor_id}")
async def historial_pagos_asesor(asesor_id: int):
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, cedula_cliente, monto_pago, fecha_pago, tipo_pago, referencia, observacion, fecha_registro
            FROM pagos
            WHERE asesor_id = %s
            ORDER BY fecha_pago DESC, fecha_registro DESC
        """, (asesor_id,))
        pagos = cur.fetchall()
        return {"status": "success", "pagos": pagos}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()


@app.get("/pagos_cliente/{cedula}")
async def obtener_pagos_cliente(cedula: str):
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT id, monto_pago, fecha_pago, tipo_pago, referencia, observacion, fecha_registro
            FROM pagos
            WHERE cedula_cliente = %s
            ORDER BY fecha_pago DESC, fecha_registro DESC
        """, (cedula,))
        pagos = cur.fetchall()
        return {"status": "success", "pagos": pagos}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()


# Obtener lista de asesores para el filtro
@app.get("/asesores")
async def obtener_asesores():
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT asesor_id, nombre_completo FROM asesor WHERE estado = 'ACTIVO'")
        asesores = cur.fetchall()
        return {"status": "success", "asesores": asesores}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()

# Obtener alertas con filtros
@app.get("/alertas")
async def obtener_alertas(asesor_id: Optional[int] = None, fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None):
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        query = "SELECT * FROM alertas WHERE 1=1"
        params = []
        if asesor_id:
            query += " AND asesor_id = %s"
            params.append(asesor_id)
        if fecha_desde:
            query += " AND fecha_alerta >= %s"
            params.append(fecha_desde)
        if fecha_hasta:
            query += " AND fecha_alerta <= %s"
            params.append(fecha_hasta)
        query += " ORDER BY fecha_alerta DESC, hora_alerta DESC"
        cur.execute(query, params)
        alertas = cur.fetchall()
        return {"status": "success", "alertas": alertas}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()

# Crear alerta (opcional, si quieres un formulario independiente)
@app.post("/crear_alerta")
async def crear_alerta(data: dict):
    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO alertas (operacion, asesor_id, asesor_nombre, fecha_alerta, hora_alerta, mensaje)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (data['operacion'], data['asesor_id'], data['asesor_nombre'], data['fecha_alerta'], data['hora_alerta'], data['mensaje']))
        conn.commit()
        return {"status": "success", "message": "Alerta creada"}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()

# Obtener lista de asesores para el filtro
@app.get("/asesores")
async def obtener_asesores():
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT asesor_id, nombre_completo FROM asesor WHERE estado = 'ACTIVO'")
        asesores = cur.fetchall()
        return {"status": "success", "asesores": asesores}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()

# Obtener alertas con filtros
@app.get("/alertas")
async def obtener_alertas(asesor_id: Optional[int] = None, fecha_desde: Optional[str] = None, fecha_hasta: Optional[str] = None):
    conn = get_pg_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        query = "SELECT * FROM alertas WHERE 1=1"
        params = []
        if asesor_id:
            query += " AND asesor_id = %s"
            params.append(asesor_id)
        if fecha_desde:
            query += " AND fecha_alerta >= %s"
            params.append(fecha_desde)
        if fecha_hasta:
            query += " AND fecha_alerta <= %s"
            params.append(fecha_hasta)
        query += " ORDER BY fecha_alerta DESC, hora_alerta DESC"
        cur.execute(query, params)
        alertas = cur.fetchall()
        return {"status": "success", "alertas": alertas}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()

# Crear alerta (opcional, si quieres un formulario independiente)
@app.post("/crear_alerta")
async def crear_alerta(data: dict):
    conn = get_pg_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO alertas (operacion, asesor_id, asesor_nombre, fecha_alerta, hora_alerta, mensaje)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (data['operacion'], data['asesor_id'], data['asesor_nombre'], data['fecha_alerta'], data['hora_alerta'], data['mensaje']))
        conn.commit()
        return {"status": "success", "message": "Alerta creada"}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        cur.close()
        conn.close()


# --- 4. ACTIVACIÓN DEL FRONTEND ---
if os.path.exists(frontend_path):
    print(f"Sistema: Carpeta frontend detectada en {frontend_path}")
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    print(f"Sistema: ERROR - No se encontró la carpeta en {frontend_path}")
