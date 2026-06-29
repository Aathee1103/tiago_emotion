from flask import Flask, request, jsonify
import torch
import soundfile as sf
import io
import numpy as np
import librosa

from transformers import (
    AutoModelForSpeechSeq2Seq,
    AutoProcessor,
    AutoModelForCausalLM,
    AutoTokenizer,
    pipeline
)

# =========================
# FLASK
# =========================
app = Flask(__name__)

# =========================
# DEVICE
# =========================
device = "cuda" if torch.cuda.is_available() else "cpu"

# =========================
# WHISPER
# =========================
whisper_id = "openai/whisper-large-v3-turbo"

whisper_model = AutoModelForSpeechSeq2Seq.from_pretrained(
    whisper_id,
    torch_dtype=torch.float16 if device == "cuda" else torch.float32,
    low_cpu_mem_usage=True,
    use_safetensors=True
).to(device)

whisper_processor = AutoProcessor.from_pretrained(whisper_id)

whisper_pipe = pipeline(
    "automatic-speech-recognition",
    model=whisper_model,
    tokenizer=whisper_processor.tokenizer,
    feature_extractor=whisper_processor.feature_extractor,
    device=0 if device == "cuda" else -1,
)

# =========================
# QWEN
# =========================
qwen_id = "Qwen/Qwen2.5-7B-Instruct"

tokenizer = AutoTokenizer.from_pretrained(qwen_id, trust_remote_code=True)

qwen_model = AutoModelForCausalLM.from_pretrained(
    qwen_id,
    device_map="auto",
    torch_dtype="auto",
    trust_remote_code=True
)

# =========================
# MEMORY
# =========================
messages = [
   {
  "role": "system",
  "content": (
    "You are a robotic assistant named as Tiago or Thiago. "
    "Do NOT use markdown formatting. "
    "Do NOT use #, ##, bullet points, or special formatting. "
    "Respond in plain natural sentences only."
  )
}
]

def generate(messages):
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(prompt, return_tensors="pt").to(qwen_model.device)

    outputs = qwen_model.generate(
        **inputs,
        max_new_tokens=180,
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
        repetition_penalty=1.1,
        pad_token_id=tokenizer.eos_token_id
    )

    return tokenizer.decode(
        outputs[0][inputs.input_ids.shape[1]:],
        skip_special_tokens=True
    ).strip()

# =========================
# API
# =========================
@app.route("/upload_audio", methods=["POST"])
def upload_audio():

    audio_file = request.files["file"]

    audio_bytes = audio_file.read()
    audio_buffer = io.BytesIO(audio_bytes)

    # -------------------------
    # LOAD AUDIO
    # -------------------------
    audio, sr = sf.read(audio_buffer)

    # convert stereo → mono
    if len(audio.shape) > 1:
        audio = np.mean(audio, axis=1)

    # -------------------------
    # RESAMPLE TO 16kHz (IMPORTANT)
    # -------------------------
    if sr != 16000:
        audio = librosa.resample(audio.astype(np.float32), orig_sr=sr, target_sr=16000)
        sr = 16000

    audio = audio.astype(np.float32)

    # -------------------------
    # WHISPER
    # -------------------------
    result = whisper_pipe(
        {"array": audio, "sampling_rate": sr},
        generate_kwargs={"language": "english"}
    )

    text = result["text"]
    print("USER:", text)

    # -------------------------
    # QWEN
    # -------------------------
    messages.append({"role": "user", "content": text})
    reply = generate(messages)
    messages.append({"role": "assistant", "content": reply})

    print("BOT:", reply)

    return jsonify({
        "text": text,
        "response": reply
    })



if __name__ == "__main__":
    app.run(host="10.68.0.128", port=5000)