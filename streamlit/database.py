```python
import psycopg2
import streamlit as st


def get_connection():
    return psycopg2.connect(
        st.secrets["DATABASE_URL"]
    )


def init_db():
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            # İstifadəçilər
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role VARCHAR(20) NOT NULL DEFAULT 'user'
                )
            """)

            # Tədbir kateqoriyaları
            cur.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL
                )
            """)

            # Tədbirlər
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    category_id INTEGER REFERENCES categories(id),
                    event_date TIMESTAMP NOT NULL,
                    location VARCHAR(200) NOT NULL,
                    capacity INTEGER NOT NULL CHECK (capacity > 0),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Tədbir iştirakçıları
            cur.execute("""
                CREATE TABLE IF NOT EXISTS registrations (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id)
                        ON DELETE CASCADE,
                    event_id INTEGER REFERENCES events(id)
                        ON DELETE CASCADE,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id, event_id)
                )
            """)

            # İlkin kateqoriyalar
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
    finally:
        conn.close()


def get_categories():
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM categories ORDER BY name"
            )
            return [
                {"id": row[0], "name": row[1]}
                for row in cur.fetchall()
            ]
    finally:
        conn.close()


def list_events(
    search="",
    category_id=None,
    location="",
    event_date=None
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
                    c.name,
                    e.event_date,
                    e.location,
                    e.capacity,
                    COUNT(r.id) AS registered_count
                FROM events e
                LEFT JOIN categories c
                    ON c.id = e.category_id
                LEFT JOIN registrations r
                    ON r.event_id = e.id
                WHERE (
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
                    OR e.event_date::date = %s
                )
                GROUP BY e.id, c.name
                ORDER BY e.event_date
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


def save_event(
    title,
    description,
    category_id,
    event_date,
    location,
    capacity,
    event_id=None
):
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
                """, (
                    title,
                    description,
                    category_id,
                    event_date,
                    location,
                    capacity,
                ))
            else:
                cur.execute("""
                    UPDATE events
                    SET title = %s,
                        description = %s,
                        category_id = %s,
                        event_date = %s,
                        location = %s,
                        capacity = %s
                    WHERE id = %s
                """, (
                    title,
                    description,
                    category_id,
                    event_date,
                    location,
                    capacity,
                    event_id,
                ))

        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_event(event_id):
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM events WHERE id = %s",
                (event_id,)
            )

        conn.commit()
    finally:
        conn.close()


def register_for_event(user_id, event_id):
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            # Eyni istifadəçi eyni tədbirə ikinci dəfə yazıla bilməz.
            cur.execute("""
                SELECT id
                FROM registrations
                WHERE user_id = %s AND event_id = %s
            """, (user_id, event_id))

            if cur.fetchone():
                return False, "Siz artıq bu tədbirə qeydiyyatdan keçmisiniz."

            # Tədbirin mövcudluğunu və boş yerləri yoxla.
            cur.execute("""
                SELECT
                    e.capacity,
                    COUNT(r.id),
                    e.event_date
                FROM events e
                LEFT JOIN registrations r
                    ON r.event_id = e.id
                WHERE e.id = %s
                GROUP BY e.id
                FOR UPDATE OF e
            """, (event_id,))

            event = cur.fetchone()

            if event is None:
                return False, "Tədbir tapılmadı."

            capacity, registered_count, event_date = event

            if event_date < __import__("datetime").datetime.now():
                return False, "Keçmiş tədbirə qeydiyyat mümkün deyil."

            if registered_count >= capacity:
                return False, "Tədbirdə boş yer qalmayıb."

            cur.execute("""
                INSERT INTO registrations (user_id, event_id)
                VALUES (%s, %s)
                ON CONFLICT (user_id, event_id) DO NOTHING
            """, (user_id, event_id))

        conn.commit()
        return True, "Qeydiyyat uğurla tamamlandı."
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cancel_registration(user_id, event_id):
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM registrations
                WHERE user_id = %s AND event_id = %s
            """, (user_id, event_id))

            deleted = cur.rowcount

        conn.commit()
        return deleted > 0
    finally:
        conn.close()


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
                    e.capacity
                FROM registrations r
                JOIN events e ON e.id = r.event_id
                WHERE r.user_id = %s
                ORDER BY e.event_date
            """, (user_id,))

            columns = [
                "id",
                "title",
                "event_date",
                "location",
                "capacity",
            ]

            return [
                dict(zip(columns, row))
                for row in cur.fetchall()
            ]
    finally:
        conn.close()


def get_statistics():
    conn = get_connection()

    try:
        with conn.cursor() as cur:
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

            return {
                "total_events": row[0],
                "total_users": row[1],
                "total_registrations": row[2],
                "upcoming_events": row[3],
            }
    finally:
        conn.close()
```
