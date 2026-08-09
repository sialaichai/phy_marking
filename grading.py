def test_image_reading(image_bytes):
    """Simple test to see what the API reads from the image."""
    if not DEEPSEEK_API_KEY:
        return "ERROR: No DeepSeek API key found."
    
    try:
        processed = process_image_for_api(image_bytes)
        base64_image = base64.b64encode(processed).decode('utf-8')
        
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Very simple prompt
        prompt = "What text do you see in this image? Return ONLY the exact text you see, nothing else."
        full_prompt = f"{prompt}\n\n![image](data:image/jpeg;base64,{base64_image})"
        
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": full_prompt}],
            "max_tokens": 500,
            "temperature": 0.0
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            return f"ERROR: API returned {response.status_code} - {response.text[:200]}"
        
        result = response.json()
        return result['choices'][0]['message']['content']
        
    except Exception as e:
        return f"ERROR: {str(e)}"
