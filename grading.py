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
        # Open image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed
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
        
        # If still too large, compress more
        if len(processed_bytes) > 4 * 1024 * 1024:  # 4MB
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=50, optimize=True)
            processed_bytes = buffer.getvalue()
        
        return processed_bytes
        
    except Exception as e:
        raise Exception(f"Image processing failed: {str(e)}")

def call_deepseek_api(image_bytes, prompt_text):
    """
    Call DeepSeek API with image embedded as Markdown.
    This is the format that works with DeepSeek.
    """
    if not DEEPSEEK_API_KEY:
        return "ERROR: No DeepSeek API key found."
    
    # Process image
    try:
        processed_bytes = process_image_for_api(image_bytes)
    except Exception as e:
        return f"ERROR: {str(e)}"
    
    # Convert to Base64
    try:
        base64_image = base64.b64encode(processed_bytes).decode('utf-8')
    except Exception as e:
        return f"ERROR: Base64 encoding failed: {str(e)}"
    
    # Prepare API request
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Embed image as Markdown in the text content
    # This is the format that works with DeepSeek
    image_markdown = f"![image](data:image/jpeg;base64,{base64_image})"
    full_prompt = f"{prompt_text}\n\nHere is the student's answer as an image:\n{image_markdown}"
    
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
    
    # Build prompt
    prompt = f"""You are a strict teacher. Grade the student's answer based on the question and rubric.

**Question:**
{question}

**Marking Rubric / Expected Answer:**
{rubric}

**Total Points:** {total_points}

**Student's Answer:** (See the image attached. Read and analyze all text from it.)

Please respond with valid JSON ONLY in the following format:

{{
    "score": <total points awarded out of {total_points}>,
    "feedback": [
        {{
            "mark": "<numeric point value for this criterion>",
            "rationale": "<detailed explanation of why this mark was awarded or not>"
        }}
    ],
    "summary": "<general feedback on the student's answer>"
}}

Rules:
- The score must be an integer between 0 and {total_points}.
- Each criterion from the rubric should have its own row in feedback.
- The "mark" field should ONLY be a number (e.g., "1", "2", "0").
- The "rationale" should explain why the student got or didn't get the mark.
- Base your grading ONLY on what the student actually wrote in the image.
"""

    # Call the API
    response = call_deepseek_api(image_bytes, prompt)
    
    if response.startswith("ERROR:"):
        return 0, [{"mark": "0", "rationale": response}], "API Error"
    
    # Parse JSON response
    try:
        # Clean response
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
        feedback_list = data.get("feedback", [])
        summary = data.get("summary", "No summary provided.")
        
        # Ensure score is within bounds
        if score < 0:
            score = 0
        elif score > total_points:
            score = total_points
        
        # Convert to display format
        table = []
        if feedback_list:
            for item in feedback_list:
                table.append({
                    "mark": str(item.get("mark", 0)),
                    "rationale": item.get("rationale", "No rationale provided.")
                })
        else:
            table = [{"mark": str(score), "rationale": summary}]
        
        return score, table, summary
        
    except json.JSONDecodeError as e:
        return 0, [{"mark": "0", "rationale": f"Could not parse response: {response[:200]}"}], "Parse Error"
    except Exception as e:
        return 0, [{"mark": "0", "rationale": f"Error: {str(e)}"}], "Error"

def simulate_grading(question, rubric, total_points):
    """Simulated grading when API is not available."""
    if total_points >= 3:
        score = 2
        table = [
            {"mark": "1", "rationale": "Student demonstrated understanding of the concept."},
            {"mark": "1", "rationale": "Student showed correct working steps."},
            {"mark": "0", "rationale": "Student missed the final step."}
        ]
    else:
        score = min(1, total_points)
        table = [{"mark": str(score), "rationale": "Simulated grading (API not used)."}]
    
    return score, table, "Simulated grading (API not available)."

def grade_work(image_bytes, question, rubric, total_points, use_real_api=True):
    """Wrapper for grade_submission."""
    return grade_submission(image_bytes, question, rubric, total_points, use_real_api)
