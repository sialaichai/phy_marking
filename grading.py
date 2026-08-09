import streamlit as st
import requests
import base64
import json
import re
from PIL import Image
import io

DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", None)

def call_deepseek_api(image_bytes, prompt_text):
    """
    Call DeepSeek API with image.
    Using the format from DeepSeek documentation.
    """
    if not DEEPSEEK_API_KEY:
        return "ERROR: No DeepSeek API key found."
    
    try:
        # Open and process image
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize if too large
        max_size = 1024
        if image.width > max_size or image.height > max_size:
            image.thumbnail((max_size, max_size), Image.LANCZOS)
        
        # Save as JPEG
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=80, optimize=True)
        processed_bytes = buffer.getvalue()
        
        # Convert to Base64
        base64_image = base64.b64encode(processed_bytes).decode('utf-8')
        
    except Exception as e:
        return f"ERROR: Image processing failed: {str(e)}"
    
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # DeepSeek expects the image as a data URL
    data_url = f"data:image/jpeg;base64,{base64_image}"
    
    # Build the prompt with the image
    full_prompt = f"""{prompt_text}

The student's answer is in the image below:
![image]({data_url})
"""
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "user",
                "content": full_prompt
            }
        ],
        "max_tokens": 1500,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            return f"ERROR: API returned {response.status_code} - {response.text[:300]}"
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
    Grade student submission.
    """
    if not use_real_api or not DEEPSEEK_API_KEY:
        return simulate_grading(question, rubric, total_points)
    
    prompt = f"""You are a strict teacher. Grade the student's answer.

**Question:**
{question}

**Marking Rubric:**
{rubric}

**Total Points:** {total_points}

**Instructions:**
1. Look at the image below.
2. Read the student's answer from the image.
3. Award marks based on the rubric.
4. Return JSON only.

**Output format:**
{{
    "total_score": <number between 0 and {total_points}>,
    "feedback_table": [
        {{
            "mark": "<number>",
            "rubric": "<the rubric criterion>",
            "rationale": "<explanation based on what the student wrote>"
        }}
    ],
    "overall_feedback": "<summary>"
}}

Rules:
- The total_score must be an integer.
- Each rubric criterion gets one row in feedback_table.
- The mark field must be a number only.
- Base your grading on what the student actually wrote.
"""

    response_text = call_deepseek_api(image_bytes, prompt)
    
    if response_text.startswith("ERROR:"):
        return 0, [], f"ERROR: {response_text}"
    
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
        
        total_score = int(data.get("total_score", 0))
        feedback_table = data.get("feedback_table", [])
        overall_feedback = data.get("overall_feedback", "No overall feedback.")
        
        if total_score < 0:
            total_score = 0
        elif total_score > total_points:
            total_score = total_points
        
        if not feedback_table or not isinstance(feedback_table, list):
            feedback_table = [{"mark": "0", "rubric": "Overall", "rationale": "No breakdown."}]
        
        cleaned_table = []
        for row in feedback_table:
            mark_val = row.get("mark", 0)
            if isinstance(mark_val, (int, float)):
                numeric_mark = str(mark_val)
            elif isinstance(mark_val, str):
                match = re.search(r'(\d+(?:\.\d+)?)', mark_val)
                if match:
                    numeric_mark = match.group(1)
                else:
                    numeric_mark = "0"
            else:
                numeric_mark = "0"
            
            rubric_text = row.get("rubric", "")
            rationale = row.get("rationale", "No rationale.")
            
            cleaned_table.append({
                "mark": numeric_mark,
                "rubric": rubric_text,
                "rationale": rationale.strip()
            })
        
        return total_score, cleaned_table, overall_feedback
        
    except json.JSONDecodeError as e:
        return 0, [{"mark": "0", "rubric": "Error", "rationale": f"Parse error: {response_text[:200]}"}], f"Error: {str(e)}"
    except Exception as e:
        return 0, [{"mark": "0", "rubric": "Error", "rationale": f"Unexpected error: {str(e)}"}], f"Error: {str(e)}"

def simulate_grading(question, rubric, total_points):
    """Simulated grading."""
    if total_points >= 3:
        score = 2
        table = [
            {"mark": "1", "rubric": "Criterion 1", "rationale": "Student demonstrated understanding."},
            {"mark": "1", "rubric": "Criterion 2", "rationale": "Student showed correct working steps."},
            {"mark": "0", "rubric": "Criterion 3", "rationale": "Student missed the final step."}
        ]
    else:
        score = min(1, total_points)
        table = [{"mark": str(score), "rubric": "Overall", "rationale": "Simulated grading."}]
    return score, table, "Simulated grading."

def grade_work(image_bytes, question, rubric, total_points, use_real_api=True):
    """Wrapper for grade_submission."""
    return grade_submission(image_bytes, question, rubric, total_points, use_real_api)
