import os
from datetime import date
from functools import wraps

import psycopg2
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_connection, query

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-key-change-me")


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Əvvəlcə sistemə daxil olun.", "error")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Bu əməliyyat üçün admin icazəsi lazımdır.", "error")
            return redirect(url_for("index"))
        return func(*args, **kwargs)
    return wrapper


@app.route("/")
def index():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    location = request.args.get("location", "").strip()
    event_date = request.args.get("date", "").strip()

    events = query("""
        SELECT e.*, c.name AS category,
               COUNT(r.id)::int AS registered
        FROM events e
        JOIN categories c ON c.id = e.category_id
        LEFT JOIN registrations r ON r.event_id = e.id
        WHERE e.title ILIKE %s
          AND (%s = '' OR c.name = %s)
          AND (%s = '' OR e.location ILIKE %s)
          AND (%s = '' OR e.event_date = NULLIF(%s, '')::date)
        GROUP BY e.id, c.name
        ORDER BY e.event_date, e.event_time
    """, (
        f"%{search}%", category, category,
        location, f"%{location}%",
        event_date, event_date
    ), fetchall=True)

    categories = query(
        "SELECT * FROM categories ORDER BY name",
        fetchall=True
    )

    return render_template(
        "index.html",
        events=events,
        categories=categories,
        today=date.today()
    )


@app.route("/register-account", methods=["GET", "POST"])
def register_account():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or len(password) < 8:
            flash("Məlumatları düzgün daxil edin. Şifrə ən azı 8 simvol olmalıdır.", "error")
            return render_template("register.html")

        try:
            user = query("""
                INSERT INTO users (name, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, name, role
            """, (
                name,
                email,
                generate_password_hash(password)
            ), fetchone=True)

            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]

            flash("Hesab uğurla yaradıldı.", "success")
            return redirect(url_for("index"))

        except psycopg2.errors.UniqueViolation:
            flash("Bu e-poçt artıq istifadə olunur.", "error")

        except psycopg2.Error:
            flash("Qeydiyyat zamanı xəta baş verdi.", "error")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = query(
            "SELECT * FROM users WHERE email = %s",
            (email,),
            fetchone=True
        )

        if user and check_password_hash(
            user["password_hash"], password
        ):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]

            return redirect(url_for("index"))

        flash("E-poçt və ya şifrə yanlışdır.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/event/<int:event_id>")
def event_detail(event_id):
    event = query("""
        SELECT e.*, c.name AS category,
               COUNT(r.id)::int AS registered
        FROM events e
        JOIN categories c ON c.id = e.category_id
        LEFT JOIN registrations r ON r.event_id = e.id
        WHERE e.id = %s
        GROUP BY e.id, c.name
    """, (event_id,), fetchone=True)

    if not event:
        flash("Tədbir tapılmadı.", "error")
        return redirect(url_for("index"))

    already_registered = False

    if session.get("user_id"):
        result = query("""
            SELECT id FROM registrations
            WHERE user_id = %s AND event_id = %s
        """, (session["user_id"], event_id), fetchone=True)

        already_registered = result is not None

    return render_template(
        "event_detail.html",
        event=event,
        already_registered=already_registered,
        today=date.today()
    )


@app.route("/register/<int:event_id>", methods=["POST"])
@login_required
def register_event(event_id):
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, event_date, capacity
                FROM events
                WHERE id = %s
                FOR UPDATE
            """, (event_id,))

            event = cursor.fetchone()

            if not event:
                flash("Tədbir tapılmadı.", "error")

            elif event["event_date"] < date.today():
                flash("Keçmiş tədbirə qeydiyyat mümkün deyil.", "error")

            else:
                cursor.execute("""
                    SELECT COUNT(*) AS total
                    FROM registrations
                    WHERE event_id = %s
                """, (event_id,))

                total = cursor.fetchone()["total"]

                if total >= event["capacity"]:
                    flash("Tədbirin iştirakçı limiti dolub.", "error")
                else:
                    cursor.execute("""
                        INSERT INTO registrations (user_id, event_id)
                        VALUES (%s, %s)
                        ON CONFLICT (user_id, event_id) DO NOTHING
                        RETURNING id
                    """, (session["user_id"], event_id))

                    if cursor.fetchone():
                        flash("Tədbirə qeydiyyat tamamlandı.", "success")
                    else:
                        flash("Bu tədbirə artıq qeydiyyatdan keçmisiniz.", "error")

            conn.commit()

    except psycopg2.Error:
        conn.rollback()
        flash("Qeydiyyat zamanı xəta baş verdi.", "error")

    finally:
        conn.close()

    return redirect(url_for("event_detail", event_id=event_id))


@app.route("/cancel/<int:event_id>", methods=["POST"])
@login_required
def cancel_registration(event_id):
    query("""
        DELETE FROM registrations
        WHERE user_id = %s AND event_id = %s
    """, (session["user_id"], event_id))

    flash("Qeydiyyat ləğv edildi.", "success")
    return redirect(url_for("event_detail", event_id=event_id))


@app.route("/my-registrations")
@login_required
def my_registrations():
    events = query("""
        SELECT e.*, c.name AS category
        FROM registrations r
        JOIN events e ON e.id = r.event_id
        JOIN categories c ON c.id = e.category_id
        WHERE r.user_id = %s
        ORDER BY e.event_date, e.event_time
    """, (session["user_id"],), fetchall=True)

    return render_template("my_registrations.html", events=events)


@app.route("/admin")
@login_required
@admin_required
def admin():
    stats = query("""
        SELECT
            (SELECT COUNT(*) FROM events) AS events_count,
            (SELECT COUNT(*) FROM registrations) AS registrations_count,
            (SELECT COUNT(*) FROM users) AS users_count
    """, fetchone=True)

    popular_events = query("""
        SELECT e.title, COUNT(r.id)::int AS total
        FROM events e
        LEFT JOIN registrations r ON r.event_id = e.id
        GROUP BY e.id
        ORDER BY total DESC
        LIMIT 5
    """, fetchall=True)

    categories = query("""
        SELECT c.name, COUNT(e.id)::int AS total
        FROM categories c
        LEFT JOIN events e ON e.category_id = c.id
        GROUP BY c.id
        ORDER BY total DESC
    """, fetchall=True)

    events = query("""
        SELECT e.*, c.name AS category,
               COUNT(r.id)::int AS registered
        FROM events e
        JOIN categories c ON c.id = e.category_id
        LEFT JOIN registrations r ON r.event_id = e.id
        GROUP BY e.id, c.name
        ORDER BY e.event_date
    """, fetchall=True)

    return render_template(
        "admin.html",
        stats=stats,
        popular_events=popular_events,
        categories=categories,
        events=events
    )


@app.route("/admin/events/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_event():
    categories = query(
        "SELECT * FROM categories ORDER BY name",
        fetchall=True
    )

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category_id = request.form.get("category_id", "")
        event_date = request.form.get("event_date", "")
        event_time = request.form.get("event_time", "")
        location = request.form.get("location", "").strip()
        capacity = request.form.get("capacity", "")

        if not all([
            title, description, category_id,
            event_date, event_time, location, capacity
        ]):
            flash("Bütün sahələri doldurun.", "error")

        else:
            try:
                category_id = int(category_id)
                capacity = int(capacity)
                parsed_date = date.fromisoformat(event_date)

                if parsed_date < date.today():
                    raise ValueError("Keçmiş tarix seçilə bilməz.")

                if capacity < 1:
                    raise ValueError("İştirakçı limiti ən azı 1 olmalıdır.")

                query("""
                    INSERT INTO events (
                        title, description, category_id,
                        event_date, event_time, location, capacity
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    title, description, category_id,
                    event_date, event_time, location, capacity
                ))

                flash("Tədbir yaradıldı.", "success")
                return redirect(url_for("admin"))

            except ValueError as error:
                flash(str(error) or "Daxil edilən məlumatlar yanlışdır.", "error")

            except psycopg2.Error:
                flash("Tədbir yadda saxlanılarkən xəta baş verdi.", "error")

    return render_template("event_form.html", categories=categories)


@app.route("/admin/events/<int:event_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_event(event_id):
    query(
        "DELETE FROM events WHERE id = %s",
        (event_id,)
    )

    flash("Tədbir silindi.", "success")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False
    )