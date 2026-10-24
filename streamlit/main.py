
import streamlit as st
import pandas as pd

from datetime import date, time

from database import (
    init_db,
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
    layout="wide"
)

st.title("🎓 Universitet Tədbirlərinin İdarə Edilməsi")
st.caption(
    "Tədbirləri yarat, axtar, qeydiyyatdan keç "
    "və statistik məlumatları izlə."
)

# Verilənlər bazasını hazırla
try:
    init_db()
except Exception as e:
    st.error("Verilənlər bazasına qoşulmaq mümkün olmadı.")
    st.code(str(e))
    st.stop()

# Kateqoriyalar
categories = get_categories()
category_map = {
    category["name"]: category["id"]
    for category in categories
}

# İstifadəçi sessiyası
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "role" not in st.session_state:
    st.session_state.role = "participant"

if "full_name" not in st.session_state:
    st.session_state.full_name = "Qonaq"

# Naviqasiya
pages = [
    "Tədbirlər",
    "Axtarış və filtrlər",
    "Qeydiyyatlarım",
    "Statistika",
]

if st.session_state.role == "admin":
    pages.append("İdarəetmə paneli")

page = st.sidebar.selectbox("Bölmə seç", pages)

st.sidebar.write(f"İstifadəçi: {st.session_state.full_name}")
st.sidebar.write(f"Rol: {st.session_state.role}")

# --------------------------------------------------
# TƏDBİRLƏR
# --------------------------------------------------
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
                    st.write(event["description"])

                    st.caption(
                        f"Kateqoriya: {event['category']} | "
                        f"Tarix: {event['event_date']} | "
                        f"Saat: {event['event_time']} | "
                        f"Yer: {event['location']}"
                    )

                    count = event["registered_count"]
                    capacity = event["capacity"]

                    st.progress(min(count / capacity, 1.0))
                    st.write(f"İştirakçılar: {count}/{capacity}")

                    if st.session_state.user_id is not None:
                        if st.button(
                            "Qeydiyyatdan keç",
                            key=f"register_{event['id']}",
                            disabled=count >= capacity,
                        ):
                            success, message = register_for_event(
                                st.session_state.user_id,
                                event["id"],
                            )

                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.warning(message)
                    else:
                        st.info(
                            "Qeydiyyatdan keçmək üçün sistemə "
                            "daxil olmalısan."
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
                        f"{event['location']} | "
                        f"{event['category']}"
                    )

# --------------------------------------------------
# AXTARIŞ VƏ FİLTRLƏR
# --------------------------------------------------
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
        st.error("Başlanğıc tarixi son tarixdən sonra ola bilməz.")
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
                st.write(event["description"])
                st.caption(
                    f"{event['category']} | {event['event_date']} | "
                    f"{event['location']}"
                )
                st.write(
                    f"Qeydiyyat: {event['registered_count']} / "
                    f"{event['capacity']}"
                )

                if st.session_state.user_id is not None:
                    if st.button(
                        "Qeydiyyatdan keç",
                        key=f"search_register_{event['id']}",
                        disabled=(
                            event["registered_count"] >= event["capacity"]
                        ),
                    ):
                        success, message = register_for_event(
                            st.session_state.user_id,
                            event["id"],
                        )
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.warning(message)

# --------------------------------------------------
# QEYDİYYATLARIM
# --------------------------------------------------
elif page == "Qeydiyyatlarım":
    st.subheader("📝 Qeydiyyatlarım")

    if st.session_state.user_id is None:
        st.info("Qeydiyyatlarını görmək üçün sistemə daxil ol.")
    else:
        registrations = get_user_registrations(
            st.session_state.user_id
        )

        if not registrations:
            st.info("Heç bir tədbirə qeydiyyatdan keçməmisən.")

        for registration in registrations:
            with st.container(border=True):
                st.write(f"**{registration['title']}**")
                st.caption(
                    f"{registration['event_date']} | "
                    f"{registration['event_time']} | "
                    f"{registration['location']}"
                )

                if st.button(
                    "Qeydiyyatı ləğv et",
                    key=f"cancel_{registration['event_id']}",
                ):
                    cancel_registration(
                        st.session_state.user_id,
                        registration["event_id"],
                    )
                    st.success("Qeydiyyat ləğv edildi.")
                    st.rerun()

# --------------------------------------------------
# STATİSTİKA
# --------------------------------------------------
elif page == "Statistika":
    st.subheader("📊 İdarəetmə statistikası")

    overview, popular, by_category = get_statistics()

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Ümumi tədbirlər",
        overview["event_count"],
    )

    col2.metric(
        "Ümumi qeydiyyatlar",
        overview["registration_count"],
    )

    col3.metric(
        "Gələcək tədbirlər",
        overview["upcoming_count"],
    )

    if popular:
        st.markdown("### Ən çox qeydiyyat olan tədbirlər")

        popular_df = pd.DataFrame(
            [dict(row) for row in popular]
        )

        st.dataframe(
            popular_df,
            use_container_width=True,
            hide_index=True,
        )

    if by_category:
        st.markdown("### Kateqoriyalar üzrə statistika")

        category_df = pd.DataFrame(
            [dict(row) for row in by_category]
        )

        st.bar_chart(
            category_df.set_index("category")["events"]
        )

# --------------------------------------------------
# TƏDBİRLƏRİN İDARƏ EDİLMƏSİ
# --------------------------------------------------
elif page == "İdarəetmə paneli":
    st.subheader("🛠️ Tədbirlərin idarə edilməsi")

    with st.form("create_event_form", clear_on_submit=True):
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

        submitted = st.form_submit_button("Tədbir yarat")

        if submitted:
            if not title.strip():
                st.error("Tədbirin adını daxil et.")
            elif not description.strip():
                st.error("Tədbirin təsvirini daxil et.")
            elif not location.strip():
                st.error("Tədbirin yerini daxil et.")
            else:
                try:
                    save_event(
                        title,
                        description,
                        category_map[category_name],
                        event_date,
                        event_time,
                        location,
                        int(capacity),
                        st.session_state.user_id,
                    )

                    st.success("Tədbir yaradıldı.")
                    st.rerun()

                except Exception as e:
                    st.error("Tədbir yaradıla bilmədi.")
                    st.code(str(e))

    st.divider()
    st.markdown("### Mövcud tədbirlər")

    events = list_events()

    if not events:
        st.info("Silinəcək və ya redaktə ediləcək tədbir yoxdur.")
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

        if st.button("Seçilmiş tədbiri sil", type="secondary"):
            delete_event(selected_event["id"])
            st.success("Tədbir silindi.")
            st.rerun()
