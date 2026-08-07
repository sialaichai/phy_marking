import streamlit as st
import database as db
import grading
from PIL import Image
import io

# ---- Page config ----
st.set_page_config(page_title="Smart Marking App", layout="centered")

# ---- Initialise Supabase tables and default accounts ----
db.init_db()

# ---- Login / session management ----
if "user" not in st.session_state:
    st.title("🔐 Smart Marking App – Login")
    col1, col2 = st.columns(2)
    with col1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user = db.authenticate(username, password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid credentials")
    with col2:
        st.markdown("**Default accounts:**")
        st.code("Teacher: teacher / teacher123\nStudent: student / student123")
    st.stop()   # Stop execution until logged in

# ---- User is logged in ----
user = st.session_state.user
role = user["role"]
user_id = user["id"]

# ---- Sidebar ----
st.sidebar.title(f"👋 Welcome, {user['username']}")
st.sidebar.markdown(f"**Role:** {role.capitalize()}")
if st.sidebar.button("🚪 Logout"):
    del st.session_state.user
    st.rerun()

st.sidebar.divider()
if role == "teacher":
    st.sidebar.markdown("### Teacher Dashboard")
    page = st.sidebar.radio("Go to:", ["Upload Mark Scheme", "View Submissions", "Change Password"])
else:
    st.sidebar.markdown("### Student Dashboard")
    page = st.sidebar.radio("Go to:", ["Submit Work", "My Results", "Change Password"])


# ========================================================
#                    CHANGE PASSWORD (Shared)
# ========================================================
if page == "Change Password":
    st.header("🔑 Change Your Password")

    # If password was just updated, log out and redirect to login
    if "password_updated" in st.session_state and st.session_state.password_updated:
        st.success("✅ Password updated successfully! You are now being logged out.")
        # Clear session and force re‑login
        del st.session_state.user
        del st.session_state.password_updated
        st.rerun()
        st.stop()   # Stop further execution

    with st.form("change_password_form"):
        old_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Update Password")

        if submitted:
            if not old_password or not new_password or not confirm_password:
                st.error("All fields are required.")
            elif new_password != confirm_password:
                st.error("New passwords do not match.")
            elif len(new_password) < 6:
                st.error("New password must be at least 6 characters.")
            else:
                # Verify old password
                user = st.session_state.user
                if db.authenticate(user["username"], old_password):
                    db.update_password(user["id"], new_password)
                    st.session_state.password_updated = True
                    st.rerun()
                else:
                    st.error("❌ Current password is incorrect.")

# ========================================================
#                    TEACHER PAGES
# ========================================================
if role == "teacher" and page == "Upload Mark Scheme":
    st.header("📤 Upload a New Mark Scheme")
    with st.form("mark_scheme_form"):
        assignment_name = st.text_input("Assignment Name", placeholder="e.g., Math Quiz 1")
        question = st.text_area("Question", placeholder="Write the question here.")
        rubric = st.text_area("Marking Rubric / Expected Answer", 
                              placeholder="Describe what a good answer should include.")
        total_points = st.number_input("Total Points", min_value=1, max_value=100, value=10)
        submitted = st.form_submit_button("💾 Save Mark Scheme")
        if submitted:
            if not assignment_name or not question or not rubric:
                st.error("All fields are required.")
            else:
                scheme_id = db.add_mark_scheme(user_id, assignment_name, question, rubric, total_points)
                if scheme_id:
                    st.success(f"✅ Mark scheme saved! ID: {scheme_id}")
                else:
                    st.error("Failed to save. Check logs.")

    # Show existing schemes
    st.subheader("📋 Your Existing Mark Schemes")
    schemes = db.get_all_mark_schemes()
    # Filter by this teacher (since we might have multiple teachers later)
    teacher_schemes = [s for s in schemes if s["teacher_id"] == user_id]
    if teacher_schemes:
        for s in teacher_schemes:
            st.write(f"**{s['assignment_name']}** (ID: {s['id']}) — {s['total_points']} points")
            with st.expander("View details"):
                st.write(f"**Question:** {s['question']}")
                st.write(f"**Rubric:** {s['rubric']}")
    else:
        st.info("You haven't uploaded any mark schemes yet.")

elif role == "teacher" and page == "View Submissions":
    st.header("📊 View Student Submissions")
    schemes = db.get_all_mark_schemes()
    teacher_schemes = [s for s in schemes if s["teacher_id"] == user_id]
    if not teacher_schemes:
        st.warning("You have no mark schemes. Please upload one first.")
    else:
        scheme_options = {f"{s['assignment_name']} (ID: {s['id']})": s["id"] for s in teacher_schemes}
        selected_label = st.selectbox("Select an assignment", list(scheme_options.keys()))
        scheme_id = scheme_options[selected_label]
        scheme = db.get_mark_scheme(scheme_id)
        submissions = db.get_submissions_by_scheme(scheme_id)
        if submissions:
            for sub in submissions:
                st.write(f"**Student:** {sub['student_name']}  |  **Grade:** {sub['grade']}/{scheme['total_points']}  |  **Feedback:** {sub['feedback']}")
                with st.expander("See details"):
                    st.write(f"**Transcribed text:** {sub['transcribed_text']}")
                    st.write(f"**Graded at:** {sub['graded_at']}")
        else:
            st.info("No submissions for this assignment yet.")

# ========================================================
#                    STUDENT PAGES
# ========================================================
if role == "student" and page == "Submit Work":
    st.header("📸 Submit Your Work")
    # Get all mark schemes (from all teachers – you may want to filter by class later)
    schemes = db.get_all_mark_schemes()
    if not schemes:
        st.warning("No assignments available. Please ask your teacher to upload a mark scheme.")
    else:
        scheme_options = {f"{s['assignment_name']} (Teacher: {s['teacher_id']})": s["id"] for s in schemes}
        selected_label = st.selectbox("Choose assignment", list(scheme_options.keys()))
        scheme_id = scheme_options[selected_label]
        scheme = db.get_mark_scheme(scheme_id)
        if scheme:
            st.write(f"**Question:** {scheme['question']}")
            st.write(f"**Total points:** {scheme['total_points']}")

        student_name = st.text_input("Your Name (as you want it to appear)", placeholder="e.g., John Doe")
        uploaded_file = st.file_uploader("Take a photo or upload an image of your answer", type=["jpg", "jpeg", "png"])
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="Your submission", width=300)
            # Inside the student submission block
            if st.button("📨 Submit for Grading"):
                if not student_name:
                    st.error("Please enter your name.")
                else:
                    with st.spinner("AI teacher is grading your work..."):
                        img_bytes = uploaded_file.getvalue()
                        
                        # Use real DeepSeek API
                        grade, feedback = grading.grade_submission(
                            img_bytes, 
                            scheme["question"], 
                            scheme["rubric"], 
                            scheme["total_points"],
                            use_real_api=True   # Set to True to use DeepSeek
                        )
                        
                        # Save to database
                        db.add_submission(scheme_id, student_name, "Image processed", grade, feedback)
                        
                        st.success(f"✅ Grading complete! You scored **{grade}/{scheme['total_points']}**.")
                        st.info(f"**Feedback:** {feedback}")

elif role == "student" and page == "My Results":
    st.header("📖 My Previous Results")
    # We'll show all submissions where student_name matches the currently logged‑in student
    # Since we don't have a unique ID for students yet, we'll ask for their name to filter.
    # But we can also show a list of all submissions and let the user filter by their name.
    # For simplicity, we'll show all submissions from all assignments.
    schemes = db.get_all_mark_schemes()
    if not schemes:
        st.info("No results available.")
    else:
        # Show a filter by student name
        all_subs = []
        for s in schemes:
            subs = db.get_submissions_by_scheme(s["id"])
            all_subs.extend([(s, sub) for sub in subs])
        if not all_subs:
            st.info("No submissions have been graded yet.")
        else:
            # Let student pick their name from the existing submissions
            names = sorted(set([sub["student_name"] for _, sub in all_subs]))
            if names:
                selected_name = st.selectbox("Select your name", names)
                # Filter
                filtered = [(s, sub) for s, sub in all_subs if sub["student_name"] == selected_name]
                if filtered:
                    for s, sub in filtered:
                        st.write(f"**Assignment:** {s['assignment_name']}  |  **Grade:** {sub['grade']}/{s['total_points']}  |  **Feedback:** {sub['feedback']}")
                        with st.expander("See details"):
                            st.write(f"**Transcribed text:** {sub['transcribed_text']}")
                            st.write(f"**Graded at:** {sub['graded_at']}")
                else:
                    st.info("No submissions found for that name.")
            else:
                st.info("No submissions with names yet. Submit some work first.")
