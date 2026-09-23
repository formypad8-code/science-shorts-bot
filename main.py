import json
import os
import requests
from groq import Groq
from gtts import gTTS
from moviepy.editor import ColorClip, TextClip, AudioFileClip, CompositeVideoClip

def send_telegram_alert(message):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        requests.post(url, json=payload)

# 1. Read memory
with open('tracker.json', 'r') as file:
    tracker = json.load(file)

chap_idx = tracker['current_chapter_index']
concept_idx = tracker['current_concept_index']

if chap_idx >= len(tracker['chapters']):
    print("Textbook is completely finished!")
    exit()

current_chap_name = tracker['chapters'][chap_idx]
concept_name = tracker['syllabus'][current_chap_name][concept_idx]
print(f"Generating video for: {current_chap_name} - {concept_name}")

# 2. Get script from Groq (Llama 3)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
prompt = f"""
You are an expert science teacher for SSC Class 10. Explain '{concept_name}' from '{current_chap_name}'.
Rules:
1. Use simple English. Explain difficult words instantly in 3-4 simple words.
2. Max 70 words per script to fit 30 seconds. If longer, split into multiple parts.
3. Output ONLY a raw JSON array of objects (no markdown blocks).
4. Format: [{{"title": "max 60 chars with 3 hashtags", "script": "spoken script words"}}]
"""

chat_completion = client.chat.completions.create(
    messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
    temperature=0.5,
)

raw_response = chat_completion.choices[0].message.content.replace('```json', '').replace('```', '').strip()
videos = json.loads(raw_response)

# 3. Build the MP4 video
for i, video in enumerate(videos):
    print(f"Processing Video {i+1}: {video['title']}")
    
    audio_filename = f"audio_part_{i+1}.mp3"
    tts = gTTS(text=video['script'], lang='en', tld='co.in')
    tts.save(audio_filename)
    
    audio_clip = AudioFileClip(audio_filename)
    video_duration = audio_clip.duration
    
    bg_clip = ColorClip(size=(1080, 1920), color=(15, 30, 60)).set_duration(video_duration)
    
    display_text = f"SSC Class 10 Science\n\n{concept_name}\n\n{video['title']}"
    txt_clip = TextClip(display_text, fontsize=65, color='white', size=(900, None), method='caption', align='center')
    txt_clip = txt_clip.set_position('center').set_duration(video_duration)
    
    final_video = CompositeVideoClip([bg_clip, txt_clip]).set_audio(audio_clip)
    
    # Clean filename to prevent GitHub upload errors
    safe_name = concept_name.replace(' ', '_').replace('?', '').replace(':', '').replace("'", "")
    video_filename = f"SSC_Science_{safe_name}_Part{i+1}.mp4"
    
    final_video.write_videofile(video_filename, fps=24, codec="libx264", audio_codec="aac")
    print(f"Finished creating {video_filename}!")

# 4. Update memory for tomorrow
tracker['current_concept_index'] += 1
if tracker['current_concept_index'] >= len(tracker['syllabus'][current_chap_name]):
    tracker['current_concept_index'] = 0
    tracker['current_chapter_index'] += 1
    if tracker['current_chapter_index'] >= len(tracker['chapters']):
        send_telegram_alert("Textbook Finished! All SSC Class 10 Science videos are done.")

with open('tracker.json', 'w') as file:
    json.dump(tracker, file, indent=2)
    
