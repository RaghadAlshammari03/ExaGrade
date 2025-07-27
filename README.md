# **ExaGrade**  

*AI-powered exam management and grading system for paper-based and online assessments.*

---

## 🌟 Introduction

**ExaGrade** is a Django-based platform built to simplify how exams are created, graded, and reviewed. It works with both scanned paper exams and online assessments. With built-in OCR and AI support, ExaGrade can extract handwritten answers, auto-grade responses, and flag anything unclear.


**Key capabilities include:**
- Handwriting recognition for scanned papers using **HandwritingOCR API**  
- Auto-grading for multiple question types with **ChatGPT API**  
- Intelligent flagging for ambiguous responses requiring manual review  
- PDF generation with live preview and full exam lifecycle tracking  

---

## ✨ Features

### **1. Courses & Exams Management** 
- **Courses Dashboard:** Instructors can create and share course codes; students join with a 6-digit code.  
- **Separate Exam Views:** Exams are managed under two dedicated tabs: **Paper Exams** and **Online Exams**, each showing real-time status with badges:
  - *Pending:* No student responses have been graded yet  
  - *In Progress:* Some, but not all responses have been graded  
  - *Requires Attention:* At least one flagged question requires manual review  
  - *Done:* All responses have been graded and no issues remain  

### **2. Smart OCR & AI Grading**
- Handwritten student answers are extracted using the **HandwritingOCR API**
- AI grading via **OpenAI GPT API**, tailored for:
  - True/False and Multiple Choice questions  
  - Short and Long Answer questions  
  - Contextual evaluation for short/long questions using different grading strategies (e.g. *Strict*, *Flexible*, *Keyword*, *Custom*)  
  - Automatic detection of doubtful or unclear answers, flagged for manual intervention  

### **3. Live PDF Preview During Exam Creation**
While creating or editing a paper exam, the screen is split into two sections:
- On the **left**, instructors fill out the exam form, adding questions, marks, types, and evaluation preferences  
- On the **right**, a live PDF preview updates in real time to show how the final exam will look  
This side-by-side experience helps instructors catch formatting issues instantly and ensures the layout is just right before downloading the exam

The same applies to the **Answered Module**, which shows a preview of a completed exam sheet with the correct answers highlighted in blue  


### **4. Instructor-Friendly Exam Creation**
- Exams can be created or edited using a dynamic and user-friendly interface  
- Supports adding any combination of:  
  - True/False questions  
  - Multiple Choice questions  
  - Short Answer questions  
  - Long Answer questions  
- Each short/long question can be configured with its own evaluation type and optional AI grading notes  

### **5. Online Exam Interface for Students**
- Clean, full-screen layout with auto-save, countdown timer
- MCQ and True/False questions are graded instantly  
- Written answers are sent for AI evaluation, with final scores shown when grading is complete  

### **6. Feedback System**
- **AI-generated feedback** is created for every graded question, giving students clear explanations of their scores  
- Instructors can also add **manual feedback**
- Feedback is stored with each question and shown to the student alongside their score  

### **7. Calendar & Reminders**
- Integrated **FullCalendar** dashboard for tracking upcoming exams  
- Color-coded events, daily reminders, and grading schedules  

### **8. PDF Generation**
- High-quality PDF generation using **ReportLab** for both exam papers and student answer modules  
- Includes:
  - Page numbers  
  - Consistent footers  
  - Structured layout  
  - Answer fields auto-filled in the student copy  

---

## 🛠️ Tech Stack

- **Backend:** Django
- **Frontend:** HTML, Tailwind CSS, JavaScript  
- **Calendar UI:** FullCalendar  
- **OCR Integration:** [HandwritingOCR API](https://www.handwritingocr.com/)  
- **AI Grading:** [OpenAI ChatGPT API](https://platform.openai.com/)  
- **PDFs:** ReportLab  
- **Database:** SQLite (for development)

---

## 🚀 Getting Started

### **1. Clone the Repository**
- git clone https://github.com/RaghadAlshammari03/ExaGrade.git
- cd ExaGrade

### **2. Set Up the Virtual Environment**
- For macOS/Linux:
  - python3 -m venv venv
  - source venv/bin/activate

- For Windows:
  - python -m venv venv
  - venv\Scripts\activate

### **3. Install Dependencies**
- pip install -r requirements.txt

### **4. Add Your API Keys**
Create a .env file in the root directory and add:
- HANDWRITING_OCR_API_KEY=your_handwritingocr_api_key
- OPENAI_API_KEY=your_openai_api_key

These keys are used for:
- HANDWRITING_OCR_API_KEY: To extract handwritten answers from scanned papers
- OPENAI_API_KEY: To grade answers and generate feedback using ChatGPT

### **5. Run the Development Server**
- python manage.py migrate
- python manage.py runserver
- Open your browser and go to: http://127.0.0.1:8000

---

## 🤖 How APIs Are Used
### HandwritingOCR API Usage
- Located in: utils\utils.py
- Converts uploaded scanned PDFs or images into structured student answers using OCR.
- The extracted answers are mapped to questions in the database.

### ChatGPT API Usage
- Located in: utils\grading.py
- The grade_answer() function sends the student answer, question prompt, correct answer, and evaluation type to ChatGPT.
- GPT returns a score (out of total marks), feedback, and flags if clarification is needed.
- Different evaluation modes are supported: "strict", "flexible", "keywords", and "custom".

---

Made by Raghad Alshammari - Sadeem Alresaini - Rana Alnughaimshi.

Supervisor: Dr. Abdulaziz Algablan
