import streamlit as st

# ---- Simulated grading (no API key needed) ----
def simulate_grade(question, rubric, student_answer, total_points):
    """
    Simple placeholder: gives points for each keyword from rubric found in answer.
    """
    keywords = rubric.split()[:5]   # simplistic – you can improve
    found = sum(1 for kw in keywords if kw.lower() in student_answer.lower())
    score = min(found, total_points)
    feedback = f"Simulated grading: found {found} keywords. (This is a placeholder – replace with real AI.)"
    return score, feedback

# ---- Placeholders for real DeepSeek calls ----
def call_deepseek_ocr(image_bytes):
    # TODO: implement actual HTTP POST to DeepSeek‑OCR
    return "This is a dummy OCR transcription."

def call_deepseek_chat(question, rubric, student_text, total_points):
    # TODO: implement actual grading prompt
    return simulate_grade(question, rubric, student_text, total_points)

# ---- Main grading function ----
def grade_submission(image_bytes, question, rubric, total_points, use_real_api=False):
    if use_real_api and st.secrets.get("DEEPSEEK_API_KEY"):
        # In future, replace with real calls
        transcribed = call_deepseek_ocr(image_bytes)
        grade, feedback = call_deepseek_chat(question, rubric, transcribed, total_points)
    else:
        # For demo, we use a dummy transcription and simulation
        transcribed = "Student argues that the answer is 42 because ... (dummy OCR)"
        grade, feedback = simulate_grade(question, rubric, transcribed, total_points)
    return transcribed, grade, feedback
