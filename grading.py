def display_feedback_table(feedback_table):
    """
    Display feedback as a clean single-column list.
    Each card shows: Mark, Rubric, Rationale.
    No horizontal scrolling on mobile.
    """
    if not feedback_table or len(feedback_table) == 0:
        st.caption("No detailed breakdown available.")
        return
    
    for i, row in enumerate(feedback_table):
        mark_val = row.get('mark', '0')
        rubric = row.get('rubric', '')
        rationale = row.get('rationale', 'No rationale provided.')
        
        # Escape any special characters
        rubric = rubric.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        rationale = rationale.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Create a clean card-like display
        st.markdown(f"""
        <div style="
            background-color: {'#f9f9f9' if i % 2 == 0 else '#ffffff'};
            padding: 12px 15px;
            border-radius: 8px;
            margin-bottom: 8px;
            border-left: 4px solid #4CAF50;
        ">
            <div style="font-size: 18px; font-weight: bold; color: #4CAF50;">
                Mark: {mark_val}
            </div>
            <div style="font-size: 13px; color: #666; margin-top: 4px; font-weight: bold;">
                Rubric: <span style="font-weight: normal; color: #333;">{rubric}</span>
            </div>
            <div style="font-size: 14px; color: #333; margin-top: 4px; line-height: 1.5;">
                <span style="font-weight: bold;">Rationale:</span> {rationale}
            </div>
        </div>
        """, unsafe_allow_html=True)
