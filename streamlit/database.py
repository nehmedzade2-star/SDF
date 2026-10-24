import psycopg2
import streamlit as st


# ==================================================
# DATABASE CONNECTION
# ==================================================

def get_connection():
    return psycopg2.connect(
        st.secrets["DATABASE_URL"]
    )


# ==================================================
# INITIALIZE DATABASE
# ==================================================

def init_db():
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role VARCHAR(20) NOT NULL DEFAULT 'user'
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    category_id INTEGER
                        REFERENCES categories(id)
                        ON DELETE SET NULL,
                    event_date TIMESTAMP NOT NULL,
                    location VARCHAR(200) NOT NULL,
                    capacity INTEGER NOT NULL
                        CHECK (capacity > 0),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS registrations (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER
                        REFERENCES users(id)
                        ON DELETE CASCADE,
                    event_id INTEGER
                        REFERENCES events(id)
                        ON DELETE CASCADE,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id, event_id)
                )
            """)

            cur.execute("""
                INSERT INTO categories (name)
                VALUES
                    ('Konfrans'),
                    ('Seminar'),
                    ('Workshop'),
                    ('Digər')
                ON CONFLICT (name) DO NOTHING
            """)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# Backwards compatibility for code that calls create_table()
def create_table():
    init_db()


# ==================================================
# CATEGORIES
# ==================================================

def get_categories():
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name
                FROM categories
                ORDER BY name
            """)

            return [
                {"id": row[0], "name": row[1]}
                for row in cur.fetchall()
            ]

    finally:
        conn.close()


# ==================================================
# LIST AND FILTER EVENTS
# ==================================================

def list_events(
    search="",
    category_id=None,
    location="",
    event_date=None,
    date_from=None,
    date_to=None
):
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            query = """
                SELECT
                    e.id,
                    e.title,
                    e.description,
                    e.category_id,
                    c.name AS category,
                    e.event_date,
                    e.location,
                    e.capacity,
                    COUNT(r.id) AS registered_count
                FROM events e
                LEFT JOIN categories c
                    ON c.id = e.category_id
                LEFT JOIN registrations r
                    ON r.event_id = e.id
                WHERE
                    (
                        %s = ''
                        OR e.title ILIKE %s
                        OR COALESCE(e.description, '') ILIKE %s
                    )
                    AND (
                        %s IS NULL
                        OR e.category_id = %s
                    )
                    AND (
                        %s = ''
                        OR e.location ILIKE %s
                    )
                    AND (
                        %s IS NULL
                        OR e.event_date::date >= %s
                    )
                    AND (
                        %s IS NULL
                        OR e.event_date::date <= %s
                    )
                    AND (
                        %s IS NULL
                        OR e.event_date::date = %s
                    )
                GROUP BY e.id, c.name
                ORDER BY e.event_date ASC
            """

            search_pattern = f"%{search}%"
            location_pattern = f"%{location}%"

            cur.execute(
                query,
                (
                    search,
                    search_pattern,
                    search_pattern,
                    category_id,
                    category_id,
                    location,
                    location_pattern,
                    date_from,
                    date_from,
                    date_to,
                    date_to,
                    event_date,
                    event_date,
                )
            )

            columns = [
                "id",
                "title",
                "description",
                "category_id",
                "category",
                "event_date",
                "location",
                "capacity",
                "registered_count",
            ]

            return [
                dict(zip(columns, row))
                for row in cur.fetchall()
            ]

    finally:
        conn.close()


# ==================================================
# CREATE OR UPDATE EVENT
# ==================================================

def save_event(
    title,
    description,
    category_id,
    event_date,
    location,
    capacity,
    event_id=None
):
    if not title or not title.strip():
        raise ValueError("Tədbirin adı boş ola bilməz.")

    if not location or not location.strip():
        raise ValueError("Tədbirin yeri boş ola bilməz.")

    if capacity <= 0:
        raise ValueError("İştirakçı limiti sıfırdan böyük olmalıdır.")

    conn = get_connection()

    try:
        with conn.cursor() as cur:
            if event_id is None:
                cur.execute("""
                    INSERT INTO events (
                        title,
                        description,
                        category_id,
                        event_date,
                        location,
                        capacity
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    title.strip(),
                    description,
                    category_id,
                    event_date,
                    location.strip(),
                    capacity,
                ))

            else:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM registrations
                    WHERE event_id = %s
                """, (event_id,))

                registered_count = cur.fetchone()[0]

                if capacity < registered_count:
                    raise ValueError(
                        "İştirakçı limiti mövcud qeydiyyat sayından "
                        "az ola bilməz."
                    )

                cur.execute("""
                    UPDATE events
                    SET title = %s,
                        description = %s,
                        category_id = %s,
                        event_date = %s,
                        location = %s,
                        capacity = %s
                    WHERE id = %s
                    RETURNING id
                """, (
                    title.strip(),
                    description,
                    category_id,
                    event_date,
                    location.strip(),
                    capacity,
                    event_id,
                ))

            if cur.fetchone() is None:
                raise ValueError("Tədbir tapılmadı.")

        conn.commit()
        return True

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ==================================================
# DELETE EVENT
# ==================================================

def delete_event(event_id):
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM events
                WHERE id = %s
            """, (event_id,))

            deleted = cur.rowcount

        conn.commit()
        return deleted > 0

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ==================================================
# REGISTER FOR EVENT
# ==================================================

def register_for_event(user_id, event_id):
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            # Tədbir sətrini kilidlə ki, paralel qeydiyyatlar
            # iştirakçı limitini aşmasın.
            cur.execute("""
                SELECT
                    capacity,
                    event_date >= CURRENT_TIMESTAMP
                FROM events
                WHERE id = %s
                FOR UPDATE
            """, (event_id,))

            event = cur.fetchone()

            if event is None:
                conn.rollback()
                return False, "Tədbir tapılmadı."

            capacity, is_upcoming = event

            if not is_upcoming:
                conn.rollback()
                return False, "Keçmiş tədbirə qeydiyyat mümkün deyil."

            cur.execute("""
                SELECT id
                FROM users
                WHERE id = %s
            """, (user_id,))

            if cur.fetchone() is None:
                conn.rollback()
                return False, "İstifadəçi tapılmadı."

            cur.execute("""
                SELECT id
                FROM registrations
                WHERE user_id = %s AND event_id = %s
            """, (user_id, event_id))

            if cur.fetchone():
                conn.rollback()
                return False, "Siz artıq bu tədbirə qeydiyyatdan keçmisiniz."

            cur.execute("""
                SELECT COUNT(*)
                FROM registrations
                WHERE event_id = %s
            """, (event_id,))

            registered_count = cur.fetchone()[0]

            if registered_count >= capacity:
                conn.rollback()
                return False, "Tədbirdə boş yer qalmayıb."

            cur.execute("""
                INSERT INTO registrations (user_id, event_id)
                VALUES (%s, %s)
                ON CONFLICT (user_id, event_id) DO NOTHING
            """, (user_id, event_id))

            if cur.rowcount == 0:
                conn.rollback()
                return False, "Siz artıq bu tədbirə qeydiyyatdan keçmisiniz."

        conn.commit()
        return True, "Qeydiyyat uğurla tamamlandı."

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ==================================================
# CANCEL REGISTRATION
# ==================================================

def cancel_registration(user_id, event_id):
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM registrations
                WHERE user_id = %s
                  AND event_id = %s
            """, (user_id, event_id))

            deleted = cur.rowcount

        conn.commit()
        return deleted > 0

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ==================================================
# USER REGISTRATIONS
# ==================================================

def get_user_registrations(user_id):
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    e.id,
                    e.title,
                    e.event_date,
                    e.location,
                    e.capacity,
                    c.name AS category,
                    (
                        SELECT COUNT(*)
                        FROM registrations r2
                        WHERE r2.event_id = e.id
                    ) AS registered_count
                FROM registrations r
                JOIN events e
                    ON e.id = r.event_id
                LEFT JOIN categories c
                    ON c.id = e.category_id
                WHERE r.user_id = %s
                ORDER BY e.event_date ASC
            """, (user_id,))

            columns = [
                "id",
                "title",
                "event_date",
                "location",
                "capacity",
                "category",
                "registered_count",
            ]

            return [
                dict(zip(columns, row))
                for row in cur.fetchall()
            ]

    finally:
        conn.close()


# ==================================================
# STATISTICS
# Returns exactly 3 values:
# overview, popular, by_category
# ==================================================

def get_statistics():
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            # Ümumi statistika
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM events),
                    (SELECT COUNT(*) FROM users),
                    (SELECT COUNT(*) FROM registrations),
                    (
                        SELECT COUNT(*)
                        FROM events
                        WHERE event_date >= CURRENT_TIMESTAMP
                    )
            """)

            row = cur.fetchone()

            overview = {
                "event_count": row[0],
                "total_events": row[0],
                "user_count": row[1],
                "total_users": row[1],
                "registration_count": row[2],
                "total_registrations": row[2],
                "upcoming_events": row[3],
            }

            # Ən populyar tədbirlər
            cur.execute("""
                SELECT
                    e.id,
                    e.title,
                    COUNT(r.id) AS registered_count
                FROM events e
                LEFT JOIN registrations r
                    ON r.event_id = e.id
                GROUP BY e.id, e.title
                ORDER BY registered_count DESC, e.title
                LIMIT 5
            """)

            popular = [
                {
                    "id": row[0],
                    "title": row[1],
                    "registered_count": row[2],
                }
                for row in cur.fetchall()
            ]

            # Kateqoriyalara görə tədbirlər
            cur.execute("""
                SELECT
                    COALESCE(c.name, 'Kateqoriyasız') AS category,
                    COUNT(e.id) AS event_count
                FROM events e
                LEFT JOIN categories c
                    ON c.id = e.category_id
                GROUP BY c.name
                ORDER BY event_count DESC, category
            """)

            by_category = [
                {
                    "category": row[0],
                    "event_count": row[1],
                }
                for row in cur.fetchall()
            ]

            return overview, popular, by_category

    finally:
        conn.close()
