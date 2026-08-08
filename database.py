import streamlit as st
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

# ---- Supabase client ----
def get_supabase() -> Client:
    url = st.secrets["supabase_url"].rstrip('/')
    key = st.secrets["supabase_anon_key"]
    return create_client(url, key)

# ---- Initialisation: create admin account if none ----
def init_db():
    supabase = get_supabase()
    # Check if admin exists
    admin = supabase.table("users").select("*").eq("username", "admin").execute()
    if not admin.data:
        hashed = generate_password_hash("admin123")
        supabase.table("users").insert({
            "username": "admin",
            "password_hash": hashed,
            "role": "admin"
        }).execute()

# ---- Authentication ----
def authenticate(username: str, password: str):
    supabase = get_supabase()
    # First check if it's a teacher/admin
    user = supabase.table("users").select("*").eq("username", username).execute()
    if user.data:
        user_data = user.data[0]
        if check_password_hash(user_data["password_hash"], password):
            return {"type": "user", "data": user_data}
    # Then check if it's a class (student) login
    cls = supabase.table("classes").select("*").eq("class_username", username).execute()
    if cls.data:
        class_data = cls.data[0]
        if check_password_hash(class_data["class_password_hash"], password):
            return {"type": "class", "data": class_data}
    return None

# ---- Admin: create teacher ----
def create_teacher(username: str, password: str):
    supabase = get_supabase()
    hashed = generate_password_hash(password)
    result = supabase.table("users").insert({
        "username": username,
        "password_hash": hashed,
        "role": "teacher"
    }).execute()
    return result.data[0] if result.data else None

def get_all_teachers():
    supabase = get_supabase()
    result = supabase.table("users").select("*").eq("role", "teacher").execute()
    return result.data

def delete_teacher(teacher_id: int):
    supabase = get_supabase()
    supabase.table("users").delete().eq("id", teacher_id).execute()

def reset_teacher_password(teacher_id: int, new_password: str):
    supabase = get_supabase()
    hashed = generate_password_hash(new_password)
    supabase.table("users").update({"password_hash": hashed}).eq("id", teacher_id).execute()

# ---- Teacher: class management ----
def create_class(teacher_id: int, class_name: str, class_username: str, class_password: str):
    supabase = get_supabase()
    hashed = generate_password_hash(class_password)
    result = supabase.table("classes").insert({
        "teacher_id": teacher_id,
        "class_name": class_name,
        "class_username": class_username,
        "class_password_hash": hashed
    }).execute()
    return result.data[0] if result.data else None

def get_teacher_classes(teacher_id: int):
    supabase = get_supabase()
    result = supabase.table("classes").select("*").eq("teacher_id", teacher_id).execute()
    return result.data

def update_class_password(class_id: int, new_password: str):
    supabase = get_supabase()
    hashed = generate_password_hash(new_password)
    supabase.table("classes").update({"class_password_hash": hashed}).eq("id", class_id).execute()

def delete_class(class_id: int):
    supabase = get_supabase()
    supabase.table("classes").delete().eq("id", class_id).execute()

# ---- Teacher: mark schemes ----
def add_mark_scheme(teacher_id: int, class_id: int, assignment_name: str, question: str, rubric: str, total_points: int):
    supabase = get_supabase()
    data = {
        "teacher_id": teacher_id,
        "class_id": class_id,
        "assignment_name": assignment_name,
        "question": question,
        "rubric": rubric,
        "total_points": total_points
    }
    result = supabase.table("mark_schemes").insert(data).execute()
    return result.data[0]["id"] if result.data else None

def get_teacher_mark_schemes(teacher_id: int):
    supabase = get_supabase()
    # join with classes to get class name
    result = supabase.table("mark_schemes").select("*, classes(class_name)").eq("teacher_id", teacher_id).order("created_at", desc=True).execute()
    return result.data

def get_mark_scheme(scheme_id: int):
    supabase = get_supabase()
    result = supabase.table("mark_schemes").select("*").eq("id", scheme_id).execute()
    return result.data[0] if result.data else None

# ---- Submissions ----
def add_submission(mark_scheme_id: int, student_name: str, transcribed_text: str, grade: int, feedback: str):
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

# ---- Generic: Update password for any user (admin or teacher) ----
def update_user_password(user_id: int, new_password: str):
    supabase = get_supabase()
    hashed = generate_password_hash(new_password)
    result = supabase.table("users").update({"password_hash": hashed}).eq("id", user_id).execute()
    return result.data

def get_submissions_by_scheme(scheme_id: int):
    supabase = get_supabase()
    result = supabase.table("submissions").select("*").eq("mark_scheme_id", scheme_id).order("graded_at", desc=True).execute()
    return result.data

# ---- Generic: Update password for any user (admin or teacher) ----
def update_user_password(user_id: int, new_password: str):
    supabase = get_supabase()
    hashed = generate_password_hash(new_password)
    result = supabase.table("users").update({"password_hash": hashed}).eq("id", user_id).execute()
    return result.data

# ---- Trial data management ----
def add_mark_scheme_with_trial(teacher_id: int, class_id: int, assignment_name: str, question: str, rubric: str, total_points: int, is_trial: bool = True):
    supabase = get_supabase()
    data = {
        "teacher_id": teacher_id,
        "class_id": class_id,
        "assignment_name": assignment_name,
        "question": question,
        "rubric": rubric,
        "total_points": total_points,
        "is_trial": is_trial
    }
    result = supabase.table("mark_schemes").insert(data).execute()
    return result.data[0]["id"] if result.data else None

def get_teacher_mark_schemes_filtered(teacher_id: int, include_trial: bool = True):
    supabase = get_supabase()
    query = supabase.table("mark_schemes").select("*, classes(class_name)").eq("teacher_id", teacher_id)
    if not include_trial:
        query = query.eq("is_trial", False)
    result = query.order("created_at", desc=True).execute()
    return result.data

def add_submission_with_trial(mark_scheme_id: int, student_name: str, transcribed_text: str, grade: int, feedback: str, is_trial: bool = True):
    supabase = get_supabase()
    data = {
        "mark_scheme_id": mark_scheme_id,
        "student_name": student_name,
        "transcribed_text": transcribed_text,
        "grade": grade,
        "feedback": feedback,
        "is_trial": is_trial
    }
    result = supabase.table("submissions").insert(data).execute()
    return result.data[0]["id"] if result.data else None

def delete_trial_submissions(scheme_id: int):
    supabase = get_supabase()
    supabase.table("submissions").delete().eq("mark_scheme_id", scheme_id).eq("is_trial", True).execute()

def delete_trial_mark_scheme(scheme_id: int):
    supabase = get_supabase()
    # First delete trial submissions
    supabase.table("submissions").delete().eq("mark_scheme_id", scheme_id).eq("is_trial", True).execute()
    # Then delete the mark scheme itself (only if it's trial data)
    supabase.table("mark_schemes").delete().eq("id", scheme_id).eq("is_trial", True).execute()

def delete_all_trial_data(teacher_id: int):
    supabase = get_supabase()
    # Get all trial mark schemes for this teacher
    trial_schemes = supabase.table("mark_schemes").select("id").eq("teacher_id", teacher_id).eq("is_trial", True).execute()
    if trial_schemes.data:
        scheme_ids = [s["id"] for s in trial_schemes.data]
        # Delete trial submissions for these schemes
        for scheme_id in scheme_ids:
            supabase.table("submissions").delete().eq("mark_scheme_id", scheme_id).eq("is_trial", True).execute()
        # Delete trial mark schemes
        supabase.table("mark_schemes").delete().eq("teacher_id", teacher_id).eq("is_trial", True).execute()
    # Also delete trial classes (optional)
    # supabase.table("classes").delete().eq("teacher_id", teacher_id).eq("is_trial", True).execute()

def convert_to_real_data(scheme_id: int):
    supabase = get_supabase()
    # Mark the scheme as real
    supabase.table("mark_schemes").update({"is_trial": False}).eq("id", scheme_id).execute()
    # Mark all its submissions as real
    supabase.table("submissions").update({"is_trial": False}).eq("mark_scheme_id", scheme_id).execute()

# ---- Add submission with email ----
def add_submission_with_email(mark_scheme_id: int, student_name: str, student_email: str, transcribed_text: str, grade: int, feedback: str, is_trial: bool = True):
    supabase = get_supabase()
    data = {
        "mark_scheme_id": mark_scheme_id,
        "student_name": student_name,
        "student_email": student_email,
        "transcribed_text": transcribed_text,
        "grade": grade,
        "feedback": feedback,
        "is_trial": is_trial
    }
    result = supabase.table("submissions").insert(data).execute()
    return result.data[0]["id"] if result.data else None

# ---- Get submissions by email for a class ----
def get_submissions_by_email(class_id: int, student_email: str):
    supabase = get_supabase()
    # Get all mark schemes for this class
    schemes = supabase.table("mark_schemes").select("id").eq("class_id", class_id).execute()
    if not schemes.data:
        return []
    scheme_ids = [s["id"] for s in schemes.data]
    # Get submissions matching the email
    result = supabase.table("submissions").select("*, mark_schemes(assignment_name, question, total_points)") \
        .in_("mark_scheme_id", scheme_ids) \
        .eq("student_email", student_email) \
        .order("graded_at", desc=True).execute()
    return result.data
