#!/usr/bin/env python3

from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

# =========================
# MODEL LOAD
# =========================

model_id = "Qwen/Qwen2.5-7B-Instruct"

print("Loading model...")

tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    device_map="auto",
    torch_dtype="auto",
    trust_remote_code=True
)

print("Model loaded.\n")

# =========================
# INPUT OBJECT
# =========================

obj = input("Object: ").strip()
details = input("Details about object: ").strip()

# =========================
# SYSTEM PROMPT
# =========================

system_prompt = f"""
You are an emotional memory assistant.

RULES:
- Use ONLY the given object and details.
- Do NOT invent facts or experiences.
- Always use second-person ("you").
- Keep responses 3–6 sentences.
- End with ONE question.

OBJECT: {obj}
DETAILS: {details}
"""

# =========================
# CHAT HISTORY
# =========================

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": f"Describe this memory: {obj}"}
]

# =========================
# GENERATION FUNCTION
# =========================

def generate(chat_messages):
    prompt = tokenizer.apply_chat_template(
        chat_messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    outputs = model.generate(
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
# FIRST RESPONSE
# =========================

MAX_TURNS = 5
turn = 0

reply = generate(messages)
turn += 1

print("\nROBOT:\n", reply)

messages.append({"role": "assistant", "content": reply})

# =========================
# CHAT LOOP
# =========================

while True:
    user_input = input("\nYOU: ").strip()

    if user_input.lower() in ["exit", "quit"]:
        break

    messages.append({"role": "user", "content": user_input})

    reply = generate(messages)
    turn += 1

    # ✅ ADD GOODBYE ONLY ON 5th RESPONSE
    if turn == MAX_TURNS:
        # force no question in final message
        if "?" in reply:
            # remove last sentence if it contains a question
            sentences = reply.split(".")
            sentences = [s for s in sentences if "?" not in s]
            reply = ".".join(sentences).strip()

        reply += "\n\nok, Hope you had a good time talking with me. Take care and goodbye!"

    print("\nROBOT:\n", reply)

    messages.append({"role": "assistant", "content": reply})

    # stop after 5 responses
    if turn >= MAX_TURNS:
        break