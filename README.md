# Exam Grader AI Agent 🎓  

This repository contains a **Flask-based AI Exam Grading System** that automates the grading of student exam responses. The application uses **Azure OpenAI (GPT-4o)** for AI-based evaluation and **Azure Form Recognizer** for extracting text from PDF documents.

---

## 📌 Project Aim  

The **Exam Grader AI Agent** is designed to streamline the **grading process for educators** by providing automated feedback and scoring based on a predefined rubric. This tool enables faster and more consistent grading while offering detailed insights into student performance.

By leveraging **Azure Form Recognizer** and **Azure OpenAI**, the system extracts text from student response sheets and compares them with reference answers to assign scores.  

This solution is **ideal for teachers, professors, and educational institutions** looking to **enhance efficiency and fairness** in exam evaluation.  

---

## 🚀 Features  

### 📂 Upload PDFs & Set a Rubric  
- Upload a **Reference PDF** containing exam questions, reference answers, and point allocations.  
- Upload **Student PDFs or ZIP files** for grading.  
- Provide a **Custom Grading Rubric** for evaluation criteria.  

📌 **More details:** [Uploading PDFs and Setting a Rubric](https://github.com/aslisen17/ExamGrader_AI/issues/2#issue-2910175446)  

![Uploading PDFs](https://github.com/aslisen17/ExamGrader_AI/assets/2)

---

### 🤖 AI-Powered Exam Grading  
- Uses **Azure Form Recognizer** to extract text from PDFs.  
- Compares student responses with the reference key.  
- Assigns **AI-based scores** according to the provided rubric.  
- Displays results in an **intuitive user interface**.  

📌 **More details:** [AI Exam Grader](https://github.com/aslisen17/ExamGrader_AI/issues/1#issue-2910172333)  

![AI Exam Grader](https://github.com/aslisen17/ExamGrader_AI/assets/1)

---

### 📊 Exam Grading Results  
- Generates **detailed score reports** for each student.  
- Displays **question-wise scores** and **AI-generated feedback**.  
- Allows navigation to **detailed question-by-question breakdowns**.  

📌 **More details:** [Exam Grading Results](https://github.com/aslisen17/ExamGrader_AI/issues/3#issue-2910184138)  

![Exam Results](https://github.com/aslisen17/ExamGrader_AI/assets/3)

---

## 🏗 Architecture  

The **Exam Grader AI Agent** is built using:  

- **Flask** (Backend Framework)  
- **Azure Form Recognizer** (Text Extraction from PDFs)  
- **Azure OpenAI (GPT-4o)** (AI-based grading & feedback)  
- **Azure Blob Storage** (File Storage)  
- **Bootstrap & HTML** (Frontend Interface)  

**System Flow:**  
📌 **Reference PDFs + Student PDFs → Azure Form Recognizer → AI Grading with OpenAI → Generate Reports**  

![System Architecture](https://github.com/aslisen17/ExamGrader_AI/assets/your-architecture-image-url.png)

---

## 🛠 Installation & Setup  

### 1️⃣ Prerequisites  
- **Python 3.8+**  
- **Azure Subscription**  
- **Azure OpenAI Resource** (GPT-4o Model Deployed)  
- **Azure Form Recognizer**  
- **Azure Blob Storage**  
- **Visual Studio Code (Recommended)**  

---

### 2️⃣ Clone the Repository  

```bash
git clone https://github.com/aslisen17/ExamGrader_AI.git
cd ExamGrader_AI
