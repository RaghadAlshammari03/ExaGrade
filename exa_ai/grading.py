from openai import OpenAI
import re
from django.conf import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def grade_answer(question, student_text, solution_text, marks, eval_type="strict", custom_note="", question_type=None):
    eval_instructions = {
        "strict": "Grade strictly based on exact match with the solution.",
        "flexible": "Accept answers that have the same meaning, even if phrased differently.",
        "keywords": "Check whether key concepts from the solution are present in the student's answer.",
        "coding": "Grade this as a code answer. Check logic, syntax, and correctness of the output.",
        "custom": custom_note.strip() or "Use your judgment to grade this based on the instructor's custom criteria.",
    }

    # Objective-specific instructions
    if question_type in ["true_false", "mcq"]:
        objective_notes = """
        - Accept answers like "A", "B", "C", or "D" regardless of case (e.g., "a" = "A") (for MCQ).
        - Accept "T", "True", "✓", "✔️" or "F", "False", "X", "✖️" (for True/False).
        - Only accept one final answer. If student writes multiple (e.g., "A and B"), mark as unclear.
        - If the answer is ambiguous or doesn't match expected format, include "REQUIRES ATTENTION" in your feedback.
        - Provide a short and clear judgment: Correct ✅, Incorrect ❌, or Unclear ⚠️.
        """
    else:
        objective_notes = ""

    # Dynamic temperature
    temperature = 0.2 if question_type in ["true_false", "mcq"] else 0.5

    prompt = f"""
You are an AI grading assistant.

IMPORTANT:
- The Solution Text is 100% correct.
- Do NOT use external knowledge or assume anything.
- If unsure how to grade or if the student answer is ambiguous (e.g., "A and B"), include "REQUIRES ATTENTION".

Evaluation Type: {eval_type}
{eval_instructions[eval_type]}
{objective_notes.strip()}

Return ONLY in this format:
Score: x/{marks}
Feedback: [Your clear feedback here.]

Question: {question}
Student Answer: {student_text}
Solution Text: {solution_text}
""".strip()

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Score: 0/{marks}\nFeedback: Error: {str(e)}"

    
def parse_score_and_feedback(response_text, marks, question_number=None):
    try:
        score_match = re.search(r"Score:\s*(\d+(?:\.\d+)?)\s*/\s*\d+", response_text)
        score = float(score_match.group(1)) if score_match else 0.0

        feedback_lines = response_text.strip().splitlines()
        feedback_text = "\n".join([line for line in feedback_lines if not line.lower().startswith("score:")])
        feedback_text = feedback_text.replace("Feedback:", "").strip()

        requires_attention = "requires attention" in feedback_text.lower()

        keyword_map = {
            "correct": ("✅", "#2ecc71"),
            "incorrect": ("❌", "#e74c3c"),
            "unclear": ("⚠️", "#f39c12"),
            "partially correct": ("⚠️", "#f1c40f"),
            "missing": ("⚠️", "#f1c40f"),
            "misunderstood": ("❌", "#e74c3c"),
        }

        points = re.split(r"\.\s+|\n+", feedback_text)
        structured_feedback = []

        for pt in points:
            pt = pt.strip().rstrip(".")
            if not pt:
                continue
            icon = "•"
            for kw, (icon_candidate, color) in keyword_map.items():
                if re.search(rf"\b{kw}\b", pt, re.IGNORECASE):
                    icon = icon_candidate
                    pt = re.sub(rf"(?i)\b({kw})\b", rf"<strong style='color:{color};'>\1</strong>", pt)
                    break
            structured_feedback.append(f"{icon} {pt}")

        feedback_html = "<br>".join(structured_feedback) if structured_feedback else "No feedback provided."
        badge = f"<span style='background:#eee; padding:4px 8px; border-radius:5px;'>Score: {int(score)} / {marks}</span>"
        prefix = f"<strong>Question {question_number}:</strong><br>" if question_number else ""
        return score, f"{prefix}{badge}<br>{feedback_html}", requires_attention

    except Exception as e:
        return 0.0, f"<strong>Question {question_number or '?'}:</strong> Error parsing feedback: {str(e)}", False
