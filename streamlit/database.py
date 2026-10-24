import psycopg2
import streamlit as st


def get_connection():
    return psycopg2.connect(
        st.secrets["DATABASE_URL"]
    )


def create_table():
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    score NUMERIC(5, 2) NOT NULL
                )
            """)
        conn.commit()
    finally:
        conn.close()


def add_student(name, score):
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO students (name, score) VALUES (%s, %s)",
                (name, score)
            )
        conn.commit()
    finally:
        conn.close()


def get_students():
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, score FROM students ORDER BY id DESC"
            )
            return cur.fetchall()
    finally:
        conn.close()


def delete_student(student_id):
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM students WHERE id = %s",
                (student_id,)
            )
        conn.commit()
    finally:
        conn.close()
