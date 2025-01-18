#from huggingface_hub import snapshot_download
# model_name = "Jai-V/fine_tuned_model_mistral_test"
# methods = ['q4_k_m']
# base_model = r"C:/Users/jarvis/Desktop/JARVIS Jr ML Engineer/Gemini/llama.cpp-master/original_model/"
# quantized_path = r"C:/Users/jarvis/Desktop/JARVIS Jr ML Engineer/Gemini/llama.cpp-master/quantized_model/"
# snapshot_download(repo_id=model_name, local_dir=base_model , local_dir_use_symlinks=False)
# original_model = quantized_path+'/FP16.gguf'
from huggingface_hub import snapshot_download
model_id="Jai-V/fine_tuned_model_llama_test_1" #"Jai-V/outputs" #"lmsys/vicuna-13b-v1.5"
snapshot_download(repo_id=model_id, local_dir="llama_fine_tune",
                  local_dir_use_symlinks=False, revision="main")