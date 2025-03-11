import re
import os
import zipfile
import openai
import pandas as pd
from flask import Flask, request, render_template, jsonify, send_file, url_for
from werkzeug.utils import secure_filename
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from collections import defaultdict

# -----------------------------
# Load environment variables
# -----------------------------
from dotenv import load_dotenv
load_dotenv()

# Retrieve Azure/OpenAI credentials from .env
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION")
OPENAI_API_TYPE = os.getenv("OPENAI_API_TYPE")

FORM_RECOGNIZER_ENDPOINT = os.getenv("FORM_RECOGNIZER_ENDPOINT")
FORM_RECOGNIZER_KEY = os.getenv("FORM_RECOGNIZER_KEY")

# Optionally retrieve Azure Blob Storage creds
from azure.storage.blob import BlobServiceClient
BLOB_CONNECTION_STRING = os.getenv("AZURE_BLOB_CONNECTION_STRING")
BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER")

# OpenAI Setup
openai.api_key = OPENAI_API_KEY
openai.api_base = OPENAI_API_BASE
openai.api_version = OPENAI_API_VERSION
openai.api_type = OPENAI_API_TYPE

# Azure Form Recognizer Client
form_recognizer_client = DocumentAnalysisClient(
    endpoint=FORM_RECOGNIZER_ENDPOINT,
    credential=AzureKeyCredential(FORM_RECOGNIZER_KEY)
)

# -----------------------------
# Flask App Setup
# -----------------------------
app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "temp")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -----------------------------
# Global Dictionary for Storing Student Details
# Key = student_file (string), Value = list of question dict
# -----------------------------
student_details_cache = {}

# -----------------------------
# Helper Functions
# -----------------------------
def cleanup_pdf_artifacts(text):
    """Removes excessive whitespace from extracted PDF text."""
    return re.sub(r"\s+", " ", text).strip()

def extract_text_with_form_recognizer(file_path):
    """Extracts text from a PDF using Azure Form Recognizer (prebuilt-read)."""
    with open(file_path, "rb") as pdf_file:
        poller = form_recognizer_client.begin_analyze_document(
            "prebuilt-read", document=pdf_file.read()
        )
        result = poller.result()

    extracted_text = [line.content for page in result.pages for line in page.lines]
    return "\n".join(extracted_text)

def parse_reference_text(full_text):
    """
    Parses the reference PDF text into structured questions with:
      - question_number
      - question_text
      - points
      - reference_answer
    We look for lines like:
      Question X:
      Points: X
      Reference Answer: ...
    """
    pattern = re.compile(r"(?i)(question\s+(\d+)\s*[:\.]?)")
    splitted = pattern.split(full_text)

    results = []
    for i in range(1, len(splitted), 3):
        question_number = splitted[i+1].strip()
        question_block = splitted[i+2].strip()

        # Extract "Points: X"
        points_pattern = re.compile(r"(?i)points\s*:\s*(\d+)")
        match_points = points_pattern.search(question_block)
        question_points = 0
        if match_points:
            question_points = int(match_points.group(1))
            question_block = points_pattern.sub("", question_block).strip()

        # Extract "Reference Answer:"
        ref_pattern = re.compile(r"(?i)reference\s*[\n\r\s]*answer\s*[:\.]")
        parts = ref_pattern.split(question_block, maxsplit=1)
        if len(parts) < 2:
            reference_answer = ""
            question_text = question_block
        else:
            question_text = parts[0].strip()
            reference_answer = parts[1].strip()

        results.append({
            "number": question_number,
            "question_text": question_text,
            "points": question_points,
            "reference_answer": reference_answer
        })
    
    return results

def parse_student_text(full_text):
    """
    Parses student PDF text into structured answers:
      - question_number
      - answer
    We remove "Points: X" or "Student Answer:" if present.
    """
    pattern = re.compile(r"(?i)(question\s+(\d+)\s*[:\.]?)")
    splitted = pattern.split(full_text)

    results = []
    for i in range(1, len(splitted), 3):
        question_number = splitted[i+1].strip()
        block = splitted[i+2].strip()

        # Remove "Points: X"
        points_pattern = re.compile(r"(?i)points\s*:\s*\d+")
        block = points_pattern.sub("", block).strip()

        # Remove "Student Answer:"
        block = re.sub(r"(?i)student answer\s*:\s*", "", block).strip()

        results.append({
            "number": question_number,
            "answer": block
        })
    
    return results

def is_open_ended(question_text):
    """
    Simple heuristic to decide if partial credit is allowed (open-ended).
    If question text includes 'True or False' or 'Which of the following' or multiple-choice markers (A), B), etc.),
    treat as MC/TF => 0 or full credit. Otherwise => partial credit.
    """
    text_lower = question_text.lower()
    if "true or false" in text_lower:
        return False
    if "which of the following" in text_lower:
        return False
    if "a)" in text_lower or "b)" in text_lower or "c)" in text_lower or "d)" in text_lower:
        return False
    return True

def grade_mc_or_tf_question(reference_answer, student_answer, question_points):
    """
    For multiple-choice or TF questions: 0 or full question_points.
    """
    prompt = f"""
You are a strict grader for a multiple-choice/true-false question worth {question_points} points.
If the student's answer exactly matches the reference answer, assign {question_points}. Otherwise assign 0.

Reference Answer: {reference_answer}
Student Answer: {student_answer}

Respond in this format:

Score: [0 or {question_points}]
Overall Feedback: [brief explanation]
"""
    response = openai.ChatCompletion.create(
        deployment_id="gpt-4o-mini",  # Replace with your actual Azure OpenAI deployment name
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=256
    )
    return response["choices"][0]["message"]["content"].strip()

def grade_open_ended_question(reference_answer, student_answer, rubric, question_points):
    """
    Open-ended => partial credit from 0 to question_points.
    """
    prompt = f"""
You are an AI grader. Use the rubric to assign partial credit from 0 to {question_points}.

Rubric:
\"\"\"
{rubric}
\"\"\"

Reference Answer: {reference_answer}
Student Answer: {student_answer}

Output in this format:

Score: [0-{question_points}]
Overall Feedback: [1-2 sentence explanation]
"""
    response = openai.ChatCompletion.create(
        deployment_id="gpt-4o-mini",  # Replace with your Azure OpenAI deployment name
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=256
    )
    return response["choices"][0]["message"]["content"].strip()

def parse_gpt_feedback(feedback_text):
    """
    Extract "Score: X" and "Overall Feedback: ..."
    """
    lines = feedback_text.split("\n")
    result = {"score": "0", "overall": ""}
    for line in lines:
        low = line.lower().strip()
        if low.startswith("score:"):
            result["score"] = line.split(":", 1)[1].strip()
        elif low.startswith("overall feedback:"):
            result["overall"] = line.split(":", 1)[1].strip()
    return result

# -----------------------------
# Routes
# -----------------------------
@app.route('/')
def home():
    return render_template('index.html', results=None, error=None)

@app.route('/upload', methods=['POST'])
def upload_files():
    """Handles uploading, parsing, grading, and summarizing."""
    global student_details_cache
    student_details_cache = {}

    # 1) Reference PDF
    if 'reference' not in request.files or not request.files['reference'].filename.strip():
        return render_template('index.html', error="No reference file uploaded.")
    reference_file = request.files['reference']
    ref_filename = secure_filename(reference_file.filename)
    ref_local_path = os.path.join(app.config['UPLOAD_FOLDER'], ref_filename)
    reference_file.save(ref_local_path)

    # Optional: Upload reference file to Blob Storage
    if BLOB_CONNECTION_STRING and BLOB_CONTAINER:
        try:
            blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
            container_client = blob_service_client.get_container_client(BLOB_CONTAINER)
            with open(ref_local_path, 'rb') as data:
                container_client.upload_blob(name=ref_filename, data=data, overwrite=True)
        except Exception as e:
            print(f"Blob upload (reference) failed: {e}")

    # 2) Parse reference
    reference_text = cleanup_pdf_artifacts(extract_text_with_form_recognizer(ref_local_path))
    reference_data = parse_reference_text(reference_text)
    if not reference_data:
        return render_template('index.html', error="Could not parse any questions from reference file.")
    ref_dict = {q["number"]: q for q in reference_data}

    # 3) Rubric
    rubric_text = request.form.get("rubric", "")

    # 4) Student PDF/ZIP
    if 'files' not in request.files or not request.files['files'].filename.strip():
        return render_template('index.html', error="No student file uploaded.")
    student_file = request.files['files']
    stu_filename = secure_filename(student_file.filename)
    stu_local_path = os.path.join(app.config['UPLOAD_FOLDER'], stu_filename)
    student_file.save(stu_local_path)

    # Optional: Upload student file to Blob Storage
    if BLOB_CONNECTION_STRING and BLOB_CONTAINER:
        try:
            blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
            container_client = blob_service_client.get_container_client(BLOB_CONTAINER)
            with open(stu_local_path, 'rb') as data:
                container_client.upload_blob(name=stu_filename, data=data, overwrite=True)
        except Exception as e:
            print(f"Blob upload (student) failed: {e}")

    # 5) Parse student
    student_text = cleanup_pdf_artifacts(extract_text_with_form_recognizer(stu_local_path))
    student_data = parse_student_text(student_text)

    # 6) Grade
    results = []
    total_score_by_student = defaultdict(float)
    total_points_by_student = defaultdict(float)

    for s_q in student_data:
        q_num = s_q["number"]
        if q_num in ref_dict:
            ref_info = ref_dict[q_num]
            question_points = ref_info["points"]
            q_text = ref_info["question_text"]
            ref_answer = ref_info["reference_answer"]
            stu_answer = s_q["answer"]

            # Decide if partial credit or 0/full
            if is_open_ended(q_text):
                raw_feedback = grade_open_ended_question(ref_answer, stu_answer, rubric_text, question_points)
            else:
                raw_feedback = grade_mc_or_tf_question(ref_answer, stu_answer, question_points)

            parsed = parse_gpt_feedback(raw_feedback)
            try:
                question_score = float(parsed["score"])
            except:
                question_score = 0.0

            row_data = {
                "StudentFile": stu_filename,
                "QuestionNumber": q_num,
                "QuestionText": q_text,
                "Feedback": {
                    "score": question_score,
                    "overall": parsed["overall"]
                }
            }
            results.append(row_data)

            total_score_by_student[stu_filename] += question_score
            total_points_by_student[stu_filename] += question_points

    # 7) Summarize
    overall_scores = []
    for student_file, obtained_score in total_score_by_student.items():
        possible = total_points_by_student[student_file]
        pct = 0
        if possible > 0:
            pct = (obtained_score / possible) * 100
        overall_scores.append({
            "student_file": student_file,
            "score_obtained": round(obtained_score, 2),
            "score_possible": possible,
            "percent": round(pct, 2)
        })

    # Store question-by-question details in the global dictionary
    # so the /details/<student_file> route can display them
    student_details_cache = defaultdict(list)
    for row in results:
        filename = row["StudentFile"]
        student_details_cache[filename].append(row)

    return render_template('index.html',
                           overall_scores=overall_scores,
                           error=None  # no error
                           # We don't pass "results" to index directly anymore
                           # because we're doing the 2-page approach
                          )

@app.route('/details/<path:student_file>')
def details_page(student_file):
    """
    Displays the question-by-question breakdown for a single student's exam.
    """
    global student_details_cache
    if student_file not in student_details_cache:
        return "No details found for this student.", 404

    data_for_student = student_details_cache[student_file]
    return render_template('details.html',
                           student_file=student_file,
                           details=data_for_student)

if __name__ == '__main__':
    app.run(debug=True)
