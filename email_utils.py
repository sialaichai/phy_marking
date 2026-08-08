import streamlit as st
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content
import re

def is_valid_email(email: str) -> bool:
    """Simple email validation"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def send_grade_email(student_email: str, student_name: str, question: str, grade: int, total_points: int, feedback: str):
    """Send grade and feedback via email"""
    try:
        api_key = st.secrets.get("SENDGRID_API_KEY")
        sender_email = st.secrets.get("SENDER_EMAIL", "noreply@gradingapp.com")
        
        if not api_key:
            return "Email service not configured (missing API key)"
        
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        
        # Build email content
        subject = f"Your Grade: {grade}/{total_points}"
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #4CAF50; color: white; padding: 20px; text-align: center; border-radius: 5px; }}
                .grade {{ font-size: 48px; font-weight: bold; color: #4CAF50; text-align: center; margin: 30px 0; }}
                .feedback {{ background: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .question {{ background: #e8f4f8; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📝 Your Assignment Grade</h1>
                </div>
                
                <p>Hello <strong>{student_name}</strong>,</p>
                
                <div class="question">
                    <h3>📋 Question:</h3>
                    <p>{question}</p>
                </div>
                
                <div class="grade">
                    {grade} / {total_points}
                </div>
                
                <div class="feedback">
                    <h3>💬 Feedback:</h3>
                    <p>{feedback.replace(chr(10), '<br>')}</p>
                </div>
                
                <p>You can also view your results anytime by logging into the app.</p>
                
                <div class="footer">
                    <p>This is an automated message from the Smart Marking App.</p>
                    <p>If you have any questions, please contact your teacher.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Create email
        from_email = Email(sender_email)
        to_email = To(student_email)
        subject = subject
        content = Content("text/html", html_content)
        mail = Mail(from_email, to_email, subject, content)
        
        # Send
        response = sg.client.mail.send.post(request_body=mail.get())
        
        if response.status_code == 202:
            return "Email sent successfully!"
        else:
            return f"Email failed with status code: {response.status_code}"
            
    except Exception as e:
        return f"Email error: {str(e)}"
