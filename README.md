## 🚀 How to Run ExaGrade on Your Local Machine

Follow these steps to set up **ExaGrade** on your local machine.

---

### **1. Clone the Repository**

git clone https://github.com/yourusername/ExaGrade.git
cd ExaGrade


### **2. Set Up a Virtual Environment**
# For macOS/Linux
python -m venv venv
source venv/bin/activate  

# For Windows
venv\Scripts\activate


### **3. Install Dependencies**
pip install -r requirements.txt


### ** 4. Apply Database Migrations**
python manage.py makemigrations
python manage.py migrate


### ** 5. Run the Development Server**
python manage.py runserver
🔗 Now, open your browser and visit: http://127.0.0.1:8000/




