import streamlit as st
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import google.generativeai as genai
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.chains.question_answering import load_qa_chain
from dotenv import load_dotenv
import pdfplumber
from tabulate import tabulate
import camelot
import tempfile
import pandas as pd
from PIL import Image
import pytesseract

load_dotenv()
genai.configure(api_key=os.getenv("Google_API_KEY"))

def get_pdf_text(pdf_docs):
    text=""
    tables_text=""
    images_info=[]
    image_text = ""
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    for pdf in pdf_docs:
        reader=PdfReader(pdf)
        for page in reader.pages:
            text+=page.extract_text()
        with pdfplumber.open(pdf) as pdfplumber_reader:
            for i, page in enumerate(pdfplumber_reader.pages):
                # Extract tables from each page
                table = page.extract_table()
                if table:
                    # Convert the table to a Pandas DataFrame
                    df = pd.DataFrame(table[1:], columns=table[0])
                    # Convert the DataFrame to text and append it
                    tables_text += df.to_string(index=False) + "\n\n"
                for img_index, img in enumerate(page.images):
                    # Extract image using its bbox (bounding box)
                    bbox = (round(img['x0'],2), round(img['top'],2), round(img['x1'],2), round(img['bottom'],2))
                    image = page.within_bbox(bbox).to_image()
                    image_filename = "img.png"
                    image.save(image_filename)  # Save the image
                    images_info.append(image_filename)
                for image_file in images_info:
                    img = Image.open(image_file)
                    image_text += pytesseract.image_to_string(img) + "\n"
    return text+tables_text+image_text

def get_text_chunk(text):
    text_splitter=RecursiveCharacterTextSplitter(chunk_size=10000,chunk_overlap=1000)
    chunks=text_splitter.split_text(text)
    return chunks

def get_vector_store(text_chunks):
    embeddings=GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vector_store=FAISS.from_texts(text_chunks,embedding=embeddings)
    vector_store.save_local("faiss_index")

def get_conversation_chain():
    prompt_template=""" Answer the question as detailed as possible from the provided context, make sure to provide all the details, if the answer is not in
    provided context just say, "answer is not available in the context", don't provide the wrong answer\n\n
    Context:\n {context}?\n
    Question: \n{question}\n"""
    model=ChatGoogleGenerativeAI(model="gemini-pro",temperature=0.3)
    prompt=PromptTemplate(template=prompt_template, input_variables=["context","question"])
    chain=load_qa_chain(model,chain_type="stuff",prompt=prompt)
    return chain

def user_input(user_question):
    embeddings=GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    new_db=FAISS.load_local("faiss_index",embeddings,allow_dangerous_deserialization=True)
    docs=new_db.similarity_search(user_question)
    chain=get_conversation_chain()
    response=chain({"input_documents":docs,"question":user_question},return_only_outputs=True)
    print(response)
    st.write("Reply: ",response["output_text"])

def main():
    st.set_page_config("Chat PDF")
    st.header("Chat with PDF using Gemini💁")
    user_question = st.text_input("Ask a Question from the PDF Files")
    if user_question:
        user_input(user_question)
    with st.sidebar:
        st.title("Menu:")
        pdf_docs = st.file_uploader("Upload your PDF Files and Click on the Submit & Process Button", accept_multiple_files=True)
        if st.button("Submit & Process"):
            with st.spinner("Processing..."):
                raw_text = get_pdf_text(pdf_docs)
                text_chunks = get_text_chunk(raw_text)
                get_vector_store(text_chunks)
                st.success("Done")
if __name__=="__main__":
    main()