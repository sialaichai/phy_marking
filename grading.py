import streamlit as st
import requests
import base64
import json
import re

# Get API key from Streamlit secrets
DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", None)

def analyze_image_with_deepseek(image_bytes, prompt_text):
    """
    Send an image to DeepSeek-VL model for analysis.
    
    Args:
        image_bytes: Binary image data (from uploaded file)
        prompt_text: Task description (e.g., "Extract text from this image")
    
    Returns:
        String response from DeepSeek model
    """
    if not DEEPSEEK_API_KEY:
        return "ERROR: DeepSeek API key not found. Please add it to secrets."
    
    # Step 1: Convert image to Base64
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    # Step 2: Prepare API request
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Step 3: Build the request payload
    payload = {
        "model": "deepseek-chat",  # Uses VL capabilities
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 1000,
        "temperature": 0.3  # Lower = more consistent grading
    }
    
    # Step 4: Send request
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        return result['choices'][0]['message']['content']
        
    except requests.exceptions.Timeout:
        return "ERROR: Request timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return f"ERROR: API request failed: {e}"
    except (KeyError, IndexError) as e:
        return f"ERROR: Unexpected API response: {e}"

def grade_student_submission(image_bytes, question, rubric, total_points):
    """
    Grade a student's answer using DeepSeek API.
    
    Args:
        image_bytes: Binary image of student's answer
        question: The assignment question
        rubric: Expected answer / marking criteria
        total_points: Maximum possible score
    
    Returns:
        (grade, feedback) tuple
    """
    # Construct grading prompt
    prompt = f"""You are a strict teacher. Grade the student's answer based on the question and rubric.

**Question:**
{question}

**Marking Rubric / Expected Answer:**
{rubric}

**Total Points:** {total_points}

**Student's Answer:** (See the uploaded image. Extract and read all text from it.)

Please respond in the following JSON format ONLY. Do not include any other text or explanation:

{{
    "score": <number of points the student earned>,
    "feedback": "<detailed feedback explaining the score, referencing specific parts of the student's answer>"
}}

Rules:
- The score must be a number between 0 and {total_points}.
- Be fair and consistent with the rubric.
- Point out what the student did well and where they can improve.
"""

    # Call API
    response_text = analyze_image_with_deepseek(image_bytes, prompt)
    
    # Check for errors
    if response_text.startswith("ERROR:"):
        return 0, response_text
    
    # Parse JSON response
    try:
        # Remove any Markdown code block formatting
        if "```json" in response_text:
            response_text = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL).group(1)
        elif "```" in response_text:
            response_text = re.search(r"```\s*(.*?)\s*```", response_text, re.DOTALL).group(1)
        
        result = json.loads(response_text.strip())
        score = result.get("score", 0)
        feedback = result.get("feedback", "No feedback provided.")
        
        # Ensure score is within bounds
        if score < 0:
            score = 0
        elif score > total_points:
            score = total_points
            
        return int(score), feedback
        
    except json.JSONDecodeError:
        return 0, f"Failed to parse grading response. Raw response: {response_text[:200]}..."
    except Exception as e:
        return 0, f"Unexpected error parsing response: {e}"

# ---- Fallback: Simulated grading (if API not available) ----
def simulate_grade(question, rubric, student_answer, total_points):
    """Placeholder grading when DeepSeek API is not available."""
    keywords = rubric.split()[:5]
    found = sum(1 for kw in keywords if kw.lower() in student_answer.lower())
    score = min(found, total_points)
    feedback = f"Simulated grading: found {found} keywords. (Replace with real DeepSeek API.)"
    return score, feedback

# ---- Main entry point (for backwards compatibility) ----
def grade_submission(image_bytes, question, rubric, total_points, use_real_api=True):
    """
    Main grading function - tries real API first, falls back to simulation.
    """
    if use_real_api and DEEPSEEK_API_KEY:
        return grade_student_submission(image_bytes, question, rubric, total_points)
    else:
        # Use simulated grading with dummy transcription
        transcribed = "Dummy OCR text for simulation."
        return simulate_grade(question, rubric, transcribed, total_points)
