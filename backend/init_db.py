import psycopg2
from psycopg2.extras import RealDictCursor

# Configuración de conexión (Mismos datos del docker-compose)
DB_CONFIG = {
    "host": "localhost",
    "database": "cobranzas_db",
    "user": "admin_mujer",
    "password": "password_seguro",
    "port": "5432"
}

def reiniciar_base_datos():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("  Limpiando base de datos antigua...")
    # Borramos tablas si existen para empezar limpio
    cur.execute("DROP TABLE IF EXISTS gestiones CASCADE;")
    cur.execute("DROP TABLE IF EXISTS obligaciones CASCADE;")
    cur.execute("DROP TABLE IF EXISTS deudores CASCADE;")

    print(" Creando tablas maestras...")
    
    # 1. Tabla DEUDORES (Según tu diccionario)
    cur.execute("""
    CREATE TABLE deudores (
        deudor_id BIGSERIAL PRIMARY KEY,
        numero_documento VARCHAR(20) UNIQUE NOT NULL,
        nombres VARCHAR(100) NOT NULL,
        email VARCHAR(150),
        decil INTEGER CHECK (decil BETWEEN 1 AND 10),
        score_comportamiento DECIMAL(5,2)
    );
    """)

    # 2. Tabla OBLIGACIONES (Créditos)
    cur.execute("""
    CREATE TABLE obligaciones (
        obligacion_id BIGSERIAL PRIMARY KEY,
        deudor_id BIGINT REFERENCES deudores(deudor_id),
        numero_obligacion VARCHAR(30) UNIQUE NOT NULL,
        saldo_total DECIMAL(15,2) NOT NULL,
        dias_mora INTEGER,
        estado VARCHAR(20) DEFAULT 'ACTIVA'
    );
    """)

    print(" Sembrando datos de prueba...")
    
    # Insertamos 3 Clientes Ficticios
    cur.execute("""
    INSERT INTO deudores (numero_documento, nombres, email, decil, score_comportamiento) VALUES
    ('1010', 'Juan Perez', 'juan@test.com', 8, 750.00),
    ('2020', 'Maria Gomez', 'maria@test.com', 4, 520.00),
    ('3030', 'Carlos Mora', 'carlos@test.com', 1, 300.00)
    RETURNING deudor_id;
    """)
    
    # Insertamos sus deudas
    # Juan debe 1.5M, Maria debe 500k, Carlos debe 5M
    cur.execute("""
    INSERT INTO obligaciones (deudor_id, numero_obligacion, saldo_total, dias_mora, estado) VALUES
    (1, 'CRED-1001', 1500000.00, 30, 'ACTIVA'),
    (2, 'CRED-2001', 500000.00, 90, 'ACTIVA'),
    (3, 'CRED-3001', 5000000.00, 360, 'CASTIGADA');
    """)

    conn.commit()
    cur.close()
    conn.close()
    print(" ¡Base de datos poblada con éxito!")

if __name__ == "__main__":
    reiniciar_base_datos()
