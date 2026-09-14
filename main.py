import os
import json
import random
import requests
import datetime
import asyncio
import edge_tts
from moviepy.editor import *

# Configuration
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
TELEGRAM_BOT_TOKEN_SUCCESS = os.environ.get("TELEGRAM_BOT_TOKEN_SUCCESS")
TELEGRAM_BOT_TOKEN_FAIL = os.environ.get("TELEGRAM_BOT_TOKEN_FAIL")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
API_KEY = "ansh"

def send_telegram(token, message):
    if not token or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})

async def generate_audio(text, voice, output_filename):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_filename)

def get_image_from_api(topic, local_folder):
    url = f"https://ansh-apis.is-dev.org/api/nano?key={API_KEY}&prompt={topic}"
    try:
        response = requests.get(url, timeout=15).json()
        # Find the image URL from common JSON keys
        img_url = response.get("url") or response.get("image") or response.get("image_url")
        if img_url:
            img_data = requests.get(img_url).content
            file_path = os.path.join(local_folder, f"{int(datetime.datetime.now().timestamp())}.jpg")
            with open(file_path, 'wb') as f:
                f.write(img_data)
            return file_path
    except Exception as e:
        print(f"API Failed: {e}")
    
    # Fallback to local image
    if os.path.exists(local_folder):
        images = [img for img in os.listdir(local_folder) if img.endswith(('.png', '.jpg', '.jpeg'))]
        if images:
            return os.path.join(local_folder, random.choice(images))
    return None

def get_valid_facts(topic):
    history_file = "history.json"
    with open(history_file, "r") as f:
        try:
            history = json.load(f)
        except:
            history = {}

    facts_file = f"facts/{topic}/facts.txt"
    with open(facts_file, "r") as f:
        all_facts = [line.strip() for line in f if line.strip()]

    valid_facts = []
    now = datetime.datetime.now()
    for fact in all_facts:
        if fact in history:
            last_used = datetime.datetime.fromisoformat(history[fact])
            if (now - last_used).days < 366:
                continue # Skip if used within 366 days
        valid_facts.append(fact)
    return valid_facts, history

def create_text_clip(text, duration, highlight=False):
    # Highlight 1-2 words in gold, rest in white
    words = text.split()
    if highlight and len(words) > 1:
        gold_text = " ".join(words[:2])
        white_text = " ".join(words[2:])
        # Note: MoviePy complex inline coloring is tricky. We stack clips vertically.
        tc1 = TextClip(gold_text, fontsize=70, color='gold', font="Arial-Bold", method='caption', size=(900, None))
        tc2 = TextClip(white_text, fontsize=60, color='white', font="Arial", method='caption', size=(900, None))
        txt_clip = clips_array([[tc1], [tc2]]).set_position('center').set_duration(duration)
    else:
        txt_clip = TextClip(text, fontsize=60, color='white', font="Arial", method='caption', size=(900, None))
        txt_clip = txt_clip.set_position(('center', 'bottom')).set_duration(duration)
    return txt_clip

async def main():
    try:
        topics = [d for d in os.listdir("facts") if os.path.isdir(os.path.join("facts", d))]
        topic = random.choice(topics)
        
        valid_facts, history = get_valid_facts(topic)
        if len(valid_facts) < 2:
            raise Exception(f"Not enough fresh facts for topic: {topic}")
        
        selected_facts = random.sample(valid_facts, 2)
        
        with open("hooks.txt", "r") as f:
            hooks = [line.strip() for line in f if line.strip()]
        hook_text = random.choice(hooks)

        # 1. Generate Audios
        await generate_audio(hook_text, "en-US-GuyNeural", "hook.mp3") # Male
        await generate_audio(selected_facts[0], "en-US-AriaNeural", "fact1.mp3") # Female
        await generate_audio(selected_facts[1], "en-US-GuyNeural", "fact2.mp3") # Male
        
        hook_audio = AudioFileClip("hook.mp3")
        fact1_audio = AudioFileClip("fact1.mp3")
        fact2_audio = AudioFileClip("fact2.mp3")

        # 2. Get Images
        img_folder = f"facts/{topic}/images"
        os.makedirs(img_folder, exist_ok=True)
        img1_path = get_image_from_api(topic, img_folder)
        img2_path = get_image_from_api(topic, img_folder)

        # 3. Build Clips
        # Hook Clip
        hook_txt = create_text_clip(hook_text, hook_audio.duration, highlight=True).set_position('center')
        hook_clip = ColorClip(size=(1080, 1920), color=(0,0,0), duration=hook_audio.duration)
        hook_clip = CompositeVideoClip([hook_clip, hook_txt]).set_audio(hook_audio)

        # Fact 1 Clip
        f1_bg = ColorClip(size=(1080, 1920), color=(0,0,0), duration=fact1_audio.duration)
        f1_img = ImageClip(img1_path).resize(width=900).set_position('center').set_duration(fact1_audio.duration)
        f1_txt = create_text_clip(selected_facts[0], fact1_audio.duration)
        f1_clip = CompositeVideoClip([f1_bg, f1_img, f1_txt]).set_audio(fact1_audio)

        # Fact 2 Clip
        f2_bg = ColorClip(size=(1080, 1920), color=(0,0,0), duration=fact2_audio.duration)
        f2_img = ImageClip(img2_path).resize(width=900).set_position('center').set_duration(fact2_audio.duration)
        f2_txt = create_text_clip(selected_facts[1], fact2_audio.duration)
        f2_clip = CompositeVideoClip([f2_bg, f2_img, f2_txt]).set_audio(fact2_audio)

        # Combine
        final_video = concatenate_videoclips([hook_clip, f1_clip, f2_clip])

        # Add Background Music
        music_files = [f for f in os.listdir("music") if f.endswith(".mp3")]
        if music_files:
            bg_music = AudioFileClip(os.path.join("music", random.choice(music_files)))
            bg_music = bg_music.fx(vfx.loop, duration=final_video.duration).volumex(0.1)
            final_audio = CompositeAudioClip([final_video.audio, bg_music])
            final_video = final_video.set_audio(final_audio)

        output_file = "final_short.mp4"
        final_video.write_videofile(output_file, fps=24, codec="libx264", audio_codec="aac")

        # Post to Webhook
        with open(output_file, 'rb') as f:
            webhook_res = requests.post(WEBHOOK_URL, files={'file': f})
        
        # Update History & Save
        now_str = datetime.datetime.now().isoformat()
        history[selected_facts[0]] = now_str
        history[selected_facts[1]] = now_str
        with open("history.json", "w") as f:
            json.dump(history, f, indent=4)

        # Success Telegram Notification
        send_telegram(TELEGRAM_BOT_TOKEN_SUCCESS, f"✅ Video generated and posted successfully!\nWebhook Status: {webhook_res.status_code}")

    except Exception as e:
        error_msg = f"❌ Automation Failed!\nName: Fact Shorts Automation\nError: {str(e)}"
        print(error_msg)
        send_telegram(TELEGRAM_BOT_TOKEN_FAIL, error_msg)

if __name__ == "__main__":
    asyncio.run(main())
