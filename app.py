import streamlit as st
import database as db
import grading
from PIL import Image
import io

st.set_page_config(page_title="Smart Marking App", layout="centered")

# ---- Init DB ----
db.init_db()

# ---- Session state ----
if "auth" not in st.session_state:
    st.session_state.auth = None   # {"type": "user" or "class", "data": {...}}
if "page" not in st.session_state:
    st.session_state.page = "login"

# ---- LOGIN ----
if st.session_state.auth is None:
    st.title("🔐 Smart Marking App – Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            auth = db.authenticate(username, password)
            if auth:
                st.session_state.auth = auth
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.caption("Demo accounts: admin/admin123, or use a class username/password created by teacher.")
    st.stop()

# ---- Extract auth info ----
auth = st.session_state.auth
auth_type = auth["type"]  # "user" or "class"
auth_data = auth["data"]

# ---- Logout button ----
st.sidebar.title(f"👋 Welcome, {auth_data.get('username') or auth_data.get('class_name')}")
if st.sidebar.button("🚪 Logout"):
    st.session_state.auth = None
    st.rerun()

st.sidebar.divider()

# ========================================================
#                    ADMIN DASHBOARD
# ========================================================
if auth_type == "user" and auth_data["role"] == "admin":
    st.header("👑 Admin Dashboard")
    st.subheader("Manage Teachers")

    # Create teacher
    with st.expander("➕ Create New Teacher"):
        with st.form("create_teacher"):
            new_username = st.text_input("Teacher username")
            new_password = st.text_input("Teacher password", type="password")
            if st.form_submit_button("Create"):
                if new_username and new_password:
                    result = db.create_teacher(new_username, new_password)
                    if result:
                        st.success(f"Teacher {new_username} created.")
                        st.rerun()
                    else:
                        st.error("Username may already exist.")
                else:
                    st.error("Both fields required.")

    # List teachers
    teachers = db.get_all_teachers()
    if teachers:
        for t in teachers:
            col1, col2, col3 = st.columns([3, 2, 2])
            col1.write(f"**{t['username']}** (ID: {t['id']})")
            if col2.button("Reset Password", key=f"reset_{t['id']}"):
                # simple prompt in Streamlit
                new_pw = st.text_input(f"New password for {t['username']}", key=f"pw_{t['id']}", type="password")
                if new_pw and len(new_pw) >= 6:
                    db.reset_teacher_password(t['id'], new_pw)
                    st.success("Password updated.")
                    st.rerun()
            if col3.button("Delete", key=f"del_{t['id']}"):
                db.delete_teacher(t['id'])
                st.success("Teacher deleted.")
                st.rerun()
    else:
        st.info("No teachers yet.")

# ========================================================
#                    TEACHER DASHBOARD
# ========================================================
elif auth_type == "user" and auth_data["role"] == "teacher":
    teacher_id = auth_data["id"]
    st.header("👨‍🏫 Teacher Dashboard")

    # Sidebar navigation
    page = st.sidebar.radio("Go to:", ["Manage Classes", "Upload Mark Scheme", "View Marks"])

    # ---------- Manage Classes ----------
    if page == "Manage Classes":
        st.subheader("📚 Your Classes")
        classes = db.get_teacher_classes(teacher_id)
        if classes:
            for cls in classes:
                with st.expander(f"**{cls['class_name']}** (username: {cls['class_username']})"):
                    st.write(f"Class ID: {cls['id']}")
                    # Change password
                    new_pw = st.text_input(f"New password for {cls['class_name']}", key=f"cpw_{cls['id']}", type="password")
                    if st.button("Update Password", key=f"upd_{cls['id']}"):
                        if new_pw and len(new_pw) >= 6:
                            db.update_class_password(cls['id'], new_pw)
                            st.success("Password updated.")
                            st.rerun()
                    if st.button("Delete Class", key=f"delc_{cls['id']}"):
                        db.delete_class(cls['id'])
                        st.success("Class deleted.")
                        st.rerun()
        else:
            st.info("You have no classes yet.")

        # Create new class
        with st.form("create_class"):
            st.write("### Create a new class")
            class_name = st.text_input("Class Name (e.g., Physics 101)")
            class_username = st.text_input("Class Username (for student login)")
            class_password = st.text_input("Class Password", type="password")
            if st.form_submit_button("Create Class"):
                if class_name and class_username and class_password:
                    result = db.create_class(teacher_id, class_name, class_username, class_password)
                    if result:
                        st.success(f"Class '{class_name}' created.")
                        st.rerun()
                    else:
                        st.error("Username may already exist.")
                else:
                    st.error("All fields required.")

    # ---------- Upload Mark Scheme ----------
    elif page == "Upload Mark Scheme":
        st.subheader("📤 Upload a New Mark Scheme")
        classes = db.get_teacher_classes(teacher_id)
        if not classes:
            st.warning("You need to create a class first.")
        else:
            class_options = {f"{c['class_name']} (ID: {c['id']})": c['id'] for c in classes}
            selected_class_label = st.selectbox("Select class", list(class_options.keys()))
            class_id = class_options[selected_class_label]

            with st.form("mark_scheme_form"):
                assignment_name = st.text_input("Assignment Name")
                question = st.text_area("Question")
                rubric = st.text_area("Marking Rubric / Expected Answer")
                total_points = st.number_input("Total Points", min_value=1, max_value=100, value=10)
                if st.form_submit_button("Save Scheme"):
                    if assignment_name and question and rubric:
                        scheme_id = db.add_mark_scheme(teacher_id, class_id, assignment_name, question, rubric, total_points)
                        if scheme_id:
                            st.success(f"Mark scheme saved! ID: {scheme_id}")
                        else:
                            st.error("Failed to save.")
                    else:
                        st.error("All fields are required.")

    # ---------- View Marks ----------
    elif page == "View Marks":
        st.subheader("📊 View Marks by Assignment and Class")
        schemes = db.get_teacher_mark_schemes(teacher_id)
        if not schemes:
            st.info("No mark schemes uploaded yet.")
        else:
            # Group by assignment name (or ID) and show class name
            # We'll display each scheme with its class and submissions
            for scheme in schemes:
                class_name = scheme.get('classes', {}).get('class_name', 'Unknown')
                st.markdown(f"### **{scheme['assignment_name']}** (Class: {class_name})")
                submissions = db.get_submissions_by_scheme(scheme['id'])
                if submissions:
                    for sub in submissions:
                        st.write(f"- **{sub['student_name']}**: {sub['grade']}/{scheme['total_points']} – {sub['feedback']}")
                else:
                    st.write("No submissions yet.")

# ========================================================
#                    STUDENT (CLASS) DASHBOARD
# ========================================================
elif auth_type == "class":
    class_data = auth_data
    class_id = class_data["id"]
    st.header(f"📘 Class: {class_data['class_name']}")

    # Student page options
    page = st.sidebar.radio("Go to:", ["Submit Work", "My Results"])

    # ---------- Submit Work ----------
    if page == "Submit Work":
        # Get all mark schemes for this class
        supabase = db.get_supabase()
        schemes = supabase.table("mark_schemes").select("*").eq("class_id", class_id).execute().data
        if not schemes:
            st.warning("No assignments available for this class yet.")
        else:
            scheme_options = {f"{s['assignment_name']} (ID: {s['id']})": s['id'] for s in schemes}
            selected_label = st.selectbox("Choose assignment", list(scheme_options.keys()))
            scheme_id = scheme_options[selected_label]
            scheme = db.get_mark_scheme(scheme_id)
            if scheme:
                st.write(f"**Question:** {scheme['question']}")
                st.write(f"**Total points:** {scheme['total_points']}")

            student_name = st.text_input("Your Full Name (for this submission)")
            # Inside the submission block, after they enter their name
            st.session_state["student_name_filter"] = student_name
            uploaded_file = st.file_uploader("Take a photo or upload an image of your answer", type=["jpg", "jpeg", "png"])
            if uploaded_file is not None:
                image = Image.open(uploaded_file)
                st.image(image, caption="Your submission", width=300)
                if st.button("📨 Submit for Grading"):
                    if not student_name:
                        st.error("Please enter your name.")
                    else:
                        with st.spinner("Grading..."):
                            img_bytes = uploaded_file.getvalue()
                            # Use the real DeepSeek API (set use_real_api=True)
                            grade, feedback = grading.grade_submission(
                                img_bytes, 
                                scheme["question"], 
                                scheme["rubric"], 
                                scheme["total_points"],
                                use_real_api=True   # now using real API
                            )
                            db.add_submission(scheme_id, student_name, "Image processed", grade, feedback)
                            st.success(f"✅ Grade: **{grade}/{scheme['total_points']}**")
                            st.info(f"**Feedback:** {feedback}")

    # ---------- My Results ----------
    elif page == "My Results":
        st.subheader("📖 Your Previous Results")
        student_name_filter = st.text_input("Enter your full name to see your submissions:", value=st.session_state.get("my_name", ""))
        if not student_name_filter:
            st.info("Please enter your name above.")
            # Optional: clear the key if empty
        else:
            st.session_state["my_name"] = student_name_filter
            supabase = db.get_supabase()
            schemes = supabase.table("mark_schemes").select("*").eq("class_id", class_id).execute().data
            if not schemes:
                st.info("No assignments available.")
            else:
                found_any = False
                for scheme in schemes:
                    all_subs = db.get_submissions_by_scheme(scheme['id'])
                    # Filter by student name
                    my_subs = [s for s in all_subs if s['student_name'].lower() == student_name_filter.lower()]
                    if my_subs:
                        found_any = True
                        st.markdown(f"### **{scheme['assignment_name']}**")
                        for sub in my_subs:
                            # Only show score and feedback, not other names
                            st.write(f"- **Score**: {sub['grade']}/{scheme['total_points']} – **Feedback**: {sub['feedback']}")
                            with st.expander("See details"):
                                st.write(f"**Your transcribed text:** {sub['transcribed_text']}")
                                st.write(f"**Graded at:** {sub['graded_at']}")
                if not found_any:
                    st.warning(f"No submissions found for '{student_name_filter}'. Please check your name.")
