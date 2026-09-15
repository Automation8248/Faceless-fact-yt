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
TELEGRAM_TOKEN_SUCCESS = os.environ.get("TELEGRAM_TOKEN_SUCCESS")
TELEGRAM_TOKEN_FAIL = os.environ.get("TELEGRAM_TOKEN_FAIL")
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
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})

async def generate_audio_and_subs(text, voice, audio_filename, vtt_filename):
    communicate = edge_tts.Communicate(text, voice)
    submaker = edge_tts.SubMaker()
    with open(audio_filename, "wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.create_sub((chunk["offset"], chunk["duration"]), chunk["text"])
    with open(vtt_filename, "w", encoding="utf-8") as file:
        file.write(submaker.generate_subs())

def parse_vtt_to_clips(vtt_file, video_size=(1080, 1920)):
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
            return file_path
    except:
        pass
    
    if os.path.exists(local_folder):
        images = [img for img in os.listdir(local_folder) if img.endswith(('.png', '.jpg', '.jpeg'))]
        if images: return os.path.join(local_folder, random.choice(images))
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
    raise Exception("Failed to upload video to all 20+ servers.")

async def main():
    try:
        history_file = "history.json"
        with open(history_file, "r") as f:
            try: history = json.load(f)
            except: history = {}

        # Scan for valid topics and categories (Skipping empty ones)
        if not os.path.exists(BASE_DIR):
            raise Exception(f"Main directory '{BASE_DIR}' not found!")
            
        topics = [d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))]
        
        all_valid_facts = []
        for t in topics:
            t_path = os.path.join(BASE_DIR, t)
            categories = [d for d in os.listdir(t_path) if os.path.isdir(os.path.join(t_path, d))]
            for c in categories:
                v_facts = get_valid_facts(t, c, history)
                # Only add facts if they exist, inherently ignoring empty folders
                for f in v_facts:
                    all_valid_facts.append({
                        "topic": t,
                        "category": c,
                        "fact": f
                    })

        if len(all_valid_facts) < 3:
            raise Exception("Not enough valid facts found across folders. Needs at least 3 fresh facts.")

        # Randomly select exactly 3 distinct facts from the entire valid pool
        selected_data = random.sample(all_valid_facts, 3)
        
        # Add to history to ensure timer starts
        for data in selected_data:
            history[data["fact"]] = datetime.datetime.now().isoformat()

        # Hook setup
        with open("hooks.txt", "r") as f:
            hooks = [line.strip() for line in f if line.strip()]
        hook_text = random.choice(hooks)

        # Generate Audio and VTT Subs
        await generate_audio_and_subs(hook_text, "en-US-GuyNeural", "hook.mp3", "hook.vtt")
        
        video_segments = []
        
        # Build Hook Clip with Synced Subtitles
        hook_audio = AudioFileClip("hook.mp3")
        hook_bg = ColorClip(size=(1080, 1920), color=(0,0,0), duration=hook_audio.duration)
        hook_subs = parse_vtt_to_clips("hook.vtt")
        hook_clip = CompositeVideoClip([hook_bg] + hook_subs).set_audio(hook_audio)
        video_segments.append(hook_clip)

        # Build Fact Clips with Alternating Voices
        voices = ["en-US-AriaNeural", "en-US-GuyNeural", "en-US-AriaNeural"]
        for i, data in enumerate(selected_data):
            audio_f = f"fact{i}.mp3"
            vtt_f = f"fact{i}.vtt"
            await generate_audio_and_subs(data["fact"], voices[i], audio_f, vtt_f)
            
            f_audio = AudioFileClip(audio_f)
            img_folder = os.path.join(BASE_DIR, data["topic"], data["category"], "images")
            img_path = get_image_from_api(data["category"], img_folder)
            
            f_bg = ColorClip(size=(1080, 1920), color=(0,0,0), duration=f_audio.duration)
            f_img = ImageClip(img_path).resize(width=900).set_position('center').set_duration(f_audio.duration)
            
            f_subs = parse_vtt_to_clips(vtt_f)
            f_clip = CompositeVideoClip([f_bg, f_img] + f_subs).set_audio(f_audio)
            video_segments.append(f_clip)

        # Combine
        final_video = concatenate_videoclips(video_segments)

        # Add Background Music
        music_files = [f for f in os.listdir("music") if f.endswith(".mp3")]
        if music_files:
            bg_music = AudioFileClip(os.path.join("music", random.choice(music_files)))
            bg_music = bg_music.fx(vfx.loop, duration=final_video.duration).volumex(0.1)
            final_audio = CompositeAudioClip([final_video.audio, bg_music])
            final_video = final_video.set_audio(final_audio)

        output_file = "final_short.mp4"
        final_video.write_videofile(output_file, fps=24, codec="libx264", audio_codec="aac")

        # Upload Video
        video_url = upload_video(output_file)

        # Send Webhook
        requests.post(WEBHOOK_URL, json={"url": video_url})
        
        # Save History
        with open("history.json", "w") as f:
            json.dump(history, f, indent=4)

        # Success Message
        success_msg = f"✅ Social media name: The interesting Facts\nPost link URL: {video_url}"
        send_telegram(TELEGRAM_TOKEN_SUCCESS, success_msg)

    except Exception as e:
        error_msg = f"❌ Automation Failed!\nAutomation name: Fact Shorts\nSocial media name: The interesting Facts\nError: {str(e)}"
        send_telegram(TELEGRAM_TOKEN_FAIL, error_msg)

if __name__ == "__main__":
    asyncio.run(main())
