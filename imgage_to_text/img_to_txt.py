import google.generativeai as genai
import os
import base64
genai.configure(api_key="")
from pdf2image import convert_from_path
from PIL import Image
import google.generativeai as genai

# Configure the API key
# genai.configure(api_key="YOUR_API_KEY")

# Load the PDF and convert pages to images
images = convert_from_path(f"C:/Users/jarvis/Downloads/ELM_company.pdf",poppler_path=f"C:/Users/jarvis/Downloads/Release-24.08.0-0/poppler-24.08.0/Library/bin")

# Initialize the Gemini Vision model
model = genai.GenerativeModel(model_name="gemini-2.0-flash-exp")

# Define your prompt
prompt = "Please analyze the document and provide the text as it is in the document."

# Process each image
for img in images:
    response = model.generate_content([prompt, img])
    # print(response.text)
    with open("output.txt", "a", encoding="utf-8") as file:
        file.write(response.text+"\n\n")

