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

def grade_submission(image_bytes, question, rubric, total_points, use_real_api=True):
    """Grade student submission - SIMPLIFIED VERSION."""
    if not use_real_api or not DEEPSEEK_API_KEY:
        return simulate_grading(question, rubric, total_points)
    
    prompt = f"""You are a teacher. Grade the student's answer.

QUESTION:
{question}

RUBRIC:
{rubric}

TOTAL POINTS: {total_points}

The student's answer is in the image above.

Return ONLY JSON:
{{
    "score": <number between 0 and {total_points}>,
    "feedback": [
        {{
            "rubric": "<the rubric criterion>",
            "mark": <number>
        }}
    ]
}}

Rules:
- The score is the total points awarded.
- Each rubric criterion gets one row in feedback.
- The mark must be a number only.
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
        total_score = int(data.get("score", 0))
        feedback = data.get("feedback", [])
        
        if total_score < 0:
            total_score = 0
        elif total_score > total_points:
            total_score = total_points
        
        if not feedback or not isinstance(feedback, list):
            feedback = [{"rubric": "Overall", "mark": total_score}]
        
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
        
        return total_score, table, "Grading complete."
        
    except json.JSONDecodeError as e:
        return 0, [{"rubric": "Error", "mark": "0"}], f"Error: {str(e)}"
    except Exception as e:
        return 0, [{"rubric": "Error", "mark": "0"}], f"Error: {str(e)}"

def simulate_grading(question, rubric, total_points):
    """Simulated grading."""
    if total_points >= 3:
        return 2, [
            {"rubric": "Criterion 1", "mark": "1"},
            {"rubric": "Criterion 2", "mark": "1"},
            {"rubric": "Criterion 3", "mark": "0"}
        ], "Simulated grading."
    else:
        return min(1, total_points), [{"rubric": "Overall", "mark": str(min(1, total_points))}], "Simulated grading."

def grade_work(image_bytes, question, rubric, total_points, use_real_api=True):
    """Wrapper."""
    return grade_submission(image_bytes, question, rubric, total_points, use_real_api)
