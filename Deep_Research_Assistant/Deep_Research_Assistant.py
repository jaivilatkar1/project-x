import streamlit as st
import json
import time
import re
from datetime import datetime
from typing import List, Dict, Optional
import asyncio
import aiohttp
from llama_cpp import Llama
import os
import ssl
import certifi
from dataclasses import dataclass

def sections_for_format(fmt: str)->List[str]:
    fmt=(fmt or "").strip().lower()
    if fmt=="executive":
        return ["EXECUTIVE SUMMARY"]
    elif fmt=="detailed":
        return ["INTRODUCTION","DETAILED ANALYSIS","CURRENT TRENDS AND DEVELOPMENTS","IMPLICATIONS AND RECOMMENDATIONS","CONCLUSION"]
    elif fmt=="academic":
        return ["ABSTRACT","INTRODUCTION","METHODOLOGY","FINDINGS","DISCUSSION","CONCLUSION"]
    elif fmt=="presentation":
        return ["OVERVIEW","KEY INSIGHTS","RECOMMENDATIONS","NEXT STEPS","CONCLUSION"]
    return ["INTRODUCTION","DETAILED ANALYSIS","CONCLUSION"]

def extract_final_block(text: str)->str:
    m=re.search(r"<final>([\s\S]*?)</final>",text,flags=re.IGNORECASE)
    if m:
        cleaned_text=m.group(1).strip()
    else:
        cleaned_text=text
    preamble_patterns=[
        r"^(?:note:|okay,|hmm,|internal|let me|i (?:will|'ll)|as an ai|thinking|plan:|here is your report|the following is|i have prepared|i am presenting|based on the provided information|below is the report|i hope this meets your requirements|this report outlines|this is the final report).*?$",
        r"^(?:Here is the report|I have compiled the report|The report is provided below|This is the requested report).*?$", # More specific preambles
        r"^(?:Please find the report below|Here's the report).*?$"
    ]
    for pattern in preamble_patterns:
        cleaned_text=re.sub(pattern,"",cleaned_text,flags=re.IGNORECASE|re.MULTILINE).strip()
    cleaned_text=re.sub(r"(?m)^\s*[-*•]\s+","",cleaned_text).strip()
    cleaned_text=re.sub(r"[#`*_]{1,3}","",cleaned_text).strip()
    headers = [
        "EXECUTIVE SUMMARY","INTRODUCTION","DETAILED ANALYSIS","CURRENT TRENDS AND DEVELOPMENTS",
        "IMPLICATIONS AND RECOMMENDATIONS","CONCLUSION","ABSTRACT","METHODOLOGY","FINDINGS",
        "DISCUSSION","OVERVIEW","KEY INSIGHTS","RECOMMENDATIONS","NEXT STEPS"
    ]
    sorted_headers=sorted(headers,key=len,reverse=True)
    first_pos=-1
    for h in sorted_headers:
        match=re.search(r'\b'+re.escape(h),cleaned_text,flags=re.IGNORECASE)
        if match:
            if first_pos==-1 or match.start()<first_pos:
                first_pos=match.start()
    if first_pos>=0:
        cleaned_text=cleaned_text[first_pos:].strip()
    return cleaned_text

@dataclass
class ResearchConfig:
    model_path:str="/Users/jai/Agentic AI/YTRAG/models/Jan-v1-4B-Q4_K_M.gguf"
    max_tokens:int=4096
    temperature:float=0.6
    top_p:float=0.95
    top_k:int=20
    context_length:int=4096
    search_api_key:str=os.getenv("SERPER_API_KEY","")
    search_engine:str="serper"

class DeepResearchAssistant:
    def __init__(self,config:ResearchConfig):
        self.config=config
        self.llm=None
        self.demo_mode=False
    def load_model(self):
        try:
            if not os.path.exists(self.config.model_path):
                print(f"Model file not found at {self.config.model_path}")
                return False
            file_size_gb=os.path.getsize(self.config.model_path)/(1024*1024*1024)
            if file_size_gb<1:
                print(f"Model file size ({file_size_gb:.2f} GB) is smaller than expected. Please verify the model file.")
                return False
            self.llm=Llama(model_path=self.config.model_path,n_ctx=self.config.context_length,
                           verbose=False,n_threads=max(1,min(4,os.cpu_count()//2)),n_gpu_layers=0,
                           use_mmap=True,use_mlock=False,n_batch=128,f16_kv=True)
            test=self.llm("Hello world",max_tokens=5,temperature=0.1,echo=False)
            ok=bool(test and 'choices' in test)
            print("Model loaded" if ok else "Model loaded but test generation failed")
            return ok
        except Exception as e:
            print(f"Error loading model: {e}")
            return False

    def generate_response(self,prompt:str,max_tokens:int=None,extra_stops:Optional[List[str]]=None)->str:
            if not self.llm:
                return "Model not loaded."
            stops=["</s>","<|im_end|>","<|endoftext|"]
            if extra_stops:
                stops.extend(extra_stops)
            mt=max_tokens or self.config.max_tokens
            try:
                resp=self.llm(prompt,max_tokens=mt,temperature=self.config.temperature,top_p=self.config.top_p,
                            top_k=self.config.top_k,stop=stops,echo=False)
                return resp['choices'][0]['text'].strip()
            except Exception as e:
                return f"Error during generation: {e}"
    async def search_web(self,query:str,num_results:int=10)->List[Dict]:
        if self.config.search_api_key:
            return await self.search_serper(query,num_results)
        return []
    async def search_serper(self,query:str,num_results:int)->List[Dict]:
        url="https://google.serper.dev/search"
        payload={"q":query,"num":num_results}
        headers={"X-API-KEY":self.config.search_api_key,"Content-Type":"application/json"}
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        async with aiohttp.ClientSession() as session:
            async with session.post(url,json=payload,headers=headers,ssl=ssl_ctx) as response:
                data=await response.json()
                results=[]
                for item in data.get("organic",[]):
                    results.append({
                        'title':item.get("title",""),
                        'url':item.get('url',''),
                        'snippet':item.get('snippet',''),
                        'source':'web'
                    })
                return results
    def generate_search_queries(self,topic:str,focus_area:str,depth:str)->List[str]:
        counts={'surface':5,'moderate':8,'deep':15,'comprehensive':25}
        n=counts.get(depth,8)
        base=[
            f"{topic} overview", f"{topic} recent developments", f"{topic} academic studies",
            f"{topic} case studies", f"{topic} policy and regulations", f"{topic} technical approaches",
            f"{topic} market analysis", f"{topic} statistics and data",
        ]
        return base[:n]

    def synthesize_research(self,topic:str,search_results:List[Dict],focus_area:str,report_format:str)->str:
        context_lines=[]
        for i,result in enumerate(search_results[:20]):
            title=result.get('title','')
            snippet=result.get('snippet','')
            context_lines.append(f"Source {i+1} Title: {title}\nSource {i+1} Summary: {snippet}")
        context="\n".join(context_lines)
        sections=sections_for_format(report_format)
        sections_text='\n'.join(sections)
        synthesis_prompt=f"""You are an expert research analyst. Write the final, polished report on: "{topic}" for a professional, real-world audience.
            ***CRITICAL INSTRUCTIONS:***
            - Your entire response MUST be the final report, wrapped **EXACTLY** inside <final> and </final> tags.
            - DO NOT output any text, thoughts, or commentary BEFORE the <final> tag or AFTER the </final> tag.
            - DO NOT include any conversational filler, internal thoughts, or commentary about the generation process (e.g., "As an AI...", "I will now summarize...", "Here is your report:").
            - DO NOT use markdown formatting (e.g., #, ##, *, -).
            - DO NOT use bullet points or lists.
            - Maintain a formal, academic/professional tone throughout.
            - Ensure the report is complete and self-contained.
            - Include the following section headers, in this order, and no others:
            {sections_text}
            Guidance:
            - Base your writing strictly on the Research Notes provided below. If the notes lack specific data, write a careful, methodology-forward analysis without inventing facts or numbers.
            Research Notes:
            {context}
            Now produce ONLY the final report:
            <final>
            ...your report here...
            </final>
            """
        
        raw=self.generate_response(synthesis_prompt,max_tokens=1800,extra_stops=["</final>"])
        final_report=extract_final_block(raw)
        final_report=re.sub(r"(?m)^\s*[-*•]\s+","",final_report).strip()
        final_report=re.sub(r'[#`*_]{1,3}','',final_report).strip()
        first=next((h for h in sections if h in final_report),None)
        if first:
            final_report=final_report[final_report.find(first):].strip()
        return final_report

def main():
    st.set_page_config(page_title="Deep Research Assistant",page_icon="🔍",layout="wide")
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.25rem; border-radius: 10px; color: white; text-align: center; margin-bottom: 1rem;">
        <h1 style="margin:0;"> Deep Research Assistant</h1>
    </div>
    """,unsafe_allow_html=True)
    if 'research_assistant' not in st.session_state:
        config=ResearchConfig()
        st.session_state.research_assistant=DeepResearchAssistant(config)
        st.session_state.model_loaded=st.session_state.research_assistant.load_model()
        st.session_state.research_results=[]
    if not st.session_state.research_assistant.config.search_api_key:
        st.warning("No search API key provided. Web search functionality will be disabled.")
    research_topic=st.text_area("Research Topic",placeholder="Enter the research topic or question here...",height=100)
    col1a,col1b=st.columns(2)
    with col1a:
        research_depth=st.selectbox("Research Depth",["Surface","Moderate","Deep","Comprehensive"],index=1,
                                    format_func=lambda x:{"surface": "Surface (5-8 sources)","moderate": "Moderate (10-15)",
                                                            "deep": "Deep Dive (20-30)","comprehensive": "Comprehensive (40+)"}[x.lower()])
        focus_area=st.selectbox("Focus Area",["general", "academic", "business", "technical", "policy"], index=0, format_func=str.title)
    with col1b:
        time_frame=st.selectbox("Time Frame",['current','recent','comprehensive'],index=1,
                                format_func=lambda x:{"current":"Current (≤6 months)","recent":"Recent (≤2 years)","comprehensive":"All time"}[x])
        report_format=st.selectbox("Report Format",["executive","detailed","academic","presentation"],index=1,
                                   format_func=lambda x:{"executive":"Executive Summary","detailed":"Detailed Analysis","academic":"Academic Style","presentation":"Presentation Format"}[x])
    if st.button("Start Deep Research",type="primary",use_container_width=True):
        if not st.session_state.model_loaded:
            st.error("Model failed to load. Please check the model path and try again.")
        elif not research_topic.strip():
            st.error("Please enter a research topic to proceed.")
        else:
            start_research(research_topic, research_depth, focus_area, time_frame, report_format)
    if st.session_state.research_results:
        display_research_results(st.session_state.research_results)

def start_research(topic: str, depth: str, focus: str, timeframe: str, format_type: str):
    assistant=st.session_state.research_assistant
    progress_bar=st.progress(0)
    status_text=st.empty()
    try:
        status_text.text("Generating search queries...")
        progress_bar.progress(15)
        queries=assistant.generate_search_queries(topic,focus,depth)
        status_text.text("Searching sources...")
        progress_bar.progress(40)
        all_results=[]
        for i,query in enumerate(queries):
            loop=asyncio.new_event_loop()
            results=loop.run_until_complete(assistant.search_web(query,num_results=5))
            all_results.extend(results)
            loop.close()
            progress_bar.progress(40+int((i+1)/max(1,len(queries))*30))
            time.sleep(0.05)
        status_text.text("Synthesizing research report...")
        progress_bar.progress(80)
        research_report=assistant.synthesize_research(topic,all_results,focus,format_type)
        status_text.text("Research complete!")
        progress_bar.progress(100)
        st.session_state.research_results={'topic': topic,'report': research_report,'sources': all_results,'queries': queries,
            'config': {'depth': depth, 'focus': focus, 'timeframe': timeframe, 'format': format_type},'timestamp': datetime.now()}
        time.sleep(0.3)
        status_text.empty()
        progress_bar.empty()
    except Exception as e:
        st.error(f"An error occurred during research: {e}")
        status_text.empty()
        progress_bar.empty()

def display_research_results(results: Dict):
    st.header(f"Research Report: {results['topic']}")
    st.subheader("Final Synthesized Report")
    st.markdown(f'<div style="background:#f8f9ff;padding:1rem;border-radius:10px;border:1px solid #e1e8ed;">{results["report"]}</div>',
        unsafe_allow_html=True,)
    with st.expander("Sources",expanded=False):
        for i,source in enumerate(results['sources'][:12]):
            st.markdown(f"""<div style="background:#fff;padding:0.75rem;border-radius:8px;border:1px solid #e1e8ed;margin:0.4rem 0;">
                <h4 style="margin:0 0 .25rem 0;">{source['title']}</h4>
                <p style="margin:0 0 .25rem 0;">{source['snippet']}</p>
                <small><a href="{source['url']}" target="_blank">{source['url']}</a></small>
            </div>""", unsafe_allow_html=True)
    st.markdown("### Export")
    c1,c2,c3=st.columns(3)
    with c1:
        report_text=f"Research Report: {results['topic']}\n\n{results['report']}"
        st.download_button("Download Report as Text",data=report_text,file_name=f"{results['topic']}_research_report.txt",mime="text/plain")
    with c2:
        json_data=json.dumps(results, default=str, indent=2)
        st.download_button("Download Full Data as JSON",data=json_data,file_name=f"{results['topic']}_research_data.json",mime="application/json")
    with c3:
        if st.button("Start New Research"):
            st.session_state.research_results=None
            st.experimental_rerun()

if __name__=="__main__":
    main()

