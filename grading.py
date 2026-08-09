import streamlit as st
import requests
import base64
import json
import re
from PIL import Image
import io

# ---- Get API key from Streamlit secrets ----
DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", None)

# ============================================================
#                    IMAGE PROCESSING
# ============================================================

def process_image_for_api(image_bytes):
    """Process and optimize image for DeepSeek API."""
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

# ============================================================
#                    API CALLS
# ============================================================

def call_deepseek_api(image_bytes, prompt_text):
    """Call DeepSeek API with image embedded as Markdown."""
    if not DEEPSEEK_API_KEY:
        return "ERROR: No DeepSeek API key found."
    
    try:
        processed_bytes = process_image_for_api(image_bytes)
    except Exception as e:
        return f"ERROR: {str(e)}"
    
    try:
        base64_image = base64.b64encode(processed_bytes).decode('utf-8')
    except Exception as e:
        return f"ERROR: Base64 encoding failed: {str(e)}"
    
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    image_markdown = f"![image](data:image/jpeg;base64,{base64_image})"
    full_prompt = f"{prompt_text}\n\n{image_markdown}"
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": full_prompt}],
        "max_tokens": 1500,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            return f"ERROR: API returned {response.status_code} - {response.text[:200]}"
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        return f"ERROR: {str(e)}"

def call_deepseek_text_only(prompt_text):
    """Call DeepSeek API without image (text only)."""
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

# ============================================================
#                    OCR (TEXT EXTRACTION)
# ============================================================

def extract_text_from_image(image_bytes):
    """Extract text from image using OCR."""
    prompt = """Extract ALL text from this image. This is a student's answer.
Return ONLY the text you see in the image, nothing else.
Do not add any extra text or explanations.
"""
    response = call_deepseek_api(image_bytes, prompt)
    if response.startswith("ERROR:"):
        return "", response
    return response.strip(), None

# ============================================================
#                    SIMULATED GRADING (FALLBACK)
# ============================================================

def simulate_grading(question, rubric, total_points):
    """
    Simulated grading when API is not available.
    Returns: (score, feedback_table, summary, extracted_text)
    """
    extracted_text = "Simulated grading (API not used)."
    
    if total_points >= 3:
        score = 2
        table = [
            {"rubric": "Criterion 1", "mark": "1"},
            {"rubric": "Criterion 2", "mark": "1"},
            {"rubric": "Criterion 3", "mark": "0"}
        ]
        summary = "Simulated grading."
    else:
        score = min(1, total_points)
        table = [{"rubric": "Overall", "mark": str(score)}]
        summary = "Simulated grading."
    
    return score, table, summary, extracted_text

# ============================================================
#                    MAIN GRADING FUNCTION
# ============================================================

def grade_work(image_bytes, question, rubric, total_points, use_real_api=True):
    """
    Grade student submission.
    Returns: (score, feedback_table, summary, extracted_text)
    """
    # If API not available or disabled, use simulation
    if not use_real_api or not DEEPSEEK_API_KEY:
        return simulate_grading(question, rubric, total_points)
    
    # STEP 1: Extract text from the image
    student_text, error = extract_text_from_image(image_bytes)
    
    if error:
        return 0, [{"rubric": "OCR Error", "mark": "0"}], f"OCR failed: {error}", student_text if student_text else ""
    
    if not student_text or len(student_text) < 5:
        return 0, [{"rubric": "No text extracted", "mark": "0"}], "No text could be read from the image.", student_text if student_text else ""
    
    # STEP 2: Grade the extracted text (text-only API call)
    grading_prompt = f"""Grade the student's answer.

STUDENT'S ANSWER:
{student_text}

RUBRIC:
{rubric}

TOTAL POINTS: {total_points}

Return JSON ONLY:
{{
    "score": <number>,
    "feedback": [
        {{"rubric": "<criterion>", "mark": <number>}}
    ]
}}
"""
    
    response = call_deepseek_text_only(grading_prompt)
    
    if response.startswith("ERROR:"):
        return 0, [{"rubric": "Grading error", "mark": "0"}], response, student_text
    
    # Parse the JSON response
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
        score = int(data.get("score", 0))
        feedback = data.get("feedback", [])
        
        # Clamp score
        if score < 0:
            score = 0
        elif score > total_points:
            score = total_points
        
        # Format feedback table
        if not feedback:
            feedback = [{"rubric": "Overall", "mark": str(score)}]
        
        table = []
        for item in feedback:
            mark_val = item.get("mark", 0)
            if isinstance(mark_val, (int, float)):
                numeric_mark = str(mark_val)
            elif isinstance(mark_val, str):
                match = re.search(r'(\d+(?:\.\d+)?)', mark_val)
                numeric_mark = match.group(1) if match else "0"
            else:
                numeric_mark = "0"
            
            table.append({
                "mark": numeric_mark,
                "rubric": item.get("rubric", "")
            })
        
        return score, table, "Grading complete.", student_text
        
    except json.JSONDecodeError as e:
        return 0, [{"rubric": "Parse error", "mark": "0"}], f"Error: {str(e)}", student_text
    except Exception as e:
        return 0, [{"rubric": "Unexpected error", "mark": "0"}], f"Error: {str(e)}", student_text
