import streamlit as st
import database as db
import grading
import email_utils
from PIL import Image
import io
import traceback
import pandas as pd
import json
import re
import base64

# ---- Helper function for numeric mark extraction ----
def extract_numeric_mark(mark_val):
    """
    Extract only the numeric value from a mark field.
    Handles: "1", "2", "0.5", "1 mark", "2 marks", "1/2", "1 out of 2", etc.
    """
    if isinstance(mark_val, (int, float)):
        return str(mark_val)
    
    if isinstance(mark_val, str):
        # Try to extract number from string
        match = re.search(r'(\d+(?:\.\d+)?)', mark_val)
        if match:
            num = float(match.group(1))
            if num == int(num):
                return str(int(num))
            return str(num)
    
    return "0"

# ---- Helper function to display feedback table (single column) ----
def display_feedback_table(feedback_table):
    """
    Display feedback as a clean single-column list.
    Each card shows: Mark, Rubric, Rationale.
    No horizontal scrolling on mobile.
    """
    if not feedback_table or len(feedback_table) == 0:
        st.caption("No detailed breakdown available.")
        return
    
    for i, row in enumerate(feedback_table):
        mark_val = row.get('mark', '0')
        rubric_text = row.get('rubric', '')
        rationale = row.get('rationale', 'No rationale provided.')
        
        # Escape special characters for HTML
        rubric_text = rubric_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        rationale = rationale.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Alternating background colors
        bg_color = '#f9f9f9' if i % 2 == 0 else '#ffffff'
        
        st.markdown(f"""
        <div style="
            background-color: {bg_color};
            padding: 12px 15px;
            border-radius: 8px;
            margin-bottom: 8px;
            border-left: 4px solid #4CAF50;
        ">
            <div style="font-size: 18px; font-weight: bold; color: #4CAF50;">
                Mark: {mark_val}
            </div>
            <div style="font-size: 13px; color: #666; margin-top: 4px; font-weight: bold;">
                Rubric: <span style="font-weight: normal; color: #333;">{rubric_text if rubric_text else 'N/A'}</span>
            </div>
            <div style="font-size: 14px; color: #333; margin-top: 4px; line-height: 1.5;">
                <span style="font-weight: bold;">Rationale:</span> {rationale}
            </div>
        </div>
        """, unsafe_allow_html=True)

# ---- Page config ----
st.set_page_config(
    page_title="Smart Marking App", 
    layout="centered",
    initial_sidebar_state="auto"
)

# ---- Custom CSS for mobile-friendly UI ----
st.markdown("""
<style>
    /* Make buttons larger and more prominent */
    .stButton button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
        font-size: 18px;
        font-weight: bold;
        padding: 12px 24px;
        border-radius: 8px;
        border: none;
        margin-top: 10px;
    }
    .stButton button:hover {
        background-color: #45a049;
        transform: scale(1.02);
        transition: all 0.3s ease;
    }
    .stButton button[kind="secondary"] {
        background-color: #f44336;
    }
    .stButton button[kind="secondary"]:hover {
        background-color: #d32f2f;
    }
    .stTextInput input, .stTextArea textarea, .stSelectbox select {
        font-size: 16px !important;
        padding: 12px !important;
    }
    /* Camera input - larger on mobile */
    .stCameraInput {
        width: 100% !important;
        min-height: 400px !important;
    }
    .stCameraInput video {
        width: 100% !important;
        height: auto !important;
        min-height: 400px !important;
        object-fit: cover !important;
    }
    .stCameraInput div {
        width: 100% !important;
    }
    .stCameraInput button {
        font-size: 20px !important;
        padding: 15px 30px !important;
    }
    .stCameraInput > div {
        width: 100% !important;
        max-width: 100% !important;
    }
    @media (max-width: 768px) {
        .stButton button {
            font-size: 20px;
            padding: 15px 30px;
        }
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
            font-size: 1.5em !important;
        }
        .stCameraInput {
            min-height: 500px !important;
        }
        .stCameraInput video {
            min-height: 500px !important;
        }
        .stCameraInput button {
            font-size: 24px !important;
            padding: 20px 40px !important;
        }
    }
    /* Prevent horizontal scroll */
    .main {
        overflow-x: hidden !important;
        max-width: 100% !important;
    }
    .block-container {
        max-width: 100% !important;
        padding: 1rem !important;
        overflow-x: hidden !important;
    }
    .stApp {
        overflow-x: hidden !important;
    }
</style>
""", unsafe_allow_html=True)

# ---- Init DB ----
db.init_db()

# ---- Session state ----
if "auth" not in st.session_state:
    st.session_state.auth = None
if "page" not in st.session_state:
    st.session_state.page = "login"

# ---- LOGIN ----
if st.session_state.auth is None:
    st.title("🔐 Smart Marking App – Login")
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", placeholder="Enter your password", type="password")
        submitted = st.form_submit_button(
            "🔐 Login",
            use_container_width=True,
            type="primary"
        )
        if submitted:
            if not username or not password:
                st.error("Please enter both username and password.")
            else:
                auth = db.authenticate(username, password)
                if auth:
                    st.session_state.auth = auth
                    st.rerun()
                else:
                    st.error("Invalid credentials")
    
    st.caption("Demo accounts: admin/admin123, or use a class username/password created by your teacher.")
    st.stop()

# ---- Extract auth info ----
auth = st.session_state.auth
auth_type = auth["type"]  # "user" or "class"
auth_data = auth["data"]

# ---- Logout button ----
st.sidebar.title(f"👋 Welcome, {auth_data.get('username') or auth_data.get('class_name')}")
if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.auth = None
    st.rerun()

st.sidebar.divider()

# ========================================================
#                    ADMIN DASHBOARD
# ========================================================
if auth_type == "user" and auth_data["role"] == "admin":
    admin_id = auth_data["id"]
    st.header("👑 Admin Dashboard")
    page = st.sidebar.radio("Go to:", ["Manage Teachers", "Change Password"])
    
    if page == "Manage Teachers":
        st.subheader("Manage Teachers")
        with st.expander("➕ Create New Teacher"):
            with st.form("create_teacher"):
                new_username = st.text_input("Teacher username", placeholder="Enter username")
                new_password = st.text_input("Teacher password", placeholder="Enter password", type="password")
                submitted = st.form_submit_button(
                    "➕ Create Teacher",
                    use_container_width=True,
                    type="primary"
                )
                if submitted:
                    if new_username and new_password:
                        result = db.create_teacher(new_username, new_password)
                        if result:
                            st.success(f"Teacher {new_username} created.")
                            st.rerun()
                        else:
                            st.error("Username may already exist.")
                    else:
                        st.error("Both fields required.")
        
        teachers = db.get_all_teachers()
        if teachers:
            for t in teachers:
                col1, col2, col3 = st.columns([3, 2, 2])
                col1.write(f"**{t['username']}** (ID: {t['id']})")
                if col2.button("Reset Password", key=f"reset_{t['id']}"):
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
    
    elif page == "Change Password":
        st.subheader("🔑 Change Your Admin Password")
        if "admin_pw_updated" in st.session_state and st.session_state.admin_pw_updated:
            st.success("✅ Password updated successfully! Please log in again.")
            del st.session_state.auth
            del st.session_state.admin_pw_updated
            st.rerun()
            st.stop()
        
        with st.form("admin_change_pw"):
            old_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            submitted = st.form_submit_button(
                "🔑 Update Password",
                use_container_width=True,
                type="primary"
            )
            if submitted:
                if not old_password or not new_password or not confirm_password:
                    st.error("All fields are required.")
                elif new_password != confirm_password:
                    st.error("New passwords do not match.")
                elif len(new_password) < 6:
                    st.error("New password must be at least 6 characters.")
                else:
                    if db.authenticate(auth_data["username"], old_password):
                        db.update_user_password(admin_id, new_password)
                        st.session_state.admin_pw_updated = True
                        st.rerun()
                    else:
                        st.error("❌ Current password is incorrect.")

# ========================================================
#                    TEACHER DASHBOARD
# ========================================================
elif auth_type == "user" and auth_data["role"] == "teacher":
    teacher_id = auth_data["id"]
    st.header("👨‍🏫 Teacher Dashboard")

    # Sidebar navigation
    page = st.sidebar.radio("Go to:", ["Manage Classes", "Upload Mark Scheme", "View Marks", "Manage Trial Data"])

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
                    if st.button("Update Password", key=f"upd_{cls['id']}", use_container_width=True):
                        if new_pw and len(new_pw) >= 6:
                            db.update_class_password(cls['id'], new_pw)
                            st.success("Password updated.")
                            st.rerun()
                    if st.button("Delete Class", key=f"delc_{cls['id']}", use_container_width=True):
                        db.delete_class(cls['id'])
                        st.success("Class deleted.")
                        st.rerun()
        else:
            st.info("You have no classes yet.")

        # Create new class
        with st.form("create_class"):
            st.write("### Create a new class")
            class_name = st.text_input("Class Name (e.g., Physics 101)", placeholder="Enter class name")
            class_username = st.text_input("Class Username (for student login)", placeholder="Enter username for students")
            class_password = st.text_input("Class Password", placeholder="Enter password for students", type="password")
            is_trial_class = st.checkbox("🧪 This is a trial class (for testing)", value=True)
            
            submitted = st.form_submit_button(
                "📚 Create Class",
                use_container_width=True,
                type="primary"
            )
            if submitted:
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
        
        with st.form("mark_scheme_form"):
            assignment_name = st.text_input("Assignment Name", placeholder="e.g., Physics Quiz 1")
            
            st.write("### 📄 Upload Question (Optional)")
            st.caption("Upload the question as a PDF or image file for students to reference.")
            question_file = st.file_uploader(
                "Upload question file (PDF or image)",
                type=["pdf", "jpg", "jpeg", "png"],
                accept_multiple_files=False
            )
            
            question = st.text_area(
                "Question Text (Optional if uploading file)", 
                placeholder="Write the question here, or leave blank if uploading a file.",
                height=100
            )
            
            rubric = st.text_area("Marking Rubric / Expected Answer", placeholder="Describe what a good answer should include.", height=150)
            total_points = st.number_input("Total Points", min_value=1, max_value=100, value=10)
            is_trial = st.checkbox("🧪 This is trial data (for testing)", value=True)
            
            submitted = st.form_submit_button(
                "💾 Save Mark Scheme",
                use_container_width=True,
                type="primary"
            )
            if submitted:
                if not assignment_name:
                    st.error("Assignment name is required.")
                elif not question and question_file is None:
                    st.error("Please provide either question text or upload a question file.")
                else:
                    question_file_data = None
                    question_file_name = None
                    question_file_type = None
                    
                    if question_file is not None:
                        file_bytes = question_file.getvalue()
                        question_file_data = base64.b64encode(file_bytes).decode('utf-8')
                        question_file_name = question_file.name
                        question_file_type = question_file.type
                    
                    scheme_id = db.add_mark_scheme(
                        teacher_id, 
                        assignment_name, 
                        question, 
                        rubric, 
                        total_points, 
                        is_trial,
                        question_file_data=question_file_data,
                        question_file_name=question_file_name,
                        question_file_type=question_file_type
                    )
                    if scheme_id:
                        st.success(f"Mark scheme saved! ID: {scheme_id}")
                    else:
                        st.error("Failed to save.")

    # ---------- View Marks ----------
    elif page == "View Marks":
        st.subheader("📊 View Marks by Assignment and Class")
        
        show_trial = st.checkbox("Show trial data", value=True)
        schemes = db.get_teacher_mark_schemes(teacher_id, include_trial=show_trial)
        
        if not schemes:
            st.info("No mark schemes found.")
        else:
            for scheme in schemes:
                trial_tag = "🧪 TRIAL" if scheme.get('is_trial', True) else "✅ REAL"
                st.markdown(f"### **{scheme['assignment_name']}** {trial_tag}")
                
                if scheme.get('question_file_data'):
                    st.caption("📎 Question file attached")
                
                submissions = db.get_submissions_by_scheme(scheme['id'])
                
                if not submissions:
                    st.write("No submissions yet.")
                else:
                    classes = {}
                    for sub in submissions:
                        class_name = sub.get('classes', {}).get('class_name', 'Unknown Class')
                        if class_name not in classes:
                            classes[class_name] = []
                        classes[class_name].append(sub)
                    
                    for class_name, class_subs in classes.items():
                        st.write(f"**📚 Class: {class_name}**")
                        
                        for sub in class_subs:
                            with st.expander(f"📋 {sub['student_name']} – {sub['grade']}/{scheme['total_points']}"):
                                try:
                                    feedback_data = json.loads(sub['feedback'])
                                    if isinstance(feedback_data, dict):
                                        if 'overall_feedback' in feedback_data:
                                            st.info(f"**Overall:** {feedback_data['overall_feedback']}")
                                        
                                        if 'feedback_table' in feedback_data and feedback_data['feedback_table']:
                                            display_feedback_table(feedback_data['feedback_table'])
                                        else:
                                            st.write(sub['feedback'])
                                except:
                                    st.write(sub['feedback'])
                    st.divider()

    # ---------- Manage Trial Data ----------
    elif page == "Manage Trial Data":
        st.subheader("🧹 Manage Trial Data")
        st.warning("⚠️ This section allows you to delete trial data. These actions are permanent and cannot be undone!")
        st.info("Trial data is marked with 🧪 and is meant for testing purposes only.")
        
        schemes = db.get_teacher_mark_schemes(teacher_id, include_trial=True)
        trial_schemes = [s for s in schemes if s.get('is_trial', True)]
        real_schemes = [s for s in schemes if not s.get('is_trial', False)]
        
        if not trial_schemes:
            st.success("✅ No trial data found. Everything is clean!")
        else:
            st.write(f"Found **{len(trial_schemes)}** trial assignments.")
            
            st.subheader("🗑️ Delete Trial Submissions for a Specific Assignment")
            scheme_options = {f"{s['assignment_name']} (ID: {s['id']})": s['id'] for s in trial_schemes}
            selected_scheme = st.selectbox("Select trial assignment to clean", list(scheme_options.keys()))
            scheme_id = scheme_options[selected_scheme]
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Delete trial submissions only", use_container_width=True):
                    db.delete_trial_submissions(scheme_id)
                    st.success("Trial submissions deleted!")
                    st.rerun()
            with col2:
                if st.button("⚠️ Delete entire trial assignment", use_container_width=True):
                    db.delete_trial_mark_scheme(scheme_id)
                    st.success("Trial assignment deleted!")
                    st.rerun()
            
            st.subheader("🔄 Convert Trial Data to Real Data")
            st.info("This will mark the assignment and all its submissions as REAL data.")
            selected_convert = st.selectbox("Select trial assignment to convert", list(scheme_options.keys()), key="convert_select")
            scheme_id_convert = scheme_options[selected_convert]
            if st.button("✅ Convert to REAL data", use_container_width=True):
                db.convert_to_real_data(scheme_id_convert)
                st.success("Assignment converted to REAL data!")
                st.rerun()
            
            st.divider()
            st.subheader("🔥 Delete ALL Trial Data")
            st.warning("This will delete ALL your trial assignments and their submissions.")
            
            confirm = st.checkbox("I understand this is permanent and cannot be undone")
            if confirm and st.button("⚠️ Delete ALL trial data", use_container_width=True, type="primary"):
                db.delete_all_trial_data(teacher_id)
                st.success("All trial data deleted!")
                st.rerun()
        
        if real_schemes:
            st.divider()
            st.success(f"✅ You have **{len(real_schemes)}** real assignments (not trial).")

# ========================================================
#                    STUDENT (CLASS) DASHBOARD
# ========================================================
elif auth_type == "class":
    class_data = auth_data
    class_id = class_data["id"]
    st.header(f"📘 Class: {class_data['class_name']}")

    page = st.sidebar.radio("Go to:", ["Submit Work", "My Results"])

    # ---------- Submit Work ----------
    # ---------- Submit Work ----------
    if page == "Submit Work":
        st.header("📸 Submit Your Work")
        
        supabase = db.get_supabase()
        
        class_info = supabase.table("classes").select("teacher_id").eq("id", class_id).execute()
        if not class_info.data:
            st.error("Class not found.")
        else:
            teacher_id_from_class = class_info.data[0]["teacher_id"]
            
            schemes = supabase.table("mark_schemes").select("*").eq("teacher_id", teacher_id_from_class).execute().data
            
            if not schemes:
                st.warning("No assignments available from your teacher yet.")
            else:
                scheme_options = {f"{s['assignment_name']}": s['id'] for s in schemes}
                selected_label = st.selectbox("Choose assignment", list(scheme_options.keys()))
                scheme_id = scheme_options[selected_label]
                scheme = db.get_mark_scheme(scheme_id)
                
                if scheme:
                    st.subheader("📋 Question")
                    
                    if scheme.get('question_file_data'):
                        st.caption("📎 Question file attached by teacher")
                        
                        try:
                            file_data = base64.b64decode(scheme['question_file_data'])
                            file_name = scheme.get('question_file_name', 'question')
                            file_type = scheme.get('question_file_type', '')
                            
                            if 'pdf' in file_type.lower() or file_name.lower().endswith('.pdf'):
                                st.download_button(
                                    label="📥 Download Question PDF",
                                    data=file_data,
                                    file_name=file_name,
                                    mime="application/pdf"
                                )
                                st.info("📄 Click the button above to download and view the question PDF.")
                            elif any(ext in file_name.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']):
                                image = Image.open(io.BytesIO(file_data))
                                st.image(image, caption="Question", use_container_width=True)
                            else:
                                st.download_button(
                                    label=f"📥 Download {file_name}",
                                    data=file_data,
                                    file_name=file_name
                                )
                        except Exception as e:
                            st.warning(f"⚠️ Could not display question file: {str(e)}")
                    
                    if scheme.get('question'):
                        if scheme.get('question_file_data'):
                            st.write("**Question Text:**")
                        st.write(scheme['question'])
                    
                    if not scheme.get('question') and not scheme.get('question_file_data'):
                        st.warning("⚠️ No question available. Please contact your teacher.")
                    
                    st.write(f"**Total points:** {scheme['total_points']}")
    
                # ---- CUSTOM CSS FOR LARGER CAMERA ----
                st.markdown("""
                <style>
                    .stCameraInput {
                        width: 100% !important;
                        min-height: 400px !important;
                    }
                    .stCameraInput video {
                        width: 100% !important;
                        height: auto !important;
                        min-height: 400px !important;
                        object-fit: cover !important;
                    }
                    .stCameraInput div {
                        width: 100% !important;
                    }
                    .stCameraInput button {
                        font-size: 20px !important;
                        padding: 15px 30px !important;
                    }
                    .stCameraInput > div {
                        width: 100% !important;
                        max-width: 100% !important;
                    }
                    @media (max-width: 768px) {
                        .stCameraInput {
                            min-height: 500px !important;
                        }
                        .stCameraInput video {
                            min-height: 500px !important;
                        }
                        .stCameraInput button {
                            font-size: 24px !important;
                            padding: 20px 40px !important;
                        }
                    }
                </style>
                """, unsafe_allow_html=True)
    
                with st.form("submission_form"):
                    student_name = st.text_input("Your Full Name", placeholder="e.g., John Doe")
                    student_email = st.text_input("Your Email Address (optional)", placeholder="john@example.com")
                    st.caption("📧 If provided, your grade and feedback will be sent to this email address.")
                    
                    st.write("### 📷 Take a photo of your work")
                    st.write("**Tap the button below to open your camera**")
                    camera_image = st.camera_input(
                        "",
                        disabled=False,
                        key="camera_input_large"
                    )
                    
                    if camera_image is not None:
                        image = Image.open(camera_image)
                        st.image(image, caption="Captured photo", width=300)
                        st.success("✅ Photo captured! Ready to submit.")
                    
                    st.write("---")
                    st.write("### 📁 Or upload an image file")
                    uploaded_file = st.file_uploader(
                        "Upload image (JPG/PNG)", 
                        type=["jpg", "jpeg", "png"],
                        accept_multiple_files=False
                    )
                    
                    if uploaded_file is not None:
                        image = Image.open(uploaded_file)
                        st.image(image, caption="Uploaded image", width=300)
                        st.success("✅ Image uploaded! Ready to submit.")
                    
                    # Determine which image to submit
                    image_to_submit = None
                    if camera_image is not None:
                        image_to_submit = camera_image
                    elif uploaded_file is not None:
                        image_to_submit = uploaded_file
                    
                    # ---- SUBMIT BUTTON ----
                    submitted = st.form_submit_button(
                        "📨 Submit for Grading",
                        use_container_width=True,
                        type="primary"
                    )
                    
                    if submitted:
                        # Validation
                        if not student_name:
                            st.error("Please enter your name.")
                        elif image_to_submit is None:
                            st.error("Please take a photo or upload an image of your work.")
                        else:
                            with st.spinner("Grading..."):
                                img_bytes = image_to_submit.getvalue()
                                
                                # Get question text
                                question_text = scheme.get('question', '')
                                if not question_text and scheme.get('question_file_data'):
                                    question_text = f"Question file: {scheme.get('question_file_name', 'See attachment')}"
                                
                                # Grade the submission
                                grade, feedback_table, overall_feedback = grading.grade_work(
                                    img_bytes, 
                                    question_text,
                                    scheme["rubric"], 
                                    scheme["total_points"],
                                    use_real_api=True
                                )
                                
                                feedback_json = json.dumps({
                                    "overall_feedback": overall_feedback,
                                    "feedback_table": feedback_table
                                })
                                
                                is_trial = scheme.get('is_trial', True)
                                
                                email_sent = False
                                if student_email and email_utils.is_valid_email(student_email):
                                    try:
                                        db.add_submission(
                                            scheme_id, 
                                            class_id,
                                            student_name, 
                                            student_email, 
                                            "Image processed", 
                                            grade, 
                                            feedback_json,
                                            is_trial=is_trial
                                        )
                                        
                                        email_feedback = f"{overall_feedback}\n\nDetailed breakdown:\n"
                                        for row in feedback_table:
                                            mark_val = row.get('mark', 0)
                                            numeric_mark = extract_numeric_mark(mark_val)
                                            email_feedback += f"- {numeric_mark}: {row.get('rationale', 'No rationale')}\n"
                                        
                                        email_status = email_utils.send_grade_email(
                                            student_email, 
                                            student_name, 
                                            question_text, 
                                            grade, 
                                            scheme["total_points"], 
                                            email_feedback
                                        )
                                        if "sent successfully" in email_status.lower():
                                            email_sent = True
                                    except Exception as e:
                                        db.add_submission(
                                            scheme_id, 
                                            class_id,
                                            student_name, 
                                            "", 
                                            "Image processed", 
                                            grade, 
                                            feedback_json
                                        )
                                else:
                                    db.add_submission(
                                        scheme_id, 
                                        class_id,
                                        student_name, 
                                        "", 
                                        "Image processed", 
                                        grade, 
                                        feedback_json
                                    )
                                
                                # ---- DISPLAY RESULTS ----
                                st.success(f"✅ Grading complete! You scored **{grade}/{scheme['total_points']}**.")
                                
                                if overall_feedback:
                                    st.info(f"**Overall Feedback:** {overall_feedback}")
                                
                                if feedback_table and len(feedback_table) > 0:
                                    st.subheader("📊 Detailed Mark Breakdown")
                                    display_feedback_table(feedback_table)
                                else:
                                    st.caption("No detailed breakdown available.")
                                
                                if email_sent:
                                    st.success("📧 A copy of your grade has been sent to your email.")
                                elif student_email:
                                    st.warning("⚠️ Email could not be sent, but your grade is shown above.")
                                else:
                                    st.info("💡 No email provided. Your grade is shown above.")
                                
                                st.caption("Your grade and feedback are private and only visible to you and your teacher.")
                
                # ---- TEST BUTTON - OUTSIDE THE FORM ----
                # This is placed OUTSIDE the form to avoid widget conflicts
                if image_to_submit is not None:
                    if st.button("🔬 Test Image Reading", key="test_image_reading"):
                        with st.spinner("Testing image reading..."):
                            try:
                                img_bytes = image_to_submit.getvalue()
                                result = grading.test_image_reading(img_bytes)
                                if result.startswith("ERROR:"):
                                    st.error(f"❌ {result}")
                                else:
                                    st.success("✅ Image read successfully!")
                                    st.write("**What the API sees:**")
                                    st.write(result)
                            except Exception as e:
                                st.error(f"❌ Test failed: {str(e)}")
    
    # ---------- My Results ----------
    elif page == "My Results":
        st.subheader("📖 View Your Results")
        
        st.info("Enter your email address to view your own grades and feedback. No other students can see your results.")
        
        view_email = st.text_input("Enter your email address:", placeholder="john@example.com")
        
        if view_email:
            if not email_utils.is_valid_email(view_email):
                st.error("Please enter a valid email address.")
            else:
                submissions = db.get_submissions_by_email(class_id, view_email)
                
                if not submissions:
                    st.warning(f"No submissions found for {view_email}. Please check your email or submit some work first.")
                else:
                    st.success(f"Found {len(submissions)} submission(s) for {view_email}")
                    
                    for sub in submissions:
                        scheme_data = sub.get('mark_schemes', {})
                        assignment_name = scheme_data.get('assignment_name', 'Unknown Assignment')
                        question = scheme_data.get('question', '')
                        total_points = scheme_data.get('total_points', 0)
                        
                        st.markdown(f"### 📝 {assignment_name}")
                        st.write(f"**Score:** {sub['grade']}/{total_points}")
                        
                        with st.expander("📋 View Full Feedback and Question"):
                            st.write(f"**Question:** {question}")
                            
                            try:
                                feedback_data = json.loads(sub['feedback'])
                                if isinstance(feedback_data, dict):
                                    if 'overall_feedback' in feedback_data:
                                        st.info(f"**Overall:** {feedback_data['overall_feedback']}")
                                    
                                    if 'feedback_table' in feedback_data and feedback_data['feedback_table']:
                                        st.write("**Detailed Breakdown:**")
                                        display_feedback_table(feedback_data['feedback_table'])
                                    else:
                                        st.write(sub['feedback'])
                                else:
                                    st.write(sub['feedback'])
                            except:
                                st.write(sub['feedback'])
                            
                            st.write(f"**Submitted:** {sub['graded_at']}")
                        
                        st.divider()
