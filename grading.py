import streamlit as st
import requests
import base64
import json
import re
from PIL import Image
import io

# Get API key from Streamlit secrets
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
    Returns properly encoded image bytes.
    """
    try:
        # Open image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize if too large (max dimensions 1024x1024)
        max_size = 1024
        if image.width > max_size or image.height > max_size:
            image.thumbnail((max_size, max_size), Image.LANCZOS)
        
        # Save as JPEG with compression
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=80, optimize=True)
        processed_bytes = buffer.getvalue()
        
        # Check size - if still > 4MB, reduce quality further
        if len(processed_bytes) > 4 * 1024 * 1024:  # 4MB
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=50, optimize=True)
            processed_bytes = buffer.getvalue()
        
        return processed_bytes
        
    except Exception as e:
        raise Exception(f"Image processing failed: {str(e)}")

def analyze_image_with_deepseek(image_bytes, prompt_text):
    """
    Send an image to DeepSeek model for analysis using the correct format.
    """
    if not DEEPSEEK_API_KEY:
        return "ERROR: DeepSeek API key not found. Please add it to secrets."
    
    # Step 1: Process and optimize image
    try:
        processed_bytes = process_image_for_api(image_bytes)
    except Exception as e:
        return f"ERROR: {str(e)}"
    
    # Step 2: Convert to Base64
    try:
        base64_image = base64.b64encode(processed_bytes).decode('utf-8')
    except Exception as e:
        return f"ERROR: Base64 encoding failed: {str(e)}"
    
    # Step 3: Prepare API request
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Step 4: Build payload with image as markdown
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
        "temperature": 0.2
    }
    
    # Step 5: Send request
    try:
        response = requests.post(
            url, 
            headers=headers, 
            json=payload, 
            timeout=60
        )
        
        # Handle specific error codes
        if response.status_code == 400:
            error_detail = response.json() if response.text else {}
            error_msg = error_detail.get('error', {}).get('message', 'Unknown error')
            return f"ERROR: Bad Request - {error_msg}"
        elif response.status_code == 401:
            return "ERROR: Invalid API key. Please check your DeepSeek API key in secrets."
        elif response.status_code == 429:
            return "ERROR: Rate limit exceeded. Please wait a few minutes and try again."
        elif response.status_code == 500:
            return "ERROR: DeepSeek server error. Please try again later."
        
        response.raise_for_status()
        
        result = response.json()
        return result['choices'][0]['message']['content']
        
    except requests.exceptions.Timeout:
        return "ERROR: Request timed out. Please try again with a smaller image."
    except requests.exceptions.RequestException as e:
        return f"ERROR: API request failed: {str(e)}"
    except (KeyError, IndexError) as e:
        return f"ERROR: Unexpected API response structure: {str(e)}"

def grade_student_submission(image_bytes, question, rubric, total_points):
    """
    Grade a student's answer using DeepSeek API with clean numeric marks.
    """
    # Construct grading prompt - explicitly request numeric marks only
    prompt = f"""You are a strict teacher. Grade the student's answer based on the question and rubric.

**Question:**
{question}

**Marking Rubric / Expected Answer (each line represents separate criteria with points):**
{rubric}

**Total Points:** {total_points}

**Student's Answer:** (See the uploaded image. Read and analyze all text from it.)

**IMPORTANT INSTRUCTIONS:**
1. The rubric has specific point allocations. For each criterion in the rubric, determine if the student met it.
2. For each criterion, assign the numeric points earned (e.g., 1, 2, 0).
3. Write a clear, specific rationale explaining WHY they got those points.

**OUTPUT FORMAT - JSON ONLY:**
{{
    "total_score": <sum of all points awarded, max {total_points}>,
    "feedback_table": [
        {{
            "mark": <ONLY THE NUMBER, e.g., 1, 2, 0. NOTHING ELSE>,
            "rationale": "<Explain why they got this mark. Reference what they wrote. Be specific.>"
        }},
        ... (one entry for each criterion in the rubric)
    ],
    "overall_feedback": "<A short paragraph summarizing strengths and areas for improvement>"
}}

**CRITICAL RULES:**
- "mark" field MUST be a NUMBER like 1, 2, 0 - NO text!
- DO NOT put descriptions like "1 mark for formula" in the mark field.
- DO NOT repeat the rubric wording in the mark field.
- Example of CORRECT mark field: "1"
- Example of WRONG mark field: "1 mark for stating F=ma"
- The rationale should explain the specific reasons for awarding or not awarding the point.
- Be fair and consistent with the rubric.
- If the answer is completely wrong or illegible, total_score = 0.
"""

    # Call API
    response_text = analyze_image_with_deepseek(image_bytes, prompt)
    
    # Check for errors
    if response_text.startswith("ERROR:"):
        return 0, [], f"ERROR: {response_text}"
    
    # Parse JSON response
    try:
        # Clean the response (remove markdown code blocks)
        cleaned_text = response_text.strip()
        if "```json" in cleaned_text:
            cleaned_text = re.search(r"```json\s*(.*?)\s*```", cleaned_text, re.DOTALL)
            if cleaned_text:
                cleaned_text = cleaned_text.group(1)
        elif "```" in cleaned_text:
            cleaned_text = re.search(r"```\s*(.*?)\s*```", cleaned_text, re.DOTALL)
            if cleaned_text:
                cleaned_text = cleaned_text.group(1)
        
        # Parse JSON
        result = json.loads(cleaned_text)
        total_score = result.get("total_score", 0)
        feedback_table = result.get("feedback_table", [])
        overall_feedback = result.get("overall_feedback", "No overall feedback provided.")
        
        # Ensure total_score is valid
        try:
            total_score = int(total_score)
        except (ValueError, TypeError):
            total_score = 0
            
        # Clamp score to valid range
        if total_score < 0:
            total_score = 0
        elif total_score > total_points:
            total_score = total_points
        
        # Validate and clean feedback_table
        if not feedback_table or not isinstance(feedback_table, list):
            feedback_table = [
                {"mark": "0", "rationale": "No detailed breakdown available."}
            ]
        
        # Clean each row - ensure mark is numeric ONLY
        cleaned_table = []
        for row in feedback_table:
            # Get the mark value
            mark_val = row.get("mark", 0)
            
            # Force clean to numeric only
            if isinstance(mark_val, (int, float)):
                numeric_mark = mark_val
            elif isinstance(mark_val, str):
                # Try to extract ONLY the number
                match = re.search(r'^(\d+(?:\.\d+)?)', mark_val.strip())
                if match:
                    numeric_mark = float(match.group(1))
                else:
                    numeric_mark = 0
            else:
                numeric_mark = 0
            
            # Ensure it's an integer or simple decimal
            if numeric_mark == int(numeric_mark):
                numeric_mark = int(numeric_mark)
            
            # Get rationale (clean it up)
            rationale = row.get("rationale", "No rationale provided.")
            # Remove any rubric wording that might have been included
            rationale = re.sub(r'^\s*\d+\s*mark(s?)?\s*(for|if|when)?\s*', '', rationale, flags=re.IGNORECASE)
            
            cleaned_table.append({
                "mark": numeric_mark,
                "rationale": rationale.strip()
            })
        
        return total_score, cleaned_table, overall_feedback
        
    except json.JSONDecodeError as e:
        return 0, [{"mark": 0, "rationale": f"Failed to parse response: {str(e)}"}], f"Error: {str(e)}"
    except Exception as e:
        return 0, [{"mark": 0, "rationale": f"Unexpected error: {str(e)}"}], f"Error: {str(e)}"

# ---- Fallback: Simulated grading with table ----
def simulate_grade(question, rubric, student_answer, total_points):
    """Placeholder grading when DeepSeek API is not available."""
    keywords = rubric.split()[:3]
    found = sum(1 for kw in keywords if kw.lower() in student_answer.lower())
    score = min(found, total_points)
    
    feedback_table = []
    for i, kw in enumerate(keywords[:3]):
        earned = 1 if kw.lower() in student_answer.lower() else 0
        feedback_table.append({
            "mark": earned,
            "rationale": f"{'✓ Found' if earned else '✗ Not found'} '{kw}' in student answer."
        })
    
    overall_feedback = f"Simulated grading: found {found} of {len(keywords)} keywords."
    return score, feedback_table, overall_feedback

# ---- Main entry point ----
def grade_submission(image_bytes, question, rubric, total_points, use_real_api=True):
    """
    Main grading function - tries real API first, falls back to simulation.
    """
    if use_real_api and DEEPSEEK_API_KEY:
        return grade_student_submission(image_bytes, question, rubric, total_points)
    else:
        transcribed = "Dummy OCR text for simulation."
        return simulate_grade(question, rubric, transcribed, total_points)
