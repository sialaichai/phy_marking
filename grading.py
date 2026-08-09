import streamlit as st
import requests
import base64
import json
import re
from PIL import Image, ImageEnhance, ImageFilter
import io

# ---- Try to import Tesseract ----
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

# ---- Get API key from Streamlit secrets ----
DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", None)

print("===== grading.py LOADED (Tesseract mode) =====")

# ============================================================
#                    IMAGE PREPROCESSING (for OCR)
# ============================================================

def preprocess_for_ocr(image_bytes):
    """
    Preprocess image to improve OCR accuracy.
    Works for both typed and camera images.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to grayscale
        if image.mode != 'L':
            image = image.convert('L')
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
        
        # Sharpen
        image = image.filter(ImageFilter.SHARPEN)
        
        # Binarize (convert to black and white)
        threshold = 150
        image = image.point(lambda p: 255 if p > threshold else 0)
        
        # Resize if too large (Tesseract works best at ~300 DPI)
        max_size = 2000
        if image.width > max_size or image.height > max_size:
            image.thumbnail((max_size, max_size), Image.LANCZOS)
        
        # Save to bytes
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()
        
    except Exception as e:
        # If preprocessing fails, return original bytes
        return image_bytes

# ============================================================
#                    OCR USING TESSERACT
# ============================================================

def extract_text_with_tesseract(image_bytes):
    """
    Extract text using Tesseract OCR with preprocessing.
    Handles both typed and camera images.
    """
    if not TESSERACT_AVAILABLE:
        return "", "Tesseract not installed. Please add pytesseract to requirements.txt and install system Tesseract."
    
    try:
        # Preprocess
        processed_bytes = preprocess_for_ocr(image_bytes)
        image = Image.open(io.BytesIO(processed_bytes))
        
        # Use Tesseract with configuration for English text
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.,;:()[]{}!?@#$%^&*+-=/_\\ ' 
        text = pytesseract.image_to_string(image, lang='eng', config=custom_config)
        
        # Clean up extra whitespace
        text = '\n'.join([line.strip() for line in text.splitlines() if line.strip()])
        return text, None
    except Exception as e:
        return "", f"Tesseract error: {str(e)}"

# ============================================================
#                    DEEPSEEK TEXT-ONLY API
# ============================================================

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
        "temperature": 0.0
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            return f"ERROR: {response.status_code} - {response.text[:200]}"
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"ERROR: {str(e)}"

# ============================================================
#                    TEST OCR FUNCTION (for app.py)
# ============================================================

def test_image_reading(image_bytes):
    """Test OCR on an image and return extracted text."""
    text, error = extract_text_with_tesseract(image_bytes)
    if error:
        return f"ERROR: {error}"
    if not text:
        return "No text extracted."
    return text

# ============================================================
#                    MAIN GRADING FUNCTION
# ============================================================

def grade_submission(image_bytes, question, rubric, total_points, use_real_api=True):
    """
    Grade student submission.
    Step 1: Extract text with Tesseract
    Step 2: Grade with DeepSeek text-only API
    Returns: (score, feedback_table, overall_feedback)
    """
    if not use_real_api or not DEEPSEEK_API_KEY:
        return simulate_grade(question, rubric, "", total_points)
    
    # STEP 1: Extract text from image
    student_text, error = extract_text_with_tesseract(image_bytes)
    
    if error:
        return 0, [{"mark": 0, "rationale": f"OCR failed: {error}"}], f"OCR Error: {error}"
    
    if not student_text or len(student_text) < 5:
        return 0, [{"mark": 0, "rationale": "No text could be extracted from the image. Please ensure the image is clear and well-lit."}], "No text extracted."
    
    # STEP 2: Grade using text-only API
    grading_prompt = f"""You are a strict teacher. Grade the student's answer based on the rubric.

**STUDENT'S ANSWER (extracted from image):**
{student_text}

**QUESTION:**
{question}

**RUBRIC:**
{rubric}

**TOTAL POINTS:** {total_points}

**Instructions:**
1. Compare the student's answer to the rubric.
2. Award points based on what the student wrote.
3. Provide a clear rationale for each mark.

**Return JSON ONLY:**
{{
    "total_score": <number between 0 and {total_points}>,
    "feedback_table": [
        {{
            "mark": <numeric points for this criterion>,
            "rationale": "<explanation based on the student's answer>"
        }}
    ],
    "overall_feedback": "<summary>"
}}

**Important:**
- The student's answer is quoted above. ONLY use that.
- Each rubric criterion gets one row.
- The mark must be a number only.
- Do NOT quote the rubric as the student's answer.
"""
    
    response = call_deepseek_text_only(grading_prompt)
    
    if response.startswith("ERROR:"):
        return 0, [{"mark": 0, "rationale": response}], f"API Error: {response}"
    
    # Parse JSON
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
        score = int(data.get("total_score", 0))
        feedback_table = data.get("feedback_table", [])
        overall_feedback = data.get("overall_feedback", "No summary.")
        
        if score < 0:
            score = 0
        elif score > total_points:
            score = total_points
        
        # Clean table
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
                "rationale": row.get("rationale", "No rationale.")
            })
        
        return score, cleaned_table, overall_feedback
        
    except json.JSONDecodeError as e:
        return 0, [{"mark": "0", "rationale": f"Parse error: {str(e)}"}], f"Error: {str(e)}"
    except Exception as e:
        return 0, [{"mark": "0", "rationale": f"Unexpected error: {str(e)}"}], f"Error: {str(e)}"

# ============================================================
#                    SIMULATED GRADE (FALLBACK)
# ============================================================

def simulate_grade(question, rubric, student_answer, total_points):
    """Placeholder grading when API not available."""
    keywords = re.findall(r'\b[a-zA-Z]{3,}\b', rubric)[:3]
    found = sum(1 for kw in keywords if kw.lower() in student_answer.lower())
    score = min(found, total_points)
    feedback_table = []
    for kw in keywords[:3]:
        earned = 1 if kw.lower() in student_answer.lower() else 0
        feedback_table.append({
            "mark": earned,
            "rationale": f"{'✓ Found' if earned else '✗ Not found'} in student answer."
        })
    return score, feedback_table, "Simulated grading."

# ============================================================
#                    LEGACY / ALIAS
# ============================================================

def grade_work(image_bytes, question, rubric, total_points, use_real_api=True):
    """Alias for grade_submission."""
    return grade_submission(image_bytes, question, rubric, total_points, use_real_api)
