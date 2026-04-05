import os
import sys
sys.path.append(os.path.dirname(__file__))
from main import get_password_hash, get_pg_connection

conn = get_pg_connection()
cur = conn.cursor()

usuarios = [
    ('angie.cuellar', 'angie123'),
    ('trinidad.baos', 'trini123'),
    ('tatiana.gaviria', 'tati123'),
    ('admin', 'admin123')
]

for username, password in usuarios:
    hashed = get_password_hash(password)
    cur.execute("UPDATE asesor SET password_hash = %s WHERE username = %s", (hashed, username))

conn.commit()
cur.close()
conn.close()
print("Contraseñas actualizadas")
