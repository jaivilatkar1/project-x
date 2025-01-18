import streamlit as st
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_experimental.agents import create_csv_agent
import google.generativeai as genai
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.llms import OpenAI
from dotenv import load_dotenv
from groq import Groq
import openai

load_dotenv()
genai.configure(api_key=os.getenv("Google_API_KEY"))

def get_csv_text(user_csv,model,q):
    text=""
    reader=create_csv_agent(model,user_csv,verbose=True)
    if q:
        text=reader.run(q)
        return text

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
    st.set_page_config("Ask your CSV")
    st.header("Chat with CSV using Gemini💁")
    #user_question = st.text_input("Ask a Question from the CSV Files")
    user_csv=st.file_uploader("Upload your PDF Files and Click on the Submit & Process Button", type="csv")
    if user_csv is not None:
        #if st.button("Submit & Process"):
            model=ChatGoogleGenerativeAI(model="gemini-pro",temperature=0.3)
            # agent=create_csv_agent(llm=model,user_csv,verbose=True)
            reader=create_csv_agent(model,user_csv,allow_dangerous_code=True)
            user_question = st.text_input("Ask a question about the CSV data:")
            #if user_question:
            #raw_text = get_csv_text(user_csv,model,user_question)
            if user_question is not None and user_question!="":
                if st.button("Submit & Process"):
                    with st.spinner("Processing..."):
                        text=reader.run(user_question)
                        #return text
                        st.write(text)
            # text_chunks = get_text_chunk(raw_text)
            # get_vector_store(text_chunks)
            #st.success("Done")

if __name__=="__main__":
    main()