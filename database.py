import streamlit as st
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

# ---- Supabase client ----
def get_supabase() -> Client:
    # Strip any accidental trailing slash from the URL
    url = st.secrets["supabase_url"].rstrip('/')
    key = st.secrets["supabase_anon_key"]
    return create_client(url, key)

# ---- Initialisation: create default accounts if they don't exist ----
def init_db():
    supabase = get_supabase()
    # Check if teacher exists
    teacher = supabase.table("users").select("*").eq("username", "teacher").execute()
    if not teacher.data:
        # Create teacher
        hashed = generate_password_hash("teacher123")
        supabase.table("users").insert({
            "username": "teacher",
            "password_hash": hashed,
            "role": "teacher"
        }).execute()
    # Check if student exists
    student = supabase.table("users").select("*").eq("username", "student").execute()
    if not student.data:
        hashed = generate_password_hash("student123")
        supabase.table("users").insert({
            "username": "student",
            "password_hash": hashed,
            "role": "student"
        }).execute()

# ---- Authentication ----
def authenticate(username: str, password: str):
    supabase = get_supabase()
    response = supabase.table("users").select("*").eq("username", username).execute()
    if not response.data:
        return None
    user = response.data[0]
    if check_password_hash(user["password_hash"], password):
        return user
    return None

# ---- Teacher: add a mark scheme ----
def add_mark_scheme(teacher_id, assignment_name, question, rubric, total_points):
    supabase = get_supabase()
    data = {
        "teacher_id": teacher_id,
        "assignment_name": assignment_name,
        "question": question,
        "rubric": rubric,
        "total_points": total_points
    }
    result = supabase.table("mark_schemes").insert(data).execute()
    return result.data[0]["id"] if result.data else None

# ---- Get all mark schemes (for display) ----
def get_all_mark_schemes():
    supabase = get_supabase()
    # Join with users to get teacher username (optional)
    result = supabase.table("mark_schemes").select("*").order("created_at", desc=True).execute()
    return result.data   # list of dicts

# ---- Get a single mark scheme by ID ----
def get_mark_scheme(scheme_id):
    supabase = get_supabase()
    result = supabase.table("mark_schemes").select("*").eq("id", scheme_id).execute()
    return result.data[0] if result.data else None

# ---- Student: add a submission ----
def add_submission(mark_scheme_id, student_name, transcribed_text, grade, feedback):
    supabase = get_supabase()
    data = {
        "mark_scheme_id": mark_scheme_id,
        "student_name": student_name,
        "transcribed_text": transcribed_text,
        "grade": grade,
        "feedback": feedback
    }
    result = supabase.table("submissions").insert(data).execute()
    return result.data[0]["id"] if result.data else None

# ---- Get submissions for a given mark scheme (teacher view) ----
def get_submissions_by_scheme(scheme_id):
    supabase = get_supabase()
    result = supabase.table("submissions").select("*").eq("mark_scheme_id", scheme_id).order("graded_at", desc=True).execute()
    return result.data

# ---- Update user password ----
def update_password(user_id: int, new_password: str):
    supabase = get_supabase()
    hashed = generate_password_hash(new_password)
    result = supabase.table("users").update({"password_hash": hashed}).eq("id", user_id).execute()
    return result.data
