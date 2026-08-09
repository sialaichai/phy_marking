import streamlit as st
import requests
import base64
import json
import re
from PIL import Image
import io

DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", None)

def process_image_for_api(image_bytes):
    """
    Process and optimize image for DeepSeek API.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        max_size = 1024
        if image.width > max_size or image.height > max_size:
            image.thumbnail((max_size, max_size), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=80, optimize=True)
        processed_bytes = buffer.getvalue()
        if len(processed_bytes) > 4 * 1024 * 1024:
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=50, optimize=True)
            processed_bytes = buffer.getvalue()
        return processed_bytes
    except Exception as e:
        raise Exception(f"Image processing failed: {str(e)}")

def call_deepseek_api(image_bytes, prompt_text):
    """
    Call DeepSeek API with image embedded as Markdown.
    """
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
    full_prompt = f"{prompt_text}\n\nHere is the student's answer as an image. Read the image carefully:\n{image_markdown}"
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": full_prompt}
        ],
        "max_tokens": 1500,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            return f"ERROR: API returned {response.status_code} - {response.text[:200]}"
        result = response.json()
        return result['choices'][0]['message']['content']
    except requests.exceptions.Timeout:
        return "ERROR: Request timed out."
    except requests.exceptions.RequestException as e:
        return f"ERROR: Request failed: {str(e)}"
    except Exception as e:
        return f"ERROR: Unexpected error: {str(e)}"

def grade_submission(image_bytes, question, rubric, total_points, use_real_api=True):
    """
    Grade student submission using DeepSeek API.
    """
    if not use_real_api or not DEEPSEEK_API_KEY:
        return simulate_grading(question, rubric, total_points)
    
    # ================================================================
    # STEP 1: Extract ONLY the student's text from the image
    # ================================================================
    ocr_prompt = """Extract ALL text from this image. This is a student's handwritten or typed answer.

Rules:
- ONLY transcribe what is written in the image.
- Do NOT add any extra text, explanations, or commentary.
- Do NOT mention the rubric or grading.
- Just copy the text exactly as it appears.
- If you see handwriting, transcribe it as accurately as possible.
- If you see typed text, copy it exactly.
- Return ONLY the extracted text, nothing else.
"""
    
    ocr_response = call_deepseek_api(image_bytes, ocr_prompt)
    
    if ocr_response.startswith("ERROR:"):
        return 0, [{"mark": "0", "rationale": f"OCR failed: {ocr_response}"}], "OCR Error"
    
    student_text = ocr_response.strip()
    
    # If no text was extracted, try a different approach
    if not student_text or len(student_text) < 5:
        ocr_prompt_alt = """What is written in this image? Please transcribe the text you see."""
        ocr_response = call_deepseek_api(image_bytes, ocr_prompt_alt)
        if not ocr_response.startswith("ERROR:"):
            student_text = ocr_response.strip()
    
    if not student_text or len(student_text) < 5:
        return 0, [{"mark": "0", "rationale": "No text could be extracted from the image. Please ensure the handwriting is clear and well-lit."}], "No text extracted"
    
    # ================================================================
    # STEP 2: Grade the extracted text with rubric criteria
    # ================================================================
    grading_prompt = f"""You are a teacher. Grade the student's answer based on the rubric.

**STUDENT'S ANSWER (extracted from image):**
"{student_text}"

**RUBRIC (marking criteria):**
{rubric}

**QUESTION:**
{question}

**Total Points:** {total_points}

**Instructions:**
1. Compare the STUDENT'S ANSWER to the RUBRIC.
2. Award points based on what the student wrote.
3. For each criterion in the rubric, create a feedback item.

**Return ONLY valid JSON:**
{{
    "score": <total points between 0 and {total_points}>,
    "feedback": [
        {{
            "criterion": "<EXACTLY the rubric criterion being evaluated>",
            "points": <points awarded for this criterion>,
            "rationale": "<explain why based on the student's answer>"
        }}
    ],
    "summary": "<brief overall feedback>"
}}

**IMPORTANT:**
- The STUDENT'S ANSWER is quoted above in quotes.
- ONLY refer to what is in the quotes for grading.
- The "criterion" field should contain the rubric criterion being evaluated.
- Do NOT use the rubric as the student's answer.
- Each rubric criterion should have a separate feedback entry.
"""
    
    # Use text-only API call for grading (no image)
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": grading_prompt}
        ],
        "max_tokens": 1500,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            fallback_response = call_deepseek_api(image_bytes, grading_prompt)
            if fallback_response.startswith("ERROR:"):
                return 0, [{"mark": "0", "rationale": f"Grading failed: {fallback_response}"}], "Grading Error"
            response_text = fallback_response
        else:
            result = response.json()
            response_text = result['choices'][0]['message']['content']
    except Exception as e:
        return 0, [{"mark": "0", "rationale": f"Error: {str(e)}"}], "Error"
    
    # Parse JSON response
    try:
        clean = response_text.strip()
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
        feedback_list = data.get("feedback", [])
        summary = data.get("summary", "No summary provided.")
        
        if score < 0:
            score = 0
        elif score > total_points:
            score = total_points
        
        table = []
        if feedback_list:
            for item in feedback_list:
                table.append({
                    "mark": str(item.get("points", 0)),
                    "rubric": item.get("criterion", ""),  # Populate rubric field
                    "rationale": item.get("rationale", "No rationale provided.")
                })
        else:
            table = [{"mark": str(score), "rubric": "", "rationale": summary}]
        
        return score, table, summary
        
    except json.JSONDecodeError as e:
        return 0, [{"mark": "0", "rubric": "", "rationale": f"Parse error: {response_text[:200]}"}], "Parse Error"
    except Exception as e:
        return 0, [{"mark": "0", "rubric": "", "rationale": f"Error: {str(e)}"}], "Error"

def simulate_grading(question, rubric, total_points):
    """Simulated grading when API is not available."""
    if total_points >= 3:
        score = 2
        # Parse rubric into criteria
        rubric_lines = [line.strip() for line in rubric.split('\n') if line.strip()]
        criteria = []
        for line in rubric_lines[:3]:
            if len(line) > 5:
                criteria.append(line)
        while len(criteria) < 3:
            criteria.append("Criterion " + str(len(criteria) + 1))
        
        table = [
            {"mark": "1", "rubric": criteria[0] if len(criteria) > 0 else "Criterion 1", "rationale": "Student demonstrated understanding."},
            {"mark": "1", "rubric": criteria[1] if len(criteria) > 1 else "Criterion 2", "rationale": "Student showed correct working steps."},
            {"mark": "0", "rubric": criteria[2] if len(criteria) > 2 else "Criterion 3", "rationale": "Student missed the final step."}
        ]
    else:
        score = min(1, total_points)
        table = [{"mark": str(score), "rubric": "Overall", "rationale": "Simulated grading (API not used)."}]
    
    return score, table, "Simulated grading (API not available)."

def grade_work(image_bytes, question, rubric, total_points, use_real_api=True):
    """Wrapper for grade_submission."""
    return grade_submission(image_bytes, question, rubric, total_points, use_real_api)
