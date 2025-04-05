---

### 📄 README.txt – Resume ATS Checker Setup Guide

🔧 Prerequisites

Ensure you have Python 3.8+ installed. You can verify with:
```bash
python --version
```

---

#### 🧩 1. Install Required Dependencies

Use the provided `requirements.txt` file:

```bash
pip install -r requirements.txt
```

This installs:
- Streamlit (web interface)
- LangChain & Gemini integrations
- Google Drive API libraries
- PDF & DOCX parsers
- dotenv for environment management

---

#### 🗂️ 2. Setup Google Cloud Credentials

You need a **Google Cloud Service Account** key to access Google Drive API.

##### 📌 Steps to generate the `credentials.json`:

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or select an existing one).
3. Enable **Google Drive API**:
   - Go to **APIs & Services > Library**.
   - Search and enable **Google Drive API**.
4. Create **Service Account Credentials**:
   - Go to **APIs & Services > Credentials**.
   - Click **Create Credentials** > **Service Account**.
   - Grant access (you can skip optional steps).
5. Create a **JSON Key** for the service account.
6. Download it and place it in your local directory.
7. Rename it (optional):  
   Example: `gen-lang-client-XXXX.json`
8. Share any Drive files/folders with the **client email** from the JSON so it can access those files.

---

#### 📁 3. Folder Structure Suggestion

```
ats_checker/
│
├── main.py
├── requirements.txt
├── .env
└── gen-lang-client-XXXX.json

```

---

#### 🔑 4. .env File

Create a `.env` file in the root directory to manage keys:

```
GOOGLE_API_KEY=YOUR_GEMINI_API_KEY
GOOGLE_APPLICATION_CREDENTIALS=C:/full/path/to/gen-lang-client-XXXX.json
```

**OR** you can directly edit the path in your code if not using `.env`.

---

#### ▶️ 5. Running the App

Run the app via Streamlit:

```bash
streamlit run main.py
```

This will open a local web page at:  
[http://localhost:8501](http://localhost:8501)

---

#### 🧪 6. Using the App

1. **Upload Resumes** (`PDF` or `DOCX`) via browser or input Google Drive file IDs.
2. **Paste Job Description**.
3. Click **"Check Resumes"**.
4. AI will analyze and show:
   - Match Score
   - Missing Skills
   - Suggestions for Improvement

---

#### 🔄 7. Troubleshooting

- Make sure `gen-lang-client-XXXX.json` exists in the path you specified.
- Ensure the Drive files are shared with the service account.
- If using Gemini API, make sure your API key is active from [Google AI Studio](https://makersuite.google.com/app/apikey).

---
