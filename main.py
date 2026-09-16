import os
import json
import random
import requests
import datetime
import asyncio
import edge_tts
import re
from moviepy.editor import *

# Configuration
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
TELEGRAM_TOKEN_SUCCESS = os.environ.get("TELEGRAM_BOT_TOKEN_SUCCESS")
TELEGRAM_TOKEN_FAIL = os.environ.get("TELEGRAM_BOT_TOKEN_FAIL")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
API_KEY = "ansh"
BASE_DIR = "Topics" 

# File Upload Servers (20+ Options)
UPLOAD_SERVERS = [
    {"url": "https://catbox.moe/user/api.php", "data": {"reqtype": "fileupload"}, "file_key": "fileToUpload"},
    {"url": "https://litterbox.catbox.moe/resources/internals/api.php", "data": {"reqtype": "fileupload", "time": "24h"}, "file_key": "fileToUpload"},
    {"url": "https://uguu.se/upload.php", "data": {}, "file_key": "files[]"},
    {"url": "https://0x0.st", "data": {}, "file_key": "file"},
    {"url": "https://api.anonfiles.com/upload", "data": {}, "file_key": "file"},
    {"url": "https://file.io", "data": {}, "file_key": "file"},
    {"url": "https://bashupload.com/", "data": {}, "file_key": "file"},
    {"url": "https://store1.gofile.io/uploadFile", "data": {}, "file_key": "file"},
    {"url": "https://temp.sh/upload", "data": {}, "file_key": "file"},
    {"url": "https://api.bayfiles.com/upload", "data": {}, "file_key": "file"},
    {"url": "https://up.labstack.com/api/v1/links", "data": {}, "file_key": "file"},
    {"url": "https://transfer.sh/", "data": {}, "file_key": "file"},
    {"url": "https://v.gd/create.php", "data": {"format": "simple"}, "file_key": "url"}, 
    {"url": "https://api.filemail.com/api/file/upload", "data": {}, "file_key": "file"},
    {"url": "https://pomf.lain.la/upload.php", "data": {}, "file_key": "files[]"},
    {"url": "https://suki.moe/api/upload", "data": {}, "file_key": "file"},
    {"url": "https://api.zippyshare.com/upload", "data": {}, "file_key": "file"},
    {"url": "https://kiwi6.com/upload", "data": {}, "file_key": "file"},
    {"url": "https://dailyuploads.net/api/upload", "data": {}, "file_key": "file"},
    {"url": "https://api.letsupload.cc/upload", "data": {}, "file_key": "file"}
]

def send_telegram(token, message):
    if not token or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})
    except Exception as e:
        print(f"Telegram failed: {e}")

async def generate_audio_and_subs(text, voice, audio_filename, vtt_filename):
    communicate = edge_tts.Communicate(text, voice)
    subs = []
    
    with open(audio_filename, "wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                subs.append((chunk["offset"], chunk["duration"], chunk["text"]))
                
    # Manually generating VTT file
    with open(vtt_filename, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for offset, duration, word in subs:
            start_sec = offset / 10000000.0
            end_sec = (offset + duration) / 10000000.0
            
            def format_time(seconds):
                h = int(seconds // 3600)
                m = int((seconds % 3600) // 60)
                s = int(seconds % 60)
                ms = int(round((seconds - int(seconds)) * 1000))
                return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
                
            f.write(f"{format_time(start_sec)} --> {format_time(end_sec)}\n{word}\n\n")

def parse_vtt_to_clips(vtt_file):
    clips = []
    with open(vtt_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    blocks = re.findall(r'(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\n(.*?)(?=\n\n|\Z)', content, re.DOTALL)
    
    for start_str, end_str, text in blocks:
        def time_to_sec(t_str):
            h, m, s = t_str.split(':')
            s, ms = s.split('.')
            return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0
            
        start_time = time_to_sec(start_str)
        end_time = time_to_sec(end_str)
        
        txt_clip = TextClip(text.strip().replace('\n', ' '), fontsize=75, color='gold', font="Arial-Bold", method='caption', size=(900, None))
        txt_clip = txt_clip.set_start(start_time).set_end(end_time).set_position('center')
        clips.append(txt_clip)
        
    return clips

def manage_image_limit(folder_path, limit=10):
    images = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
    if len(images) >= limit:
        images.sort(key=os.path.getmtime)
        for i in range(len(images) - limit + 1):
            try: os.remove(images[i])
            except: pass

def get_image_from_api(prompt, local_folder):
    os.makedirs(local_folder, exist_ok=True)
    url = f"https://ansh-apis.is-dev.org/api/nano?key={API_KEY}&prompt={prompt}"
    
    try:
        response = requests.get(url, timeout=20).json()
        img_url = response.get("url") or response.get("image") or response.get("image_url")
        if img_url:
            img_data = requests.get(img_url).content
            manage_image_limit(local_folder, limit=10) 
            
            file_path = os.path.join(local_folder, f"{int(datetime.datetime.now().timestamp())}.jpg")
            with open(file_path, 'wb') as f:
                f.write(img_data)
            print(f"API se image download aur save ho gayi: {file_path}")
            return file_path
    except Exception as e:
        print(f"API Image generation fail hua: {e}. Searching for local fallback...")
    
    if os.path.exists(local_folder):
        images = [img for img in os.listdir(local_folder) if img.endswith(('.png', '.jpg', '.jpeg'))]
        if images: 
            fallback = random.choice(images)
            print(f"Local fallback image use kar raha hu: {fallback}")
            return os.path.join(local_folder, fallback)
            
    return None

def get_valid_facts(topic, category, history):
    facts_file = os.path.join(BASE_DIR, topic, category, "facts.txt")
    if not os.path.exists(facts_file): return []
    with open(facts_file, "r") as f:
        all_facts = [line.strip() for line in f if line.strip()]
        
    valid_facts = []
    now = datetime.datetime.now()
    for fact in all_facts:
        if fact in history:
            last_used = datetime.datetime.fromisoformat(history[fact])
            if (now - last_used).days < 366:
                continue
        valid_facts.append(fact)
    return valid_facts

def upload_video(file_path):
    for server in UPLOAD_SERVERS:
        try:
            with open(file_path, 'rb') as f:
                files = {server["file_key"]: f}
                res = requests.post(server["url"], data=server.get("data", {}), files=files, timeout=30)
                if res.status_code == 200:
                    try:
                        return res.json().get('data', {}).get('file', {}).get('url', res.text.strip())
                    except:
                        return res.text.strip()
        except:
            continue
    raise Exception("Failed to upload video to all servers.")

async def main():
    try:
        history_file = "history.json"
        with open(history_file, "r") as f:
            try: history = json.load(f)
            except: history = {}

        if not os.path.exists(BASE_DIR):
            raise Exception(f"Main '{BASE_DIR}' folder hi nahi mila!")

        topics = [d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))]
        if not topics: raise Exception("No Topics found in Base folder!")
        
        selected_data = []
        available_categories = []
        
        for t in topics:
            t_path = os.path.join(BASE_DIR, t)
            for c in os.listdir(t_path):
                c_path = os.path.join(t_path, c)
                if os.path.isdir(c_path):
                    v_facts = get_valid_facts(t, c, history)
                    if len(v_facts) > 0: 
                        available_categories.append({"topic": t, "category": c, "fresh_facts": v_facts})
                        
        if not available_categories:
            raise Exception("Koi bhi valid category folder nahi mila jismein fresh facts hon!")
            
        random.shuffle(available_categories)
        
        for item in available_categories:
            if len(selected_data) == 3: break
            
            v_facts = [f for f in item["fresh_facts"] if f not in [sd["fact"] for sd in selected_data]]
            if v_facts:
                chosen_fact = random.choice(v_facts)
                selected_data.append({
                    "topic": item["topic"],
                    "category": item["category"],
                    "fact": chosen_fact
                })
                history[chosen_fact] = datetime.datetime.now().isoformat()

        if len(selected_data) < 3:
            raise Exception("Kam se kam 3 facts ki zarurat hai (alag alag ya same topic/category se), par utne fresh facts bache nahi hain.")

        if not os.path.exists("hooks.txt"):
            raise Exception("hooks.txt file nahi mili!")
            
        with open("hooks.txt", "r") as f:
            hooks = [line.strip() for line in f if line.strip()]
        hook_text = random.choice(hooks)

        await generate_audio_and_subs(hook_text, "en-US-GuyNeural", "hook.mp3", "hook.vtt")
        
        video_segments = []
        
        hook_audio = AudioFileClip("hook.mp3")
        hook_bg = ColorClip(size=(1080, 1920), color=(0,0,0), duration=hook_audio.duration)
        hook_subs = parse_vtt_to_clips("hook.vtt")
        hook_clip = CompositeVideoClip([hook_bg] + hook_subs).set_audio(hook_audio)
        video_segments.append(hook_clip)

        voices = ["en-US-AriaNeural", "en-US-GuyNeural", "en-US-AriaNeural"]
        for i, data in enumerate(selected_data):
            audio_f = f"fact{i}.mp3"
            vtt_f = f"fact{i}.vtt"
            await generate_audio_and_subs(data["fact"], voices[i], audio_f, vtt_f)
            
            f_audio = AudioFileClip(audio_f)
            
            img_folder = os.path.join(BASE_DIR, data["topic"], data["category"], "images")
            img_path = get_image_from_api(data["category"], img_folder)
            
            if not img_path:
                raise Exception(f"Image nahi mili {data['category']} ke liye!")
                
            f_bg = ColorClip(size=(1080, 1920), color=(0,0,0), duration=f_audio.duration)
            f_img = ImageClip(img_path).resize(width=900).set_position('center').set_duration(f_audio.duration)
            
            f_subs = parse_vtt_to_clips(vtt_f)
            f_clip = CompositeVideoClip([f_bg, f_img] + f_subs).set_audio(f_audio)
            video_segments.append(f_clip)

        final_video = concatenate_videoclips(video_segments)

        if os.path.exists("music"):
            music_files = [f for f in os.listdir("music") if f.endswith(".mp3")]
            if music_files:
                bg_music = AudioFileClip(os.path.join("music", random.choice(music_files)))
                bg_music = bg_music.fx(vfx.loop, duration=final_video.duration).volumex(0.1)
                final_audio = CompositeAudioClip([final_video.audio, bg_music])
                final_video = final_video.set_audio(final_audio)

        output_file = "final_short.mp4"
        final_video.write_videofile(output_file, fps=24, codec="libx264", audio_codec="aac")

        video_url = upload_video(output_file)

        if WEBHOOK_URL:
            requests.post(WEBHOOK_URL, json={"url": video_url})
        
        with open("history.json", "w") as f:
            json.dump(history, f, indent=4)

        success_msg = f"✅ Social media name: The interesting Facts\nPost link URL: {video_url}"
        send_telegram(TELEGRAM_TOKEN_SUCCESS, success_msg)
        print("Success! Video created and uploaded.")

    except Exception as e:
        error_msg = f"❌ Automation Failed!\nAutomation name: Fact Shorts\nSocial media name: The interesting Facts\nError: {str(e)}"
        print(f"Error occurred: {e}")
        send_telegram(TELEGRAM_TOKEN_FAIL, error_msg)

if __name__ == "__main__":
    asyncio.run(main())
