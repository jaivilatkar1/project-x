Step 1: Install the dependencies
First, ensure you have the required Python packages:

pip install llama-cpp-python==0.3.15
pip install streamlit aiohttp 

Step 2: Download the Jan-v1 GGUF version
Before downloading the model, create a new directory named models/ using the following command:

mkdir -p models

Then, download the model using the following command:

curl -L https://huggingface.co/janhq/Jan-v1-4B-GGUF/resolve/main/Jan-v1-4B-Q4_K_M.gguf -o Jan-v1-4B-Q4_K_M.gguf

Step 3: Set up the Serper API key
Sign up or log in to your Serper account: https://serper.dev/api-keys and select the API Keys tab, then copy the default API key for this demo. Let’s set up this key as an environment variable as follows:

export SERPER_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxx
 
