import time
import requests
import os
from django.conf import settings
from openai import OpenAI
from django.conf import settings
client = OpenAI(api_key=settings.OPENAI_API_KEY)
import re 

def extract_text_from_pdf(file_path):
    url = "https://www.handwritingocr.com/api/v3/documents"
    headers = {
        "Authorization": f"Bearer {settings.HANDWRITINGOCR_API_KEY}"
    }

    with open(file_path, "rb") as f:
        files = {'file': (os.path.basename(file_path), f.read())}
        data = {'action': 'transcribe'}

        response = requests.post(url, headers=headers, files=files, data=data)

    if response.status_code not in [200, 201]:
        print("❌ Upload Failed:", response.status_code, response.text)
        return ""

    document_id = response.json().get("id")
    if not document_id:
        print("❌ No document ID received.")
        return ""

    # Polling the document status
    max_wait = 60  # seconds
    interval = 5
    waited = 0

    while waited < max_wait:
        time.sleep(interval)
        waited += interval

        status_url = f"https://www.handwritingocr.com/api/v3/documents/{document_id}"
        status_response = requests.get(status_url, headers=headers)

        try:
            status_json = status_response.json()
        except Exception as e:
            print("❌ JSON decode error:", e)
            continue

        print(f"⏳ [Polling] Status: {status_json.get('status')}")

        if status_json.get("status") == "processed":
            pages = status_json.get("results", [])
            full_text = "\n\n".join([page.get("transcript", "") for page in pages])
            return full_text.strip()

    print("❌ Timed out waiting for OCR results.")
    return ""


def extract_name_and_id(text):
    """
    Extracts the student name and ID from OCR text like:
    'Student Name: Aisha Alomari  Student ID: 20230014'
    Returns: ('Aisha Alomari', '20230014')
    """
    name = "Empty"
    student_id = ""

    # Normalize text
    lines = text.lower().splitlines()

    for line in lines:
        line = line.strip()

        # Name patterns
        name_patterns = [
            r"student\s*name\s*[:\-]\s*(.+?)(?:\s+student\s*id[:\-]|$)",
            r"name\s*[:\-]\s*(.+?)(?:\s+student\s*id[:\-]|$)",
            r"student\s*[:\-]\s*(.+?)(?:\s+student\s*id[:\-]|$)",
        ]

        for pattern in name_patterns:
            match = re.search(pattern, line)
            if match:
                raw_name = match.group(1).strip()
                name = " ".join(word.capitalize() for word in raw_name.split())
                break  # Stop after first match

        # ID pattern
        id_match = re.search(r"student\s*id\s*[:\-]?\s*(\d{4,})", line)
        if id_match:
            student_id = id_match.group(1).strip()

        # Stop early if both found
        if name != "Empty" and student_id:
            break

    return name, student_id



