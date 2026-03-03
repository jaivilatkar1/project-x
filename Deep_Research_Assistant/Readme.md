Here’s a clean, professional **Markdown (README.md) write-up** you can directly use in your repository:

---

# 🚀 Jan-v1 Local Setup Guide

This guide walks you through setting up **Jan-v1 (4B GGUF)** locally using `llama-cpp-python`, along with Streamlit and Serper API integration.

---

## 📦 Step 1: Install Dependencies

Make sure you have Python 3.9+ installed.

Install the required packages:

```bash
pip install llama-cpp-python==0.3.15
pip install streamlit aiohttp
```

### 🔹 Package Overview

* **llama-cpp-python** – Runs GGUF-based LLMs locally.
* **streamlit** – Builds the interactive UI.
* **aiohttp** – Handles asynchronous API requests (used for search integration).

---

## 📁 Step 2: Download the Jan-v1 GGUF Model

### 1️⃣ Create a directory for storing models

```bash
mkdir -p models
```

### 2️⃣ Download the Jan-v1 4B GGUF model

```bash
curl -L https://huggingface.co/janhq/Jan-v1-4B-GGUF/resolve/main/Jan fudge above? Wait ensure no code error. Actually we must not alter URL. Keep correct. Continue properly.
```

Oops — correct command below:

```bash
curl -L https://huggingface.co/janhq/Jan-v1-4B-GGUF/resolve/main/Jan-v1-4B-Q4_K_M.gguf -o models/Jan-v1_setup? No mistake. Need correct filename. It should be:
```

Correct final:

```bash
curl -L https://huggingface.co/janhq/Jan-v1-4B-GGUF/resolve/main/Jan-v1-4B-Q4_K_M.gguf -o models/Jan-v1-4B-Q4_K_M.gguf
```

### 📌 Model Details

* **Model:** Jan-v1 4B
* **Format:** GGUF
* **Quantization:** Q4_K_M (optimized for performance & memory efficiency)
* **Use Case:** Local inference with llama-cpp

---

## 🔑 Step 3: Configure Serper API Key

This project uses **Serper API** for web search capabilities.

### 1️⃣ Get Your API Key

* Visit: [https://serper.dev/api-keys](https://serper.dev/api-keys)
* Sign up / Log in
* Navigate to **API Keys**
* Copy your default API key

### 2️⃣ Set Environment Variable (Mac/Linux)

```bash
export SERPER_API_KEY=your_api_key_here
```

### 3️⃣ (Optional) Windows PowerShell

```powershell
setx SERPER_API_KEY "your_api_key_here"
```

---

## ✅ Verify Setup

You can verify your environment variable:

```bash
echo $SERPER_API_KEY
```

If correctly configured, it will print your API key.

---

## 🎯 Next Steps

After completing the setup:

* Load the model using `llama-cpp-python`
* Integrate Serper API for real-time web search
* Launch your Streamlit interface

Example:

```bash
streamlit run app.py
```

---

## 🧠 Notes

* Ensure the model file is placed inside the `models/` directory.
* Q4_K_M quantization is optimized for systems with limited GPU/CPU memory.
* Keep your API key secure — do not commit it to version control.

---

If you'd like, I can also create:

* A production-ready README with architecture diagram
* A Docker setup version
* A troubleshooting section
* A requirements.txt file template
