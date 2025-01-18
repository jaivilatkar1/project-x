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
from groq import Groq

load_dotenv()
st.set_page_config(
    page_title="Llama Chat", layout="centered"
)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
#chat_completion = client.chat.completions.create(
#    model="llama3-8b-8192",temperature=0.5,max_tokens=1024,top_p=1,stop=None,stream=False,
#)
if "chat_history" not in st.session_state:
    st.session_state.chat_history=[]

st.title("Llama Chatbot")
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt=st.chat_input("Ask Llama")
if prompt:
    st.chat_message("user").markdown(prompt)
    st.session_state.chat_history.append({"role":"user","content":prompt})
    messages=[
        {"role":"system","content":"You are a helpful assistant"},
        *st.session_state.chat_history
    ]
    response=client.chat.completions.create(
        model= "llama-3.1-8b-instant",
        messages=messages
    )
    assistant_response=response.choices[0].message.content
    st.session_state.chat_history.append({"role":"assistant","content":assistant_response})
    
    with st.chat_message("assistant"):
        st.markdown(assistant_response)