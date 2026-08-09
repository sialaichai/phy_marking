import streamlit as st
import requests
import base64
import json
import re
from PIL import Image
import io

DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", None)

def test_deepseek_api():
    """Test the DeepSeek API connection with a simple prompt."""
    if not DEEPSEEK_API_KEY:
        return "ERROR: No API key found"
    
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": "Say 'Hello' in one word."}
        ],
        "max_tokens": 5,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            reply = result['choices'][0]['message']['content']
            return f"✅ API works! Response: '{reply}'"
        else:
            return f"❌ API error: {response.status_code} - {response.text[:100]}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

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
    This is the WORKING VERSION - only rubric field added.
    """
    if not use_real_api or not DEEPSEEK_API_KEY:
        return simulate_grading(question, rubric, total_points)
    
    # Build prompt - using the format that was working
    prompt = f"""You are a strict teacher. Grade the student's answer based on the question and rubric.

**Question:**
{question}

**Marking Rubric / Expected Answer:**
{rubric}

**Total Points:** {total_points}

**Student's Answer:** (See the uploaded image. Read and analyze all text from it.)

Please respond with valid JSON ONLY in the following format:

{{
    "total_score": <total points awarded out of {total_points}>,
    "feedback_table": [
        {{
            "mark": "<numeric point value for this criterion, e.g., '1' or '2'>",
            "rubric": "<the rubric criterion this refers to>",
            "rationale": "<detailed explanation of why this mark was awarded or not>"
        }}
    ],
    "overall_feedback": "<general feedback on the student's answer, strengths and areas for improvement>"
}}

Rules:
- The total_score must be an integer between 0 and {total_points}.
- Each criterion from the rubric should have its own row in the feedback_table.
- The "mark" field should ONLY be a number (e.g., "1", "2", "0").
- The "rubric" field should be the specific rubric criterion being evaluated.
- The "rationale" should explain why the student got or didn't get the mark.
- Be fair and consistent with the rubric.
- If the answer is completely wrong, missing, or illegible, set total_score to 0.
"""

    # Call the API
    response_text = call_deepseek_api(image_bytes, prompt)
    
    if response_text.startswith("ERROR:"):
        return 0, [], f"ERROR: {response_text}"
    
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
        
        total_score = int(data.get("total_score", 0))
        feedback_table = data.get("feedback_table", [])
        overall_feedback = data.get("overall_feedback", "No overall feedback provided.")
        
        # Ensure total_score is valid
        if total_score < 0:
            total_score = 0
        elif total_score > total_points:
            total_score = total_points
        
        # Validate feedback_table
        if not feedback_table or not isinstance(feedback_table, list):
            feedback_table = [
                {"mark": "0", "rubric": "Overall", "rationale": "No detailed breakdown available."}
            ]
        
        # Clean each row
        cleaned_table = []
        for row in feedback_table:
            # Clean mark
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
            rationale = row.get("rationale", "No rationale provided.")
            
            cleaned_table.append({
                "mark": numeric_mark,
                "rubric": rubric_text,
                "rationale": rationale.strip()
            })
        
        return total_score, cleaned_table, overall_feedback
        
    except json.JSONDecodeError as e:
        return 0, [{"mark": "0", "rubric": "Error", "rationale": f"Failed to parse response: {str(e)}"}], f"Error: {str(e)}"
    except Exception as e:
        return 0, [{"mark": "0", "rubric": "Error", "rationale": f"Unexpected error: {str(e)}"}], f"Error: {str(e)}"

def simulate_grading(question, rubric, total_points):
    """Simulated grading when API is not available."""
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
