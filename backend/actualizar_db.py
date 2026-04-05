import psycopg2
from main import get_pg_connection

def ejecutar_migracion():
    conn = None
    try:
        # Usamos la conexion que ya tienes configurada
        conn = get_pg_connection()
        cur = conn.cursor()
        
        print("Iniciando actualizacion de tabla 'clientes' en cobranzas_db...")
        
        # SQL para añadir las columnas de investigacion tecnica
        sql = """
        ALTER TABLE clientes 
        ADD COLUMN IF NOT EXISTS eps VARCHAR(100),
        ADD COLUMN IF NOT EXISTS bienes TEXT,
        ADD COLUMN IF NOT EXISTS rues VARCHAR(100),
        ADD COLUMN IF NOT EXISTS telefono_nuevo VARCHAR(20),
        ADD COLUMN IF NOT EXISTS estado_cliente VARCHAR(20) DEFAULT 'Activo';
        """
        
        cur.execute(sql)
        conn.commit()
        
        print("Migracion finalizada: Columnas añadidas correctamente.")
        cur.close()
        
    except Exception as e:
        print(f"Error durante la migracion: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    ejecutar_migracion()
