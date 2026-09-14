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
BASE_DIR = "Topics" # Sabhi topics is folder ke andar rahenge

def send_telegram(token, message):
    if not token or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message})

async def generate_audio(text, voice, output_filename):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_filename)

def manage_image_limit(folder_path, limit=20):
    """Check karta hai ki 20 se zyada images na hon. Agar hain, to purani delete kar dega."""
    images = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
    if len(images) >= limit:
        # Sort files by modification time (oldest first)
        images.sort(key=os.path.getmtime)
        # Delete oldest files until we make room for the new one (limit - 1)
        files_to_delete = len(images) - limit + 1
        for i in range(files_to_delete):
            try:
                os.remove(images[i])
                print(f"Deleted old image to maintain 20 limit: {images[i]}")
            except Exception as e:
                print(f"Error deleting old image: {e}")

def get_image_from_api(prompt, local_folder):
    """Pehle nayi image API se generate karega, fail hone par randomly local se lega."""
    # Ensure folder exists (e.g., Topics/Animals/Octopus/images)
    os.makedirs(local_folder, exist_ok=True)
    
    # 1. Hamesha pehle nayi image generate karne ka try karega
    url = f"https://ansh-apis.is-dev.org/api/nano?key={API_KEY}&prompt={prompt}"
    try:
        response = requests.get(url, timeout=20).json()
        img_url = response.get("url") or response.get("image") or response.get("image_url")
        
        if img_url:
            img_data = requests.get(img_url).content
            
            # Limit check: 20 se adhik images nahi hone chahiye
            manage_image_limit(local_folder, limit=20)
            
            # Nayi image save karega
            file_path = os.path.join(local_folder, f"{int(datetime.datetime.now().timestamp())}.jpg")
            with open(file_path, 'wb') as f:
                f.write(img_data)
            print(f"Successfully generated and saved new image for {prompt}.")
            return file_path
    except Exception as e:
        print(f"API Failed for '{prompt}': {e}. Switching to random local fallback.")
    
    # 2. Agar API fail ho jaye, to pehle se saved images mein se randomly select karega
    if os.path.exists(local_folder):
        images = [img for img in os.listdir(local_folder) if img.endswith(('.png', '.jpg', '.jpeg'))]
        if images:
            selected_fallback = random.choice(images)
            print(f"Using fallback random image for {prompt}: {selected_fallback}")
            return os.path.join(local_folder, selected_fallback)
            
    return None

def get_valid_facts(topic, category):
    history_file = "history.json"
    with open(history_file, "r") as f:
        try:
            history = json.load(f)
        except:
            history = {}

    facts_file = os.path.join(BASE_DIR, topic, category, "facts.txt")
    with open(facts_file, "r") as f:
        all_facts = [line.strip() for line in f if line.strip()]

    valid_facts = []
    now = datetime.datetime.now()
    for fact in all_facts:
        if fact in history:
            last_used = datetime.datetime.fromisoformat(history[fact])
            if (now - last_used).days < 366:
                continue # Agar 366 days ke andar use hua hai, to dobara use nahi hoga
        valid_facts.append(fact)
    return valid_facts, history

def create_text_clip(text, duration, highlight=False):
    # Hook ke time 1-2 words Golden color mein highlight honge
    words = text.split()
    if highlight and len(words) > 1:
        gold_text = " ".join(words[:2])
        white_text = " ".join(words[2:])
        tc1 = TextClip(gold_text, fontsize=70, color='gold', font="Arial-Bold", method='caption', size=(900, None))
        tc2 = TextClip(white_text, fontsize=60, color='white', font="Arial", method='caption', size=(900, None))
        txt_clip = clips_array([[tc1], [tc2]]).set_position('center').set_duration(duration)
    else:
        txt_clip = TextClip(text, fontsize=60, color='white', font="Arial", method='caption', size=(900, None))
        txt_clip = txt_clip.set_position(('center', 'bottom')).set_duration(duration)
    return txt_clip

async def main():
    try:
        # 1. Randomly Topic select karo
        topics = [d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))]
        if not topics:
            raise Exception("No Topics found in BASE_DIR!")
        topic = random.choice(topics)
        
        # 2. Select kiye gaye Topic ke andar se Random Category select karo (e.g. Octopus)
        topic_path = os.path.join(BASE_DIR, topic)
        categories = [d for d in os.listdir(topic_path) if os.path.isdir(os.path.join(topic_path, d))]
        if not categories:
            raise Exception(f"No categories found inside topic: {topic}")
        category = random.choice(categories)
        
        print(f"Selected Topic: {topic} | Selected Category: {category}")

        # 3. Valid facts filter karo (366 days cooling timer check)
        valid_facts, history = get_valid_facts(topic, category)
        if len(valid_facts) < 2:
            raise Exception(f"Not enough fresh facts for category: {category} in topic {topic}")
        
        selected_facts = random.sample(valid_facts, 2)
        
        # Hook text select karo
        with open("hooks.txt", "r") as f:
            hooks = [line.strip() for line in f if line.strip()]
        hook_text = random.choice(hooks)

        # 4. Voiceover Audios Generate (Male, Female, Male)
        await generate_audio(hook_text, "en-US-GuyNeural", "hook.mp3") 
        await generate_audio(selected_facts[0], "en-US-AriaNeural", "fact1.mp3")
        await generate_audio(selected_facts[1], "en-US-GuyNeural", "fact2.mp3") 
        
        hook_audio = AudioFileClip("hook.mp3")
        fact1_audio = AudioFileClip("fact1.mp3")
        fact2_audio = AudioFileClip("fact2.mp3")

        # 5. Category-specific Images lao (Yahan API call hoti hai)
        img_folder = os.path.join(BASE_DIR, topic, category, "images")
        
        # Image 1 and Image 2 generated or fetched randomly from fallback
        img1_path = get_image_from_api(category, img_folder)
        img2_path = get_image_from_api(category, img_folder)

        if not img1_path or not img2_path:
             raise Exception(f"Images generate nahi ho payin aur local folder '{img_folder}' mein bhi koi image fallback ke liye nahi hai.")

        # 6. Video Clips Banao
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

        # Combine Videos
        final_video = concatenate_videoclips([hook_clip, f1_clip, f2_clip])

        # Add Background Music
        music_files = [f for f in os.listdir("music") if f.endswith(".mp3")]
        if music_files:
            bg_music = AudioFileClip(os.path.join("music", random.choice(music_files)))
            bg_music = bg_music.fx(vfx.loop, duration=final_video.duration).volumex(0.1)
            final_audio = CompositeAudioClip([final_video.audio, bg_music])
            final_video = final_video.set_audio(final_audio)

        # Export Output File
        output_file = "final_short.mp4"
        final_video.write_videofile(output_file, fps=24, codec="libx264", audio_codec="aac")

        # Post to Webhook (Vaibhav's URL)
        with open(output_file, 'rb') as f:
            webhook_res = requests.post(WEBHOOK_URL, files={'file': f})
        
        # 7. Update History & Save
        now_str = datetime.datetime.now().isoformat()
        history[selected_facts[0]] = now_str
        history[selected_facts[1]] = now_str
        with open("history.json", "w") as f:
            json.dump(history, f, indent=4)

        # Success Telegram Notification
        success_msg = f"✅ Video generated successfully!\nTopic: {topic}\nCategory: {category}\nWebhook Status: {webhook_res.status_code}"
        send_telegram(TELEGRAM_BOT_TOKEN_SUCCESS, success_msg)
        print(success_msg)

    except Exception as e:
        error_msg = f"❌ Automation Failed!\nName: Fact Shorts Automation\nError: {str(e)}"
        print(error_msg)
        send_telegram(TELEGRAM_BOT_TOKEN_FAIL, error_msg)

if __name__ == "__main__":
    asyncio.run(main())
