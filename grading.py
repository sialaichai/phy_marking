import streamlit as st
import requests
import base64
import json
import re
from PIL import Image
import io

DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", None)

def process_image_for_api(image_bytes):
    """Process and optimize image."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        max_size = 1024
        if image.width > max_size or image.height > max_size:
            image.thumbnail((max_size, max_size), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=80, optimize=True)
        return buffer.getvalue()
    except Exception as e:
        raise Exception(f"Image processing failed: {str(e)}")

def test_image_reading(image_bytes):
    """Test if the image can be read by the API."""
    if not DEEPSEEK_API_KEY:
        return "ERROR: No API key found."
    
    try:
        processed = process_image_for_api(image_bytes)
        base64_image = base64.b64encode(processed).decode('utf-8')
        
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        prompt = "Describe what you see in this image in 2 sentences. Be specific about what's written."
        full_prompt = f"{prompt}\n\n![image](data:image/jpeg;base64,{base64_image})"
        
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": full_prompt}],
            "max_tokens": 200,
            "temperature": 0.1
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            return f"ERROR: API returned {response.status_code} - {response.text[:200]}"
        
        result = response.json()
        return result['choices'][0]['message']['content']
        
    except Exception as e:
        return f"ERROR: {str(e)}"

def call_deepseek_with_image(image_bytes, prompt_text):
    """Call DeepSeek API with image."""
    if not DEEPSEEK_API_KEY:
        return "ERROR: No API key."
    
    processed = process_image_for_api(image_bytes)
    base64_image = base64.b64encode(processed).decode('utf-8')
    
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    full_prompt = f"{prompt_text}\n\n![image](data:image/jpeg;base64,{base64_image})"
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": full_prompt}],
        "max_tokens": 1500,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            return f"ERROR: {response.status_code} - {response.text[:200]}"
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"ERROR: {str(e)}"

def call_deepseek_text_only(prompt_text):
    """Call DeepSeek API without image."""
    if not DEEPSEEK_API_KEY:
        return "ERROR: No API key."
    
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": 1500,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            return f"ERROR: {response.status_code} - {response.text[:200]}"
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"ERROR: {str(e)}"

def extract_text_from_image(image_bytes):
    """Extract text from the image using OCR."""
    prompt = """Extract ALL text from this image. This is a student's handwritten answer.

Rules:
- ONLY transcribe what is written in the image.
- Do NOT add any extra text or explanations.
- Return ONLY the extracted text, nothing else.
"""
    response = call_deepseek_with_image(image_bytes, prompt)
    if response.startswith("ERROR:"):
        return "", response
    return response.strip(), None

def grade_text_only(student_text, question, rubric, total_points):
    """Grade the extracted text."""
    prompt = f"""You are a teacher. Grade the student's answer.

STUDENT'S ANSWER:
"{student_text}"

QUESTION:
{question}

RUBRIC:
{rubric}

TOTAL POINTS: {total_points}

Output JSON ONLY:
{{
    "total_score": <number between 0 and {total_points}>,
    "feedback_table": [
        {{
            "mark": "<number>",
            "rubric": "<the rubric criterion>",
            "rationale": "<explanation based on the student's answer>"
        }}
    ],
    "overall_feedback": "<summary>"
}}

Rules:
- The student's answer is quoted above. ONLY use that.
- Each rubric criterion gets one row.
- The mark must be a number only.
- Do NOT quote the rubric as the student's answer.
"""
    
    response = call_deepseek_text_only(prompt)
    
    if response.startswith("ERROR:"):
        return 0, [], f"ERROR: {response}"
    
    try:
        clean = response.strip()
        if "```json" in clean:
            match = re.search(r"```json\s*(.*?)\s*```", clean, re.DOTALL)
            if match:
                clean = match.group(1)
        elif "```" in clean:
            match = re.search(r"```\s*(.*?)\s*```", clean, re.DOTALL)
            if match:
                clean = match.group(1)
        
        data = json.loads(clean)
        total_score = int(data.get("total_score", 0))
        feedback_table = data.get("feedback_table", [])
        overall_feedback = data.get("overall_feedback", "No summary.")
        
        if total_score < 0:
            total_score = 0
        elif total_score > total_points:
            total_score = total_points
        
        cleaned_table = []
        for row in feedback_table:
            mark_val = row.get("mark", 0)
            if isinstance(mark_val, (int, float)):
                numeric_mark = str(mark_val)
            elif isinstance(mark_val, str):
                match = re.search(r'(\d+(?:\.\d+)?)', mark_val)
                numeric_mark = match.group(1) if match else "0"
            else:
                numeric_mark = "0"
            
            cleaned_table.append({
                "mark": numeric_mark,
                "rubric": row.get("rubric", ""),
                "rationale": row.get("rationale", "No rationale.")
            })
        
        return total_score, cleaned_table, overall_feedback
        
    except json.JSONDecodeError as e:
        return 0, [], f"ERROR: Failed to parse response: {str(e)}"
    except Exception as e:
        return 0, [], f"ERROR: {str(e)}"

def grade_submission(image_bytes, question, rubric, total_points, use_real_api=True):
    """Main grading function."""
    if not use_real_api or not DEEPSEEK_API_KEY:
        return simulate_grading(question, rubric, total_points)
    
    # STEP 1: Extract text from image
    student_text, error = extract_text_from_image(image_bytes)
    
    if error:
        return 0, [], f"ERROR: OCR failed - {error}"
    
    if not student_text or len(student_text) < 3:
        return 0, [{"mark": "0", "rubric": "OCR", "rationale": "No text could be extracted. Please ensure the image is clear and well-lit."}], "No text extracted."
    
    # STEP 2: Grade the extracted text
    return grade_text_only(student_text, question, rubric, total_points)

def simulate_grading(question, rubric, total_points):
    """Simulated grading."""
    if total_points >= 3:
        return 2, [
            {"mark": "1", "rubric": "Criterion 1", "rationale": "Student demonstrated understanding."},
            {"mark": "1", "rubric": "Criterion 2", "rationale": "Student showed correct working steps."},
            {"mark": "0", "rubric": "Criterion 3", "rationale": "Student missed the final step."}
        ], "Simulated grading."
    else:
        return min(1, total_points), [{"mark": str(min(1, total_points)), "rubric": "Overall", "rationale": "Simulated grading."}], "Simulated grading."

def grade_work(image_bytes, question, rubric, total_points, use_real_api=True):
    """Wrapper."""
    return grade_submission(image_bytes, question, rubric, total_points, use_real_api)
