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

def call_deepseek_api(image_bytes, prompt_text):
    """
    Send an image and prompt to DeepSeek model.
    """
    if not DEEPSEEK_API_KEY:
        return "ERROR: DeepSeek API key not found. Please add it to secrets."
    
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
    
    # Build payload with image as markdown
    image_markdown = f"![image](data:image/jpeg;base64,{base64_image})"
    full_prompt = f"{prompt_text}\n\nHere is the image:\n{image_markdown}"
    
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
    
    # Send request
    try:
        response = requests.post(
            url, 
            headers=headers, 
            json=payload, 
            timeout=60
        )
        
        if response.status_code == 400:
            error_detail = response.json() if response.text else {}
            error_msg = error_detail.get('error', {}).get('message', 'Unknown error')
            return f"ERROR: Bad Request - {error_msg}"
        elif response.status_code == 401:
            return "ERROR: Invalid API key."
        elif response.status_code == 429:
            return "ERROR: Rate limit exceeded. Please wait."
        elif response.status_code == 500:
            return "ERROR: DeepSeek server error. Please try again later."
        
        response.raise_for_status()
        
        result = response.json()
        return result['choices'][0]['message']['content']
        
    except requests.exceptions.Timeout:
        return "ERROR: Request timed out."
    except requests.exceptions.RequestException as e:
        return f"ERROR: API request failed: {str(e)}"
    except (KeyError, IndexError) as e:
        return f"ERROR: Unexpected API response structure: {str(e)}"

def extract_text_from_image(image_bytes):
    """
    Step 1: Extract text from the image using DeepSeek OCR.
    Returns just the student's text without any rubric context.
    """
    prompt = """Extract ALL text from this image. This is a student's handwritten or typed answer.

Rules:
- ONLY extract text that is actually written in the image.
- Do NOT add any extra text or commentary.
- Just return the text you see in the image, exactly as written.
- If the image contains handwriting, transcribe it as accurately as possible.
- If the image contains typed text, copy it exactly.
- Do NOT include any instructions, explanations, or context in your response.
- Just return the raw text from the image.
"""
    
    response = call_deepseek_api(image_bytes, prompt)
    
    if response.startswith("ERROR:"):
        return "", response
    
    # Clean the response
    # Remove any markdown or code blocks
    cleaned = response.strip()
    if "```" in cleaned:
        cleaned = re.sub(r'```.*?```', '', cleaned, flags=re.DOTALL)
    
    return cleaned.strip(), None

def grade_student_submission(image_bytes, question, rubric, total_points):
    """
    Step 2: Grade the student's answer using the extracted text.
    """
    # Step 1: Extract text from image
    student_text, error = extract_text_from_image(image_bytes)
    
    if error:
        return 0, [], f"ERROR: {error}"
    
    if not student_text or len(student_text) < 3:
        return 0, [{"mark": 0, "rationale": "No text could be extracted from the image. Please ensure the handwriting is clear and the image is well-lit."}], "No text extracted from image."
    
    # Step 2: Grade the extracted text
    # Parse the rubric into individual criteria
    # Simple approach: split by newlines or numbered items
    criteria = []
    for line in rubric.split('\n'):
        line = line.strip()
        if line and any(c in line for c in ['1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '•', '-', '[', '(']):
            # Try to extract the point value
            points = 0
            # Look for [X] or (X) or X marks
            match = re.search(r'\[(\d+)\]|\((\d+)\)|(\d+)\s*marks?', line)
            if match:
                points = int(match.group(1) or match.group(2) or match.group(3) or 0)
            elif line.startswith(tuple(['1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.'])):
                points = 1
            else:
                points = 1
            
            criteria.append({
                "points": points,
                "description": line
            })
    
    if not criteria:
        # If no criteria found, treat the whole rubric as one criterion
        criteria = [{"points": total_points, "description": rubric}]
    
    # Step 3: Grade using the extracted text
    # Use a simpler prompt that ONLY references the student's extracted text
    grading_prompt = f"""You are a teacher. Grade the student's answer based on the rubric.

**Student's Answer (extracted from image):**
"{student_text}"

**Rubric:**
{rubric}

**Total Points:** {total_points}

**Output JSON ONLY:**
{{
    "total_score": <number between 0 and {total_points}>,
    "feedback_table": [
        {{
            "mark": <numeric points for this criterion>,
            "rationale": "<explanation based on what the student wrote>"
        }}
    ],
    "overall_feedback": "<summary>"
}}

Rules:
- The student's answer is quoted above. ONLY refer to what is in the quotes.
- The rubric is for reference only.
- For each criterion, compare the student's answer to what the rubric requires.
- Award points based on what the student wrote.
- The rationale should reference the student's actual words from the quoted text.
"""

    response = call_deepseek_api(image_bytes, grading_prompt)
    
    if response.startswith("ERROR:"):
        return 0, [], f"ERROR: {response}"
    
    # Parse JSON response
    try:
        cleaned_text = response.strip()
        if "```json" in cleaned_text:
            cleaned_text = re.search(r"```json\s*(.*?)\s*```", cleaned_text, re.DOTALL)
            if cleaned_text:
                cleaned_text = cleaned_text.group(1)
        elif "```" in cleaned_text:
            cleaned_text = re.search(r"```\s*(.*?)\s*```", cleaned_text, re.DOTALL)
            if cleaned_text:
                cleaned_text = cleaned_text.group(1)
        
        result = json.loads(cleaned_text)
        total_score = result.get("total_score", 0)
        feedback_table = result.get("feedback_table", [])
        overall_feedback = result.get("overall_feedback", "No overall feedback provided.")
        
        # Ensure total_score is valid
        try:
            total_score = int(total_score)
        except (ValueError, TypeError):
            total_score = 0
            
        if total_score < 0:
            total_score = 0
        elif total_score > total_points:
            total_score = total_points
        
        # Clean feedback_table
        if not feedback_table or not isinstance(feedback_table, list):
            feedback_table = [{"mark": 0, "rationale": "No detailed breakdown available."}]
        
        cleaned_table = []
        for row in feedback_table:
            mark_val = row.get("mark", 0)
            if isinstance(mark_val, (int, float)):
                numeric_mark = mark_val
            elif isinstance(mark_val, str):
                match = re.search(r'^(\d+(?:\.\d+)?)', mark_val.strip())
                if match:
                    numeric_mark = float(match.group(1))
                else:
                    numeric_mark = 0
            else:
                numeric_mark = 0
            
            if numeric_mark == int(numeric_mark):
                numeric_mark = int(numeric_mark)
            
            rationale = row.get("rationale", "No rationale provided.")
            
            # Remove any rubric references
            rationale = re.sub(r'(?:the\s+)?rubric\s+(?:says|states|mentions|indicates|has|requires|asks for)\s+', '', rationale, flags=re.IGNORECASE)
            rationale = re.sub(r'^\s*\d+\s*mark(s?)\s*(?:for|if|when)\s*', '', rationale, flags=re.IGNORECASE)
            
            # If rationale is just a rubric quote, replace with a generic message
            if any(phrase in rationale.lower() for phrase in ['rubric says', 'rubric states', 'rubric requires']):
                rationale = "Awarded based on comparison with rubric criteria."
            
            cleaned_table.append({
                "mark": numeric_mark,
                "rationale": rationale.strip()
            })
        
        return total_score, cleaned_table, overall_feedback
        
    except json.JSONDecodeError as e:
        return 0, [{"mark": 0, "rationale": f"Failed to parse response: {str(e)}"}], f"Error: {str(e)}"
    except Exception as e:
        return 0, [{"mark": 0, "rationale": f"Unexpected error: {str(e)}"}], f"Error: {str(e)}"

# ---- Fallback: Simulated grading ----
def simulate_grade(question, rubric, student_answer, total_points):
    """Placeholder grading when DeepSeek API is not available."""
    keywords = re.findall(r'\b[a-zA-Z]{3,}\b', rubric)[:5]
    found = sum(1 for kw in keywords if kw.lower() in student_answer.lower())
    score = min(found, total_points)
    
    feedback_table = []
    for i, kw in enumerate(keywords[:3]):
        earned = 1 if kw.lower() in student_answer.lower() else 0
        feedback_table.append({
            "mark": earned,
            "rationale": f"{'✓ Found' if earned else '✗ Not found'} in student answer."
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
