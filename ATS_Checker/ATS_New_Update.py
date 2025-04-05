import streamlit as st
from PyPDF2 import PdfReader
from docx import Document
from langchain.agents import initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory
from langchain.tools import StructuredTool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
import google.generativeai as genai
from dotenv import load_dotenv
import os
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# Load environment variables
load_dotenv()
# os.environ["GOOGLE_APLICATION_CREDENTIALS"]=r"C:/Users/jarvis/Downloads/gen-lang-client-0436996816-e7639808da70.json"
# Configure the Generative AI model
genai.configure(api_key="your-api-key")

# Define input schema for the resume matching function
class MatchResumeInput(BaseModel):
    resume_text: str = Field(description="Text content of the resume")
    job_desc: str = Field(description="Text content of the job description")

# Function to match a resume against a job description
def match_resume(resume_text, job_desc):
    prompt = f"""
    Compare the resume below to the job description and provide:
    - A match score (0-100%).
    - Key missing skills.
    - Suggestions for improvement.

    Resume:
    {resume_text}

    Job Description:
    {job_desc}
    """
    model = genai.GenerativeModel("gemini-2.0-flash-exp")
    response = model.generate_content(prompt)
    return response.text

# Initialize the language model
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", google_api_key="your-api-key")

# Initialize conversation memory
memory = ConversationBufferMemory(memory_key="chat_history")

# Create a structured tool for resume matching
resume_match_tool = StructuredTool.from_function(
    name="match_resume",
    func=match_resume,
    description="Match resume with job description and provide insights.",
    args_schema=MatchResumeInput
)

# Initialize the agent with the tool
agent = initialize_agent(
    [resume_match_tool], llm, agent=AgentType.OPENAI_FUNCTIONS, memory=memory, verbose=True
)

# Function to extract text from a .docx file
def extract_text_from_docx(file):
    doc = Document(file)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)

# Function to extract text from a .pdf file
def extract_text_from_pdf(file):
    pdf_reader = PdfReader(file)
    full_text = []
    for page in pdf_reader.pages:
        text = page.extract_text()
        if text:
            full_text.append(text)
    return '\n'.join(full_text)

# Function to download files from Google Drive
def download_file_from_google_drive(file_id, creds):
    service = build('drive', 'v3', credentials=creds)
    file_metadata = service.files().get(fileId=file_id, fields="name, mimeType").execute()
    request = service.files().get_media(fileId=file_id)
    file = io.BytesIO()
    downloader = MediaIoBaseDownload(file, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    file.seek(0)
    return file, file_metadata["name"]
def extract_match_score(response_text):
    # Implement logic to parse the response and extract the match score
    # For example, if the response contains "Match Score: 85%", extract 85
    import re
    match = re.search(r"Match Score:\s*(\d+)%", response_text)
    if match:
        return int(match.group(1))
    return 0
# Streamlit UI
st.title("📄 AI-Powered Resume ATS Checker")
st.write("Upload multiple resumes and enter the job description to check compatibility.")

# File uploader allows multiple files
uploaded_files = st.file_uploader("Upload Resume Files", type=["pdf", "docx"], accept_multiple_files=True)
job_desc = st.text_area("Paste Job Description Here", height=200)

# Google Drive file ID input
st.write("Alternatively, enter Google Drive file IDs (comma-separated) to fetch resumes:")
drive_file_ids = st.text_input("Google Drive File IDs")

# Authenticate with Google Drive API
creds = None
if os.path.exists(r"C:/gen-lang-client-0436996816-e7639808da70.json"):
    # creds = service_account.Credentials.from_authorized_user_file('token.json')
    creds = service_account.Credentials.from_service_account_file(
    r"C:/gen-lang-client-0436996816-e7639808da70.json"
    )

if uploaded_files or drive_file_ids and job_desc:
    resume_texts = []

    # Process uploaded files
    if uploaded_files:
        for uploaded_file in uploaded_files:
            if uploaded_file.name.endswith('.pdf'):
                text = extract_text_from_pdf(uploaded_file)
            elif uploaded_file.name.endswith('.docx'):
                text = extract_text_from_docx(uploaded_file)
            else:
                continue
            resume_texts.append((uploaded_file.name, text))
        st.success(f"Extracted text from {len(uploaded_files)} resumes successfully.")

    # Fetch and process files from Google Drive
    if drive_file_ids:
        file_ids = [fid.strip() for fid in drive_file_ids.split(',')]
        for file_id in file_ids:
            file, file_name = download_file_from_google_drive(file_id, creds)
            # Assuming the file name can be retrieved or inferred; adjust as needed
            # file_name = f"resume_{file_id}.pdf"  # Placeholder name
            if file_name.endswith('.pdf'):
                text = extract_text_from_pdf(file)
            elif file_name.endswith('.docx'):
                text = extract_text_from_docx(file)
            else:
                continue
            resume_texts.append((file_name, text))
        st.success(f"Fetched and extracted text from {len(file_ids)} resumes from Google Drive successfully.")

    if st.button("Check Resumes"):
        with st.spinner("Analyzing with AI..."):
            results = []
            for name, text in resume_texts:
                combined_input = f"Resume:\n{text}\n\nJob Description:\n{job_desc}"
                response = agent.run({"input": combined_input})
                # Extract match score from response
                match_score = extract_match_score(response)
                results.append((name, match_score, response))

            # Sort results based on match score
            results.sort(key=lambda x: x[1])#, reverse=True)

            # Display results
            for idx, (name, score, analysis) in enumerate(results, 1):
                st.subheader(f"{idx}. {name}")#- Match Score: {score}%
                st.write(analysis)
else:
    st.error("Please upload at least one resume and enter a job description.")

# ::contentReference[oaicite:14]{index=14}
 
