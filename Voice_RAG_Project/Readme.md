# Voice-Enabled Retrieval-Augmented Generation (RAG) System

This project showcases the development of a voice-interactive Retrieval-Augmented Generation (RAG) system utilizing OpenAI's SDK and Streamlit. The application empowers users to upload PDF documents, pose queries, and receive responses in both text and synthesized speech formats, leveraging OpenAI's text-to-speech capabilities.

## Features

- **Voice-Interactive RAG System:** Integrates OpenAI's SDK to facilitate voice-based interactions.
- **PDF Document Handling:** Supports the upload and processing of PDF files, segmenting them into manageable chunks for analysis.
- **Efficient Similarity Search:** Employs Qdrant as a vector database to enable rapid and accurate similarity searches.
- **Real-Time Text-to-Speech:** Implements immediate text-to-speech conversion with a selection of voice options.
- **User-Friendly Interface:** Provides an intuitive Streamlit-based interface for seamless user interaction.
- **Audio Response Download:** Allows users to download generated audio responses in MP3 format.
- **Multi-Document Support:** Facilitates the upload and tracking of multiple documents within the system.

## Getting Started

Follow these steps to set up and run the Voice RAG application:

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/jaivilatkar1/project-x.git
   cd project-x/Voice_RAG_Project
   ```
   **OR**
   **Download the File**
   Click on Voice_RAG_Project folder and then click on the code file and click on the download button.
   
3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure API Keys:**
   - **OpenAI API Key:** Obtain from [OpenAI Platform](https://platform.openai.com/).
   - **Qdrant Cloud Credentials:** Sign up at [Qdrant Cloud](https://cloud.qdrant.io/) to acquire your API key and URL.
   - **Environment Variables:** Create a `.env` file in the project directory with the following content:
     ```bash
     OPENAI_API_KEY='your-openai-api-key'
     QDRANT_URL='your-qdrant-url'
     QDRANT_API_KEY='your-qdrant-api-key'
     ```
5. **Launch the Application:**
   ```bash
   streamlit run rag_voice.py
   ```
6. **Interact with the System:** Open the provided URL in your web browser to begin using the Voice RAG application.

## How It Works

1. **Document Processing:**
   - **Upload:** Users need to upload "MY OVERVIEW.pdf" PDF document via the Streamlit interface uploaded in the Voice_RAG_Project folder on GitHub.
   - **Chunking:** Documents are divided into smaller segments using LangChain's `RecursiveCharacterTextSplitter`.
   - **Embedding:** Each segment is embedded using FastEmbed and stored in the Qdrant vector database.

2. **Query Handling:**
   - **Embedding Queries:** User questions are converted into embeddings.
   - **Retrieval:** Relevant document segments are fetched from Qdrant based on similarity.
   - **Response Generation:** A processing agent formulates a coherent, speech-friendly answer.
   - **Speech Optimization:** A text-to-speech (TTS) agent refines the response for optimal speech synthesis.

3. **Voice Response Generation:**
   - **Synthesis:** Text responses are transformed into speech using OpenAI's TTS capabilities.
   - **Playback Options:** Users can select from various voice personalities for audio playback.
   - **Download:** Audio responses are available for direct playback or can be downloaded as MP3 files.

## Additional Features

- **Real-Time Audio Streaming:** Enables immediate playback of synthesized responses.
- **Multiple Voice Options:** Offers a range of voice personalities to suit user preferences.
- **Document Source Tracking:** Maintains a record of document sources for reference.
- **Progress Monitoring:** Displays real-time progress during document processing.

---

By following this guide, you can set up and explore the capabilities of a voice-enabled RAG system, enhancing the way users interact with document-based information through natural language and speech. 
