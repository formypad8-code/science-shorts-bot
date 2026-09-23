import json
import os
import time
import requests
import subprocess
import glob
from groq import Groq
from gtts import gTTS
from moviepy.editor import VideoFileClip, AudioFileClip

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
print(f"Generating Manim video for: {current_chap_name} - {concept_name}")

# 2. Get Manim Script & Spoken Audio from Groq
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
prompt = f"""
You are an expert Manim Community Python developer. Visually explain '{concept_name}' from '{current_chap_name}' for a vertical YouTube Short.
Rules:
1. The VERY FIRST line must be exactly this format: # TTS: [Insert the 60-word spoken explanation here]
2. The rest of the file must be valid Manim Community Python code starting with: from manim import *
3. Name the class exactly: class ScienceShort(Scene):
4. Use basic shapes (Circle, Dot, Line, Text). Group animations using self.play(). Use self.wait(2) between actions to total roughly 25 seconds of visual time.
5. Do NOT adjust config resolutions in the code.
6. Output ONLY the raw Python code. No markdown blocks like ```python, no explanations.
"""

max_retries = 3
raw_response = ""

for attempt in range(max_retries):
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-oss-20b",
            temperature=0.2, # Lower temperature for stricter code accuracy
        )
        raw_response = chat_completion.choices[0].message.content.strip()
        break
    except Exception as e:
        print(f"Groq busy/error (Attempt {attempt+1}/{max_retries}): {e}")
        if attempt < max_retries - 1:
            time.sleep(10)
        else:
            raise e

# 3. Parse output into Audio and Video components
lines = raw_response.replace('```python', '').replace('```', '').strip().split('\n')
spoken_text = "Today we are learning an important science concept."
manim_code = ""

if lines and lines[0].startswith("# TTS:"):
    spoken_text = lines[0].replace("# TTS:", "").strip()
    manim_code = '\n'.join(lines[1:])
else:
    # Fallback if Groq forgets the formatting
    manim_code = '\n'.join(lines)

with open("scene.py", "w") as f:
    f.write(manim_code)

print(f"Extracted Script: {spoken_text}")

# 4. Generate Voiceover
audio_filename = "audio.mp3"
tts = gTTS(text=spoken_text, lang='en', tld='co.in')
tts.save(audio_filename)

# 5. Render Manim Visuals (1080x1920)
print("Rendering Manim shapes...")
subprocess.run([
    "manim", "scene.py", "ScienceShort", 
    "--resolution", "1080,1920", 
    "-o", "silent_vid.mp4"
], check=True)

# 6. Merge Audio and Video using MoviePy
safe_name = concept_name.replace(' ', '_').replace('?', '').replace(':', '').replace("'", "")
final_filename = f"SSC_Science_{safe_name}.mp4"

# Manim buries the output deep in its media folder, glob finds it dynamically
manim_output_path = glob.glob("media/videos/scene/*/silent_vid.mp4")[0]

print("Stitching audio and visuals together...")
video_clip = VideoFileClip(manim_output_path)
audio_clip = AudioFileClip(audio_filename)

# Ensure audio and video lengths match gracefully
final_clip = video_clip.set_audio(audio_clip)
if audio_clip.duration > video_clip.duration:
    # If AI talked too long, freeze the last frame of the video
    final_clip = final_clip.set_duration(audio_clip.duration)
else:
    # If AI talked too fast, cut the video when the audio stops
    final_clip = final_clip.set_duration(audio_clip.duration)

final_clip.write_videofile(final_filename, fps=24, codec="libx264", audio_codec="aac")

# 7. Update memory for next run
tracker['current_concept_index'] += 1
if tracker['current_concept_index'] >= len(tracker['syllabus'][current_chap_name]):
    tracker['current_concept_index'] = 0
    tracker['current_chapter_index'] += 1
    if tracker['current_chapter_index'] >= len(tracker['chapters']):
        send_telegram_alert("Textbook Finished! All Manim SSC Science videos are done.")

with open('tracker.json', 'w') as file:
    json.dump(tracker, file, indent=2)

print(f"Successfully generated {final_filename}")
