import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"


def get_connection():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor
    )


def query(sql, params=None, fetchone=False, fetchall=False):
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())

            if fetchone:
                result = cursor.fetchone()
            elif fetchall:
                result = cursor.fetchall()
            else:
                result = None

        conn.commit()
        return result

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()