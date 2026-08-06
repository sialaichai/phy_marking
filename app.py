import streamlit as st
import database as db
import grading
from PIL import Image

st.set_page_config(page_title="Smart Marking App", layout="centered")

# Initialise database
db.init_db()

# Simple session state for role
if "role" not in st.session_state:
    st.session_state.role = None

st.sidebar.title("📚 Smart Marking")
role = st.sidebar.radio("I am a:", ["Teacher", "Student"])
st.session_state.role = role

if role == "Teacher":
    st.sidebar.markdown("### Teacher Dashboard")
    page = st.sidebar.radio("Go to:", ["Upload Mark Scheme", "View Submissions"])
else:
    st.sidebar.markdown("### Student Dashboard")
    page = st.sidebar.radio("Go to:", ["Submit Work", "My Results"])

# ---- TEACHER: Upload Mark Scheme ----
if role == "Teacher" and page == "Upload Mark Scheme":
    st.header("📤 Upload a New Mark Scheme")
    with st.form("mark_scheme_form"):
        assignment_name = st.text_input("Assignment Name")
        question = st.text_area("Question")
        rubric = st.text_area("Marking Rubric / Expected Answer")
        total_points = st.number_input("Total Points", min_value=1, max_value=100, value=10)
        submitted = st.form_submit_button("Save Mark Scheme")
        if submitted:
            if not assignment_name or not question or not rubric:
                st.error("All fields are required.")
            else:
                scheme_id = db.add_mark_scheme(1, assignment_name, question, rubric, total_points)
                st.success(f"✅ Mark scheme saved! ID: {scheme_id}")

    st.subheader("📋 Existing Mark Schemes")
    schemes = db.get_all_mark_schemes()
    if schemes:
        for s in schemes:
            st.write(f"**{s[1]}** (ID: {s[0]}) — {s[4]} points")
            with st.expander("View details"):
                st.write(f"**Question:** {s[2]}")
                st.write(f"**Rubric:** {s[3]}")
    else:
        st.info("No mark schemes uploaded yet.")

# ---- TEACHER: View Submissions ----
elif role == "Teacher" and page == "View Submissions":
    st.header("📊 View Student Submissions")
    schemes = db.get_all_mark_schemes()
    if not schemes:
        st.warning("No mark schemes available.")
    else:
        scheme_choices = {f"{s[1]} (ID: {s[0]})": s[0] for s in schemes}
        selected_label = st.selectbox("Select an assignment", list(scheme_choices.keys()))
        scheme_id = scheme_choices[selected_label]
        scheme = db.get_mark_scheme(scheme_id)
        submissions = db.get_submissions_by_scheme(scheme_id)
        if submissions:
            for sub in submissions:
                st.write(f"**Student:** {sub[1]}  |  **Grade:** {sub[3]}/{scheme[4]}  |  **Feedback:** {sub[4]}")
                with st.expander("See details"):
                    st.write(f"**Transcribed text:** {sub[2]}")
                    st.write(f"**Graded at:** {sub[5]}")
        else:
            st.info("No submissions for this assignment yet.")

# ---- STUDENT: Submit Work ----
elif role == "Student" and page == "Submit Work":
    st.header("📸 Submit Your Work")
    schemes = db.get_all_mark_schemes()
    if not schemes:
        st.warning("No assignments available. Ask your teacher to upload one.")
    else:
        scheme_choices = {f"{s[1]} (ID: {s[0]})": s[0] for s in schemes}
        selected_label = st.selectbox("Choose assignment", list(scheme_choices.keys()))
        scheme_id = scheme_choices[selected_label]
        scheme = db.get_mark_scheme(scheme_id)
        if scheme:
            question, rubric, total_points = scheme[2], scheme[3], scheme[4]
            st.write(f"**Question:** {question}")
            st.write(f"**Total points:** {total_points}")

        student_name = st.text_input("Your Name")
        uploaded_file = st.file_uploader("Take a photo or upload an image", type=["jpg", "jpeg", "png"])
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="Your submission", width=300)
            if st.button("📨 Submit for Grading"):
                if not student_name:
                    st.error("Please enter your name.")
                else:
                    with st.spinner("Grading..."):
                        img_bytes = uploaded_file.getvalue()
                        # Set use_real_api=False for demo; change to True when you have API key
                        transcribed, grade, feedback = grading.grade_submission(
                            img_bytes, question, rubric, total_points, use_real_api=False
                        )
                        db.add_submission(scheme_id, student_name, transcribed, grade, feedback)
                        st.success(f"✅ Grade: **{grade}/{total_points}**")
                        st.info(f"**Feedback:** {feedback}")
                        st.caption(f"Transcribed text: {transcribed}")

# ---- STUDENT: My Results ----
elif role == "Student" and page == "My Results":
    st.header("📖 My Previous Results")
    schemes = db.get_all_mark_schemes()
    if not schemes:
        st.info("No results yet.")
    else:
        for s in schemes:
            scheme_id = s[0]
            submissions = db.get_submissions_by_scheme(scheme_id)
            if submissions:
                st.subheader(f"Assignment: {s[1]}")
                for sub in submissions:
                    st.write(f"**Student:** {sub[1]}  |  **Grade:** {sub[3]}/{s[4]}  |  **Feedback:** {sub[4]}")
            else:
                st.write(f"No submissions for {s[1]}")
