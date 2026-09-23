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
success = False
spoken_text = "Today we are learning an important science concept."

# 2. Self-Correction Loop: Keep trying until Manim successfully compiles
for attempt in range(max_retries):
    print(f"\n--- Attempt {attempt + 1} of {max_retries} ---")
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-oss-20b",
            temperature=0.2, 
        )
        raw_response = chat_completion.choices[0].message.content.strip()
        
        lines = raw_response.replace('```python', '').replace('```', '').strip().split('\n')
        manim_code = ""

        if lines and lines[0].startswith("# TTS:"):
            spoken_text = lines[0].replace("# TTS:", "").strip()
            manim_code = '\n'.join(lines[1:])
        else:
            manim_code = '\n'.join(lines)

        with open("scene.py", "w") as f:
            f.write(manim_code)
            
        print(f"Extracted Script: {spoken_text}")

        # Render Manim Visuals
        print("Rendering Manim shapes...")
        subprocess.run([
            "manim", "scene.py", "ScienceShort", 
            "--resolution", "1080,1920", 
            "-o", "silent_vid.mp4"
        ], check=True)
        
        # If no error is thrown, the code was perfect! Break the loop.
        success = True
        break 
        
    except subprocess.CalledProcessError:
        print("Manim crashed! Groq wrote bad geometry code. Retrying with a new script...")
        time.sleep(5)
    except Exception as e:
        print(f"API Error: {e}")
        time.sleep(5)

if not success:
    print("Failed to generate a working Manim script after 3 tries. Will try again next schedule.")
    exit(1)

# 3. Generate Voiceover
audio_filename = "audio.mp3"
tts = gTTS(text=spoken_text, lang='en', tld='co.in')
tts.save(audio_filename)

# 4. Merge Audio and Video using MoviePy
safe_name = concept_name.replace(' ', '_').replace('?', '').replace(':', '').replace("'", "")
final_filename = f"SSC_Science_{safe_name}.mp4"

manim_output_path = glob.glob("media/videos/scene/*/silent_vid.mp4")[0]

print("Stitching audio and visuals together...")
video_clip = VideoFileClip(manim_output_path)
audio_clip = AudioFileClip(audio_filename)

final_clip = video_clip.set_audio(audio_clip)
if audio_clip.duration > video_clip.duration:
    final_clip = final_clip.set_duration(audio_clip.duration)
else:
    final_clip = final_clip.set_duration(audio_clip.duration)

final_clip.write_videofile(final_filename, fps=24, codec="libx264", audio_codec="aac")

# 5. Update memory for tomorrow
tracker['current_concept_index'] += 1
if tracker['current_concept_index'] >= len(tracker['syllabus'][current_chap_name]):
    tracker['current_concept_index'] = 0
    tracker['current_chapter_index'] += 1
    if tracker['current_chapter_index'] >= len(tracker['chapters']):
        send_telegram_alert("Textbook Finished! All Manim SSC Science videos are done.")

with open('tracker.json', 'w') as file:
    json.dump(tracker, file, indent=2)

print(f"Successfully generated {final_filename}")

