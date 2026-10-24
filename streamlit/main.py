
import streamlit as st
import pandas as pd
import hashlib
import hmac
import secrets

from datetime import date, time, datetime

from database import (
    init_db,
    get_connection,
    get_categories,
    list_events,
    save_event,
    delete_event,
    register_for_event,
    cancel_registration,
    get_user_registrations,
    get_statistics,
)

st.set_page_config(
    page_title="Universitet Tədbirləri",
    page_icon="🎓",
    layout="wide",
)

# ==================================================
# VERİLƏNLƏR BAZASI VƏ HESAB SİSTEMİ
# ==================================================

def ensure_auth_schema():
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS full_name TEXT
            """)
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS username TEXT
            """)
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS password_hash TEXT
            """)
            cur.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS role TEXT
                NOT NULL DEFAULT 'participant'
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                users_username_unique
                ON users (LOWER(username))
                WHERE username IS NOT NULL
            """)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)

    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        300000,
    ).hex()

    return f"{salt}${hashed}"


def verify_password(password, stored_hash):
    try:
        salt, expected_hash = stored_hash.split("$", 1)
        actual_hash = hash_password(password, salt).split("$", 1)[1]

        return hmac.compare_digest(actual_hash, expected_hash)

    except (ValueError, AttributeError):
        return False


def create_account(full_name, username, password):
    full_name = full_name.strip()
    username = username.strip().lower()

    if not full_name or not username or not password:
        return False, "Bütün xanaları doldur."

    if len(username) < 3:
        return False, "Login ən azı 3 simvol olmalıdır."

    if len(password) < 8:
        return False, "Parol ən azı 8 simvol olmalıdır."

    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE LOWER(username) = %s",
                (username,),
            )

            if cur.fetchone():
                return False, "Bu login artıq mövcuddur."

            cur.execute("""
                INSERT INTO users
                    (full_name, username, password_hash, role)
                VALUES (%s, %s, %s, 'participant')
                RETURNING id
            """, (
                full_name,
                username,
                hash_password(password),
            ))

            user_id = cur.fetchone()[0]

        conn.commit()
        return True, user_id

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def authenticate_user(username, password):
    username = username.strip().lower()
    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, full_name, username, password_hash, role
                FROM users
                WHERE LOWER(username) = %s
            """, (username,))

            user = cur.fetchone()

        if not user or not user[3]:
            return None

        if not verify_password(password, user[3]):
            return None

        return {
            "id": user[0],
            "full_name": user[1],
            "username": user[2],
            "role": user[4],
        }

    finally:
        conn.close()


def logout():
    for key in (
        "user_id",
        "full_name",
        "username",
        "role",
    ):
        st.session_state.pop(key, None)

    st.rerun()


# ==================================================
# VERİLƏNLƏR BAZASINI HAZIRLA
# ==================================================

try:
    init_db()
    ensure_auth_schema()

except Exception as e:
    st.error("Verilənlər bazası hazırlana bilmədi.")
    st.code(str(e))
    st.stop()


# ==================================================
# SESSİYA
# ==================================================

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "role" not in st.session_state:
    st.session_state.role = "guest"

if "full_name" not in st.session_state:
    st.session_state.full_name = "Qonaq"

if "username" not in st.session_state:
    st.session_state.username = None


# ==================================================
# LOGIN VƏ HESAB YARATMA
# ==================================================

st.title("🎓 Universitet Tədbirlərinin İdarə Edilməsi")

if st.session_state.user_id is None:
    st.caption(
        "Tədbirlərə baxmaq üçün hesab tələb olunmur. "
        "Qeydiyyat və hesab yaratmaq üçün daxil ol."
    )

    login_tab, register_tab = st.tabs(
        ["Daxil ol", "Hesab yarat"]
    )

    with login_tab:
        st.subheader("Hesaba daxil ol")

        with st.form("login_form"):
            login_username = st.text_input(
                "Login",
                key="login_username",
            )
            login_password = st.text_input(
                "Parol",
                type="password",
                key="login_password",
            )

            login_submit = st.form_submit_button(
                "Daxil ol",
                use_container_width=True,
            )

        if login_submit:
            try:
                user = authenticate_user(
                    login_username,
                    login_password,
                )

                if user:
                    st.session_state.user_id = user["id"]
                    st.session_state.full_name = user["full_name"]
                    st.session_state.username = user["username"]
                    st.session_state.role = user["role"]
                    st.rerun()

                else:
                    st.error("Login və ya parol yanlışdır.")

            except Exception as e:
                st.error("Giriş zamanı xəta baş verdi.")
                st.code(str(e))

    with register_tab:
        st.subheader("Yeni hesab yarat")

        with st.form("register_form"):
            new_full_name = st.text_input("Ad və soyad")
            new_username = st.text_input("Login")
            new_password = st.text_input(
                "Parol",
                type="password",
            )
            confirm_password = st.text_input(
                "Parolu təkrar daxil et",
                type="password",
            )

            register_submit = st.form_submit_button(
                "Hesab yarat",
                use_container_width=True,
            )

        if register_submit:
            if new_password != confirm_password:
                st.error("Parollar eyni deyil.")

            else:
                try:
                    success, result = create_account(
                        new_full_name,
                        new_username,
                        new_password,
                    )

                    if success:
                        st.success(
                            "Hesab uğurla yaradıldı. "
                            "İndi login və parol ilə daxil ol."
                        )
                    else:
                        st.error(result)

                except Exception as e:
                    st.error("Hesab yaratmaq mümkün olmadı.")
                    st.code(str(e))

else:
    st.success(
        f"Xoş gəldin, {st.session_state.full_name}!"
    )

    st.caption(f"Rol: {st.session_state.role}")

    if st.button("Hesabdan çıx", key="logout_top"):
        logout()

st.divider()


# ==================================================
# KATEQORİYALAR
# ==================================================

try:
    categories = get_categories()
except Exception as e:
    st.error("Kateqoriyaları yükləmək mümkün olmadı.")
    st.code(str(e))
    st.stop()

category_map = {
    category["name"]: category["id"]
    for category in categories
}

if not category_map:
    st.warning(
        "Kateqoriya tapılmadı. Verilənlər bazasında "
        "kateqoriyaların yaradıldığını yoxla."
    )


# ==================================================
# NAVİQASİYA
# ==================================================

pages = [
    "Tədbirlər",
    "Axtarış və filtrlər",
    "Qeydiyyatlarım",
    "Statistika",
]

if st.session_state.role == "admin":
    pages.append("İdarəetmə paneli")

page = st.sidebar.selectbox(
    "Bölmə seç",
    pages,
)

st.sidebar.write(
    f"İstifadəçi: {st.session_state.full_name}"
)
st.sidebar.write(
    f"Rol: {st.session_state.role}"
)

if st.sidebar.button("Çıxış et", key="sidebar_logout"):
    logout()


# ==================================================
# TƏDBİRLƏR
# ==================================================

if page == "Tədbirlər":
    st.subheader("📅 Tədbirlərin siyahısı")

    events = list_events()

    if not events:
        st.info("Hələ heç bir tədbir yaradılmayıb.")

    else:
        upcoming, past = st.tabs(
            ["Gələcək tədbirlər", "Keçmiş tədbirlər"]
        )

        with upcoming:
            future_events = [
                event for event in events
                if event["event_date"] >= date.today()
            ]

            if not future_events:
                st.info("Gələcək tədbir yoxdur.")

            for event in future_events:
                with st.container(border=True):
                    st.subheader(event["title"])
                    st.write(event.get("description", ""))

                    st.caption(
                        f"Kateqoriya: {event.get('category', '—')} | "
                        f"Tarix: {event['event_date']} | "
                        f"Saat: {event.get('event_time', '—')} | "
                        f"Yer: {event.get('location', '—')}"
                    )

                    count = event.get("registered_count", 0)
                    capacity = event.get("capacity", 1)

                    if capacity and capacity > 0:
                        st.progress(
                            min(count / capacity, 1.0)
                        )

                    st.write(
                        f"İştirakçılar: {count}/{capacity}"
                    )

                    if st.session_state.user_id is not None:
                        if st.button(
                            "Qeydiyyatdan keç",
                            key=f"register_{event['id']}",
                            disabled=count >= capacity,
                        ):
                            try:
                                success, message = register_for_event(
                                    st.session_state.user_id,
                                    event["id"],
                                )

                                if success:
                                    st.success(message)
                                    st.rerun()
                                else:
                                    st.warning(message)

                            except Exception as e:
                                st.error("Qeydiyyat alınmadı.")
                                st.code(str(e))
                    else:
                        st.info(
                            "Qeydiyyatdan keçmək üçün "
                            "hesabına daxil ol."
                        )

        with past:
            past_events = [
                event for event in events
                if event["event_date"] < date.today()
            ]

            if not past_events:
                st.info("Keçmiş tədbir yoxdur.")

            for event in past_events:
                with st.container(border=True):
                    st.subheader(event["title"])
                    st.caption(
                        f"{event['event_date']} | "
                        f"{event.get('location', '—')} | "
                        f"{event.get('category', '—')}"
                    )


# ==================================================
# AXTARIŞ VƏ FİLTRLƏR
# ==================================================

elif page == "Axtarış və filtrlər":
    st.subheader("🔎 Tədbir axtarışı")

    col1, col2 = st.columns(2)

    with col1:
        search = st.text_input("Tədbirin adı")

        category_name = st.selectbox(
            "Kateqoriya",
            ["Hamısı"] + list(category_map.keys()),
        )

    with col2:
        location = st.text_input("Keçirilmə yeri")

        date_from = st.date_input(
            "Başlanğıc tarixi",
            value=None,
            key="search_date_from",
        )

        date_to = st.date_input(
            "Son tarix",
            value=None,
            key="search_date_to",
        )

    category_id = (
        category_map.get(category_name)
        if category_name != "Hamısı"
        else None
    )

    if date_from and date_to and date_from > date_to:
        st.error(
            "Başlanğıc tarixi son tarixdən sonra ola bilməz."
        )

    else:
        events = list_events(
            search=search,
            category_id=category_id,
            location=location,
            date_from=date_from,
            date_to=date_to,
        )

        if not events:
            st.info("Axtarışa uyğun tədbir tapılmadı.")

        for event in events:
            with st.container(border=True):
                st.subheader(event["title"])
                st.write(event.get("description", ""))

                st.caption(
                    f"{event.get('category', '—')} | "
                    f"{event['event_date']} | "
                    f"{event.get('location', '—')}"
                )

                count = event.get("registered_count", 0)
                capacity = event.get("capacity", 1)

                st.write(
                    f"Qeydiyyat: {count} / {capacity}"
                )

                if st.session_state.user_id is not None:
                    if st.button(
                        "Qeydiyyatdan keç",
                        key=f"search_register_{event['id']}",
                        disabled=count >= capacity,
                    ):
                        try:
                            success, message = register_for_event(
                                st.session_state.user_id,
                                event["id"],
                            )

                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.warning(message)

                        except Exception as e:
                            st.error("Qeydiyyat alınmadı.")
                            st.code(str(e))


# ==================================================
# QEYDİYYATLARIM
# ==================================================

elif page == "Qeydiyyatlarım":
    st.subheader("📝 Qeydiyyatlarım")

    if st.session_state.user_id is None:
        st.info(
            "Qeydiyyatlarını görmək üçün hesabına daxil ol."
        )

    else:
        registrations = get_user_registrations(
            st.session_state.user_id
        )

        if not registrations:
            st.info(
                "Heç bir tədbirə qeydiyyatdan keçməmisən."
            )

        for registration in registrations:
            with st.container(border=True):
                st.write(
                    f"**{registration['title']}**"
                )

                st.caption(
                    f"{registration['event_date']} | "
                    f"{registration.get('event_time', '—')} | "
                    f"{registration.get('location', '—')}"
                )

                # Database funksiyası tədbir ID-sini
                # id və ya event_id adı ilə qaytara bilər.
                registration_event_id = registration.get(
                    "event_id",
                    registration.get("id"),
                )

                if st.button(
                    "Qeydiyyatı ləğv et",
                    key=f"cancel_{registration_event_id}",
                ):
                    try:
                        cancelled = cancel_registration(
                            st.session_state.user_id,
                            registration_event_id,
                        )

                        if cancelled is False:
                            st.warning(
                                "Qeydiyyat ləğv edilə bilmədi."
                            )
                        else:
                            st.success(
                                "Qeydiyyat ləğv edildi."
                            )
                            st.rerun()

                    except Exception as e:
                        st.error("Qeydiyyatı ləğv etmək olmadı.")
                        st.code(str(e))


# ==================================================
# STATİSTİKA
# ==================================================

elif page == "Statistika":
    st.subheader("📊 Tədbirlərin statistikası")

    try:
        overview, popular, by_category = get_statistics()

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Ümumi tədbirlər",
            overview.get(
                "event_count",
                overview.get("total_events", 0),
            ),
        )

        col2.metric(
            "Ümumi qeydiyyatlar",
            overview.get(
                "registration_count",
                overview.get("total_registrations", 0),
            ),
        )

        col3.metric(
            "Gələcək tədbirlər",
            overview.get(
                "upcoming_count",
                overview.get("upcoming_events", 0),
            ),
        )

        if popular:
            st.markdown(
                "### Ən çox qeydiyyat olan tədbirlər"
            )

            popular_df = pd.DataFrame(
                [dict(row) for row in popular]
            )

            st.dataframe(
                popular_df,
                use_container_width=True,
                hide_index=True,
            )

        if by_category:
            st.markdown(
                "### Kateqoriyalar üzrə statistika"
            )

            category_df = pd.DataFrame(
                [dict(row) for row in by_category]
            )

            if "event_count" in category_df.columns:
                category_df = category_df.rename(
                    columns={"event_count": "events"}
                )

            if "events" in category_df.columns:
                st.bar_chart(
                    category_df.set_index("category")["events"]
                )

    except Exception as e:
        st.error("Statistikanı yükləmək mümkün olmadı.")
        st.code(str(e))


# ==================================================
# ADMIN PANELİ
# ==================================================

elif page == "İdarəetmə paneli":
    if st.session_state.role != "admin":
        st.error(
            "Bu səhifəyə yalnız admin daxil ola bilər."
        )
        st.stop()

    st.subheader("🛠️ Tədbirlərin idarə edilməsi")

    if not category_map:
        st.error(
            "Əvvəlcə verilənlər bazasına kateqoriyalar əlavə et."
        )
        st.stop()

    with st.form(
        "create_event_form",
        clear_on_submit=True,
    ):
        title = st.text_input("Tədbirin adı")
        description = st.text_area("Təsvir")

        category_name = st.selectbox(
            "Kateqoriya",
            list(category_map.keys()),
        )

        event_date = st.date_input(
            "Tarix",
            min_value=date.today(),
        )

        event_time = st.time_input(
            "Saat",
            value=time(10, 0),
        )

        location = st.text_input("Keçirilmə yeri")

        capacity = st.number_input(
            "Maksimum iştirakçı sayı",
            min_value=1,
            max_value=100000,
            value=50,
        )

        submitted = st.form_submit_button(
            "Tədbir yarat"
        )

        if submitted:
            if not title.strip():
                st.error("Tədbirin adını daxil et.")

            elif not description.strip():
                st.error("Tədbirin təsvirini daxil et.")

            elif not location.strip():
                st.error("Tədbirin yerini daxil et.")

            else:
                try:
                    # Bu çağırış əvvəlki database.py
                    # funksiyasının parametr sırasına uyğundur.
                    # Həmin versiya saatı ayrıca saxlamır.
                    save_event(
                        title=title.strip(),
                        description=description.strip(),
                        category_id=category_map[category_name],
                        event_date=event_date,
                        location=location.strip(),
                        capacity=int(capacity),
                    )

                    st.success("Tədbir yaradıldı.")
                    st.rerun()

                except Exception as e:
                    st.error("Tədbir yaradıla bilmədi.")
                    st.code(str(e))

    st.divider()
    st.markdown("### Mövcud tədbirlər")

    try:
        events = list_events()

        if not events:
            st.info(
                "Silinəcək və ya redaktə ediləcək tədbir yoxdur."
            )

        else:
            event_options = {
                f"{event['title']} (ID: {event['id']})": event
                for event in events
            }

            selected_label = st.selectbox(
                "Tədbir seç",
                list(event_options.keys()),
            )

            selected_event = event_options[selected_label]

            if st.button(
                "Seçilmiş tədbiri sil",
                type="secondary",
            ):
                delete_event(selected_event["id"])
                st.success("Tədbir silindi.")
                st.rerun()

    except Exception as e:
        st.error("Tədbirləri yükləmək mümkün olmadı.")
        st.code(str(e))
