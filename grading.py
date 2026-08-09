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
        
        # Log image details
        print(f"Image opened: {image.width}x{image.height}, mode: {image.mode}")
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Resize if too large
        max_size = 1024
        if image.width > max_size or image.height > max_size:
            image.thumbnail((max_size, max_size), Image.LANCZOS)
            print(f"Image resized to: {image.width}x{image.height}")
        
        # Save as JPEG
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=80, optimize=True)
        processed_bytes = buffer.getvalue()
        
        # If still too large, compress more
        if len(processed_bytes) > 4 * 1024 * 1024:  # 4MB
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=50, optimize=True)
            processed_bytes = buffer.getvalue()
        
        print(f"Image size: {len(processed_bytes)} bytes")
        return processed_bytes
        
    except Exception as e:
        print(f"Image processing error: {str(e)}")
        raise Exception(f"Image processing failed: {str(e)}")

def test_image_reading(image_bytes):
    """
    Test function to verify the image can be read.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        return f"✅ Image loaded: {image.width}x{image.height}, mode: {image.mode}"
    except Exception as e:
        return f"❌ Image loading failed: {str(e)}"

def call_deepseek_api(image_bytes, prompt_text):
    """
    Call DeepSeek API with image embedded as Markdown.
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
        print(f"Base64 encoding successful. Length: {len(base64_image)}")
    except Exception as e:
        return f"ERROR: Base64 encoding failed: {str(e)}"
    
    # Prepare API request
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Embed image as Markdown in the text content
    image_markdown = f"![image](data:image/jpeg;base64,{base64_image})"
    full_prompt = f"{prompt_text}\n\nHere is the student's answer as an image. Read the image carefully:\n{image_markdown}"
    
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
    
    # Build prompt - simpler and more direct
    prompt = f"""You are a teacher grading a student's answer. The student's answer is in the image attached to this message.

**IMPORTANT: The student's answer is in the IMAGE. Look at the image carefully.**

**Question:**
{question}

**Marking Rubric:**
{rubric}

**Total Points:** {total_points}

**Instructions:**
1. Look at the attached image.
2. Read what the student wrote in the image.
3. Compare it to the rubric.
4. Award points based on what the student actually wrote.

**Return ONLY valid JSON in this format:**
{{
    "score": <total points awarded between 0 and {total_points}>,
    "feedback": [
        {{
            "mark": <points for this criterion>,
            "rationale": "<explain why based on the student's answer>"
        }}
    ],
    "summary": "<brief overall feedback>"
}}

**CRITICAL RULES:**
- The student's answer is in the IMAGE.
- Base your grade ONLY on what you read in the image.
- If the image contains handwriting, read it and grade it.
- Do NOT say you can't read the image. You can read images.
- Be specific about what the student wrote.
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
