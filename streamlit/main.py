import streamlit as st
import pandas as pd

from database import (
    create_table,
    add_student,
    get_students,
    delete_student
)

st.set_page_config(
    page_title="Tələbə İdarəetmə Sistemi",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 Tələbə İdarəetmə Sistemi")
st.caption("Tələbələri əlavə et, qiymətlərini izlə və məlumatları idarə et.")

try:
    create_table()
except Exception as e:
    st.error("Verilənlər bazasına qoşulmaq mümkün olmadı.")
    st.code(str(e))
    st.stop()

students = get_students()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Ümumi tələbə", len(students))

with col2:
    average = (
        sum(float(student[2]) for student in students) / len(students)
        if students else 0
    )
    st.metric("Orta bal", f"{average:.2f}")

with col3:
    passed = sum(1 for student in students if float(student[2]) >= 51)
    st.metric("Keçid balını toplayan", passed)

st.divider()

left, right = st.columns([1, 2])

with left:
    st.subheader("➕ Yeni tələbə")

    with st.form("student_form", clear_on_submit=True):
        name = st.text_input("Tələbənin adı")
        score = st.number_input(
            "Qiymət",
            min_value=0.0,
            max_value=100.0,
            value=50.0,
            step=1.0
        )

        submitted = st.form_submit_button(
            "Tələbəni əlavə et",
            use_container_width=True
        )

        if submitted:
            if not name.strip():
                st.error("Tələbənin adını daxil et.")
            else:
                try:
                    add_student(name.strip(), score)
                    st.success("Tələbə uğurla əlavə edildi.")
                    st.rerun()
                except Exception as e:
                    st.error("Tələbə əlavə edilə bilmədi.")
                    st.code(str(e))

with right:
    st.subheader("📋 Tələbələrin siyahısı")

    if students:
        df = pd.DataFrame(
            students,
            columns=["ID", "Ad", "Bal"]
        )

        st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("🗑️ Tələbəni sil")

        options = {
            f"{student[1]} — ID: {student[0]}": student[0]
            for student in students
        }

        selected = st.selectbox(
            "Silinəcək tələbə",
            options=list(options.keys())
        )

        if st.button("Seçilmiş tələbəni sil", type="primary"):
            try:
                delete_student(options[selected])
                st.success("Tələbə silindi.")
                st.rerun()
            except Exception as e:
                st.error("Tələbəni silmək mümkün olmadı.")
                st.code(str(e))
    else:
        st.info("Hələ heç bir tələbə əlavə edilməyib.")
