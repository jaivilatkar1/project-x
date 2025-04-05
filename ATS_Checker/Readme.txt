AI-Powered Resume ATS Checker – Setup Guide
===========================================

1. Prerequisites
----------------
- Make sure you have Python 3.8 or higher installed.
- You can check the version with:
  python --version

2. Install Required Dependencies
--------------------------------
Run the following command to install the required Python libraries:

  pip install -r requirements.txt

3. Google Cloud API Setup for Google Drive
------------------------------------------

Follow these steps to enable access to Google Drive:

a. Go to https://console.cloud.google.com/
b. Create a new project or select an existing one.
c. Enable the "Google Drive API":
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Drive API" and enable it
d. Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "Service Account"
   - Follow the instructions to create the service account
e. After creating the account, go to "Keys" tab
   - Click "Add Key" > "JSON"
   - Download the JSON key file to your local machine
f. Save the JSON file (e.g., gen-lang-client-xxxx.json)
g. In your Google Drive, share the resume files with the service account email
   - The email will look like: service-account-name@project-id.iam.gserviceaccount.com

4. Folder Structure
-------------------
Project directory example:

  ats_checker/
  ├── main.py
  ├── requirements.txt
  ├── .env
  └── gen-lang-client-xxxx.json

5. .env File Setup
------------------
Create a file named ".env" in your project folder with the following content:

  GOOGLE_API_KEY=your_google_gemini_api_key
  GOOGLE_APPLICATION_CREDENTIALS=C:/full/path/to/gen-lang-client-xxxx.json

6. Run the Application
----------------------
Use Streamlit to launch the web interface:

  streamlit run main.py

7. How to Use
-------------
- Upload one or more resumes in PDF or DOCX format
- OR paste comma-separated Google Drive File IDs
- Enter the job description in the provided text area
- Click "Check Resumes"
- You will see a match score, missing skills, and suggestions for each resume

8. Notes
--------
- Make sure the JSON key file path is correct in your .env or code
- Ensure resume files in Google Drive are shared with your service account
- Get your Gemini API key from https://makersuite.google.com/app/apikey

