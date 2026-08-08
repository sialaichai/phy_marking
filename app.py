import streamlit as st
import database as db
import grading
import email_utils
from PIL import Image
import io
import traceback

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
    /* Danger buttons (delete) */
    .stButton button[kind="secondary"] {
        background-color: #f44336;
    }
    .stButton button[kind="secondary"]:hover {
        background-color: #d32f2f;
    }
    /* Make form inputs larger for touch */
    .stTextInput input, .stTextArea textarea, .stSelectbox select {
        font-size: 16px !important;
        padding: 12px !important;
    }
    /* Mobile responsiveness */
    @media (max-width: 768px) {
        .stButton button {
            font-size: 20px;
            padding: 15px 30px;
        }
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
            font-size: 1.5em !important;
        }
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

    # ---------- Upload Mark Scheme (INDEPENDENT OF CLASS) ----------
    elif page == "Upload Mark Scheme":
        st.subheader("📤 Upload a New Mark Scheme")
        
        with st.form("mark_scheme_form"):
            assignment_name = st.text_input("Assignment Name", placeholder="e.g., Physics Quiz 1")
            question = st.text_area("Question", placeholder="Write the question here.", height=100)
            rubric = st.text_area("Marking Rubric / Expected Answer", placeholder="Describe what a good answer should include.", height=150)
            total_points = st.number_input("Total Points", min_value=1, max_value=100, value=10)
            is_trial = st.checkbox("🧪 This is trial data (for testing)", value=True)
            
            submitted = st.form_submit_button(
                "💾 Save Mark Scheme",
                use_container_width=True,
                type="primary"
            )
            if submitted:
                if assignment_name and question and rubric:
                    scheme_id = db.add_mark_scheme(teacher_id, assignment_name, question, rubric, total_points, is_trial)
                    if scheme_id:
                        st.success(f"Mark scheme saved! ID: {scheme_id}")
                    else:
                        st.error("Failed to save.")
                else:
                    st.error("All fields are required.")

    # ---------- View Marks (GROUPED BY CLASS) ----------
    elif page == "View Marks":
        st.subheader("📊 View Marks by Assignment and Class")
        
        # Toggle to show/hide trial data
        show_trial = st.checkbox("Show trial data", value=True)
        schemes = db.get_teacher_mark_schemes(teacher_id, include_trial=show_trial)
        
        if not schemes:
            st.info("No mark schemes found.")
        else:
            for scheme in schemes:
                trial_tag = "🧪 TRIAL" if scheme.get('is_trial', True) else "✅ REAL"
                st.markdown(f"### **{scheme['assignment_name']}** {trial_tag}")
                
                # Get all submissions for this scheme (grouped by class)
                submissions = db.get_submissions_by_scheme(scheme['id'])
                
                if not submissions:
                    st.write("No submissions yet.")
                else:
                    # Group by class
                    classes = {}
                    for sub in submissions:
                        class_name = sub.get('classes', {}).get('class_name', 'Unknown Class')
                        if class_name not in classes:
                            classes[class_name] = []
                        classes[class_name].append(sub)
                    
                    # Display each class
                    for class_name, class_subs in classes.items():
                        st.write(f"**📚 Class: {class_name}**")
                        for sub in class_subs:
                            sub_trial_tag = "🧪" if sub.get('is_trial', True) else ""
                            st.write(f"- **{sub['student_name']}** {sub_trial_tag}: {sub['grade']}/{scheme['total_points']} – {sub['feedback']}")
                    st.divider()

    # ---------- Manage Trial Data ----------
    elif page == "Manage Trial Data":
        st.subheader("🧹 Manage Trial Data")
        st.warning("⚠️ This section allows you to delete trial data. These actions are permanent and cannot be undone!")
        st.info("Trial data is marked with 🧪 and is meant for testing purposes only.")
        
        # Get all schemes for this teacher
        schemes = db.get_teacher_mark_schemes(teacher_id, include_trial=True)
        trial_schemes = [s for s in schemes if s.get('is_trial', True)]
        real_schemes = [s for s in schemes if not s.get('is_trial', False)]
        
        if not trial_schemes:
            st.success("✅ No trial data found. Everything is clean!")
        else:
            st.write(f"Found **{len(trial_schemes)}** trial assignments.")
            
            # Option 1: Delete submissions for a specific scheme
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
            
            # Option 2: Convert trial data to real data
            st.subheader("🔄 Convert Trial Data to Real Data")
            st.info("This will mark the assignment and all its submissions as REAL data.")
            selected_convert = st.selectbox("Select trial assignment to convert", list(scheme_options.keys()), key="convert_select")
            scheme_id_convert = scheme_options[selected_convert]
            if st.button("✅ Convert to REAL data", use_container_width=True):
                db.convert_to_real_data(scheme_id_convert)
                st.success("Assignment converted to REAL data!")
                st.rerun()
            
            # Option 3: Delete all trial data (nuclear option)
            st.divider()
            st.subheader("🔥 Delete ALL Trial Data")
            st.warning("This will delete ALL your trial assignments and their submissions.")
            
            confirm = st.checkbox("I understand this is permanent and cannot be undone")
            if confirm and st.button("⚠️ Delete ALL trial data", use_container_width=True, type="primary"):
                db.delete_all_trial_data(teacher_id)
                st.success("All trial data deleted!")
                st.rerun()
        
        # Show real data summary
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

    # Student page options
    page = st.sidebar.radio("Go to:", ["Submit Work", "My Results"])

    # ---------- Submit Work ----------
    if page == "Submit Work":
        st.header("📸 Submit Your Work")

        # Add this temporarily to your student submission page to test the API
        #if st.button("🧪 Test DeepSeek API"):
         #   result = grading.test_deepseek_api()
        #    st.code(result)

        
        # Get all mark schemes for this teacher (not just this class)
        supabase = db.get_supabase()
        
        # First get the teacher_id from the class
        class_info = supabase.table("classes").select("teacher_id").eq("id", class_id).execute()
        if not class_info.data:
            st.error("Class not found.")
        else:
            teacher_id_from_class = class_info.data[0]["teacher_id"]
            
            # Now get all mark schemes for this teacher (show trial data if present)
            schemes = supabase.table("mark_schemes").select("*").eq("teacher_id", teacher_id_from_class).execute().data
            
            if not schemes:
                st.warning("No assignments available from your teacher yet.")
            else:
                scheme_options = {f"{s['assignment_name']}": s['id'] for s in schemes}
                selected_label = st.selectbox("Choose assignment", list(scheme_options.keys()))
                scheme_id = scheme_options[selected_label]
                scheme = db.get_mark_scheme(scheme_id)
                if scheme:
                    st.info(f"**Question:** {scheme['question']}")
                    st.write(f"**Total points:** {scheme['total_points']}")

                # Mobile-friendly form with clear submit button
                with st.form("submission_form"):
                    student_name = st.text_input("Your Full Name", placeholder="e.g., John Doe")
                    student_email = st.text_input("Your Email Address (optional)", placeholder="john@example.com")
                    st.caption("📧 If provided, your grade and feedback will be sent to this email address.")
                    
                    uploaded_file = st.file_uploader("Take a photo or upload an image of your answer", type=["jpg", "jpeg", "png"])
                    
                    # Add this in the student submission section, after the uploaded file preview
                    if uploaded_file is not None:
                        image = Image.open(uploaded_file)
                        st.image(image, caption="Your submission", width=300)
                        
                        # ---- Test button ----
                        if st.button("🧪 Test API with this image"):
                            with st.spinner("Testing API..."):
                                img_bytes = uploaded_file.getvalue()
                                result = grading.test_deepseek_api()
                                st.code(f"API Test: {result}")
                                
                                # Test actual image processing
                                try:
                                    processed = grading.process_image_for_api(img_bytes)
                                    st.success(f"Image processed: {len(processed)} bytes (original: {len(img_bytes)} bytes)")
                    
                    submitted = st.form_submit_button(
                        "📨 Submit for Grading",
                        use_container_width=True,
                        type="primary"
                    )
                    
                    if submitted:
                        # Validation
                        if not student_name:
                            st.error("Please enter your name.")
                        elif uploaded_file is None:
                            st.error("Please upload an image of your work.")
                        else:
                            with st.spinner("Grading..."):
                                img_bytes = uploaded_file.getvalue()
                                
                                # Grade the submission
                                grade, feedback = grading.grade_submission(
                                    img_bytes, 
                                    scheme["question"], 
                                    scheme["rubric"], 
                                    scheme["total_points"],
                                    use_real_api=True
                                )
                                
                                # Save to database with class_id
                                is_trial = scheme.get('is_trial', True)
                                
                                # Try to save with email if provided and valid
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
                                            feedback,
                                            is_trial=is_trial
                                        )
                                        
                                        # Send email notification
                                        email_status = email_utils.send_grade_email(
                                            student_email, 
                                            student_name, 
                                            scheme["question"], 
                                            grade, 
                                            scheme["total_points"], 
                                            feedback
                                        )
                                        if "sent successfully" in email_status.lower():
                                            email_sent = True
                                    except Exception as e:
                                        # Fallback: save without email
                                        db.add_submission(
                                            scheme_id, 
                                            class_id,
                                            student_name, 
                                            "", 
                                            "Image processed", 
                                            grade, 
                                            feedback
                                        )
                                else:
                                    # Save without email
                                    db.add_submission(
                                        scheme_id, 
                                        class_id,
                                        student_name, 
                                        "", 
                                        "Image processed", 
                                        grade, 
                                        feedback
                                    )
                                
                                # Show success messages
                                st.success(f"✅ Grading complete! You scored **{grade}/{scheme['total_points']}**.")
                                st.info(f"**Feedback:** {feedback}")
                                
                                if email_sent:
                                    st.success("📧 A copy of your grade has been sent to your email.")
                                elif student_email:
                                    st.warning("⚠️ Email could not be sent, but your grade is shown above.")
                                else:
                                    st.info("💡 No email provided. Your grade is shown above.")
                                
                                st.caption("Your grade and feedback are private and only visible to you and your teacher.")

    # ---------- My Results ----------
    elif page == "My Results":
        st.subheader("📖 View Your Results")
        
        st.info("Enter your email address to view your own grades and feedback. No other students can see your results.")
        
        # Ask student for their email (to view results)
        view_email = st.text_input("Enter your email address:", placeholder="john@example.com")
        
        if view_email:
            if not email_utils.is_valid_email(view_email):
                st.error("Please enter a valid email address.")
            else:
                # Get submissions for this email in this class
                submissions = db.get_submissions_by_email(class_id, view_email)
                
                if not submissions:
                    st.warning(f"No submissions found for {view_email}. Please check your email or submit some work first.")
                else:
                    st.success(f"Found {len(submissions)} submission(s) for {view_email}")
                    
                    for sub in submissions:
                        # Get scheme details from the joined data
                        scheme_data = sub.get('mark_schemes', {})
                        assignment_name = scheme_data.get('assignment_name', 'Unknown Assignment')
                        question = scheme_data.get('question', '')
                        total_points = scheme_data.get('total_points', 0)
                        
                        st.markdown(f"### 📝 {assignment_name}")
                        st.write(f"**Score:** {sub['grade']}/{total_points}")
                        
                        with st.expander("📋 View Full Feedback and Question"):
                            st.write(f"**Question:** {question}")
                            st.write(f"**Feedback:** {sub['feedback']}")
                            st.write(f"**Submitted:** {sub['graded_at']}")
                        
                        st.divider()
