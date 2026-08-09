def grade_work(image_bytes, question, rubric, total_points, use_real_api=True):
    """Wrapper that returns score, table, summary, and extracted text."""
    if not use_real_api or not DEEPSEEK_API_KEY:
        score, table, summary = simulate_grading(question, rubric, total_points)
        return score, table, summary, "Simulated grading (API not used)."
    
    # Step 1: Extract text from image
    student_text, error = extract_text_from_image(image_bytes)
    
    if error:
        return 0, [{"rubric": "Error", "mark": "0"}], f"OCR failed: {error}", student_text if student_text else ""
    
    if not student_text or len(student_text) < 5:
        return 0, [{"rubric": "No text extracted", "mark": "0"}], "No text could be read.", student_text if student_text else ""
    
    # Step 2: Grade using text-only API
    grading_prompt = f"""Grade the student's answer.

STUDENT'S ANSWER:
{student_text}

RUBRIC:
{rubric}

TOTAL POINTS: {total_points}

Return JSON ONLY:
{{
    "score": <number>,
    "feedback": [
        {{"rubric": "<criterion>", "mark": <number>}}
    ]
}}
"""
    
    response = call_deepseek_text_only(grading_prompt)
    
    if response.startswith("ERROR:"):
        return 0, [{"rubric": "Grading error", "mark": "0"}], response, student_text
    
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
        score = int(data.get("score", 0))
        feedback = data.get("feedback", [])
        
        if score < 0:
            score = 0
        elif score > total_points:
            score = total_points
        
        if not feedback:
            feedback = [{"rubric": "Overall", "mark": str(score)}]
        
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
        
        return score, table, "Grading complete.", student_text
        
    except json.JSONDecodeError as e:
        return 0, [{"rubric": "Parse error", "mark": "0"}], f"Error: {str(e)}", student_text
    except Exception as e:
        return 0, [{"rubric": "Unexpected error", "mark": "0"}], f"Error: {str(e)}", student_text
