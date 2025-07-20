import os
import uuid
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoFileClip, AudioFileClip, ImageClip, concatenate_videoclips
from flask import Flask, request, render_template, send_from_directory, url_for
import geoip2.database
from hashlib import sha256

app = Flask(__name__)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
GENERATED_DIR = os.path.join(STATIC_DIR, 'generated')
os.makedirs(GENERATED_DIR, exist_ok=True)

# files config
INPUT_IMAGE_PATH = os.path.join(STATIC_DIR, "assets/BattleOfWits-Clack.png")
FONT_PATH = os.path.join(STATIC_DIR, "assets/Spongeboy.otf")
AUDIO_FILE = os.path.join(STATIC_DIR, "assets/BattleOfWits-audio.mp3")
VIDEO_FILE = os.path.join(STATIC_DIR, "assets/BattleOfWits-part.mp4")
GEOIP_DB_PATH = os.path.join(STATIC_DIR, 'assets/GeoLite2-City.mmdb') # get it yourself from https://maxmind.com

# text config
FONT_SIZE = 120
TEXT_COLOR = "#B63825"
OUTLINE_COLOR = "black"
OUTLINE_WIDTH = 5
SHADOW_COLOR = "black"
SHADOW_OFFSET = (-10, 15)
ROTATION_ANGLE = -5

def get_location(ip):
    try:
        with geoip2.database.Reader(GEOIP_DB_PATH) as reader:
            response = reader.city(ip)
            city = response.city.name or "Unknown"
            country = response.country.name or "Unknown"
            return city, country
    except Exception as e:
        print(f"GeoIP lookup failed: {e}")
        return "Unknown", "Unknown"

def gen_image(img_path, ip, city, country):
    try:
        img = Image.open(img_path).convert("RGBA")
        width, height = img.size

        ip_text = ip
        loc_text = f"{city}, {country}"

        max_w = int(width * 0.85)

        font_size = FONT_SIZE
        font = ImageFont.truetype(FONT_PATH, font_size)
        dummy_draw = ImageDraw.Draw(img)
        bbox = dummy_draw.textbbox((0, 0), ip_text, font=font)
        text_w = bbox[2] - bbox[0]

        while text_w > max_w and font_size > 10:
            font_size -= 2
            font = ImageFont.truetype(FONT_PATH, font_size)
            bbox = dummy_draw.textbbox((0, 0), ip_text, font=font)
            text_w = bbox[2] - bbox[0]

        loc_size = int(font_size * 0.6)
        loc_font = ImageFont.truetype(FONT_PATH, loc_size)
        loc_bbox = dummy_draw.textbbox((0, 0), loc_text, font=loc_font)
        loc_w = loc_bbox[2] - loc_bbox[0]

        while loc_w > max_w and loc_size > 8:
            loc_size -= 1
            loc_font = ImageFont.truetype(FONT_PATH, loc_size)
            loc_bbox = dummy_draw.textbbox((0, 0), loc_text, font=loc_font)
            loc_w = loc_bbox[2] - loc_bbox[0]

        text_h = bbox[3] - bbox[1]
        loc_h = loc_bbox[3] - loc_bbox[1]

        line_sp = int(font_size * 0.2)
        h_total = text_h + line_sp + loc_h

        max_text_w = max(text_w, loc_w)

        mx = OUTLINE_WIDTH + abs(SHADOW_OFFSET[0]) + font_size // 2
        my = OUTLINE_WIDTH + abs(SHADOW_OFFSET[1]) + font_size // 2

        text_img_s = (max_text_w + 2 * mx, h_total + 2 * my)
        text_img = Image.new("RGBA", text_img_s, (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_img)

        main_pos = ((text_img_s[0] - text_w) // 2, my)
        main_shadow_pos = (main_pos[0] + SHADOW_OFFSET[0], main_pos[1] + SHADOW_OFFSET[1])

        loc_pos = ((text_img_s[0] - loc_w) // 2, my + text_h + line_sp)
        loc_shadow_pos = (loc_pos[0] + SHADOW_OFFSET[0], loc_pos[1] + SHADOW_OFFSET[1])

        # shadows
        draw.text(main_shadow_pos, ip_text, font=font, fill=SHADOW_COLOR)
        draw.text(loc_shadow_pos, loc_text, font=loc_font, fill=SHADOW_COLOR)

        # outline for main text
        for x in range(-OUTLINE_WIDTH, OUTLINE_WIDTH + 1):
            for y in range(-OUTLINE_WIDTH, OUTLINE_WIDTH + 1):
                if x * x + y * y <= OUTLINE_WIDTH * OUTLINE_WIDTH:
                    outline_pos = (main_pos[0] + x, main_pos[1] + y)
                    draw.text(outline_pos, ip_text, font=font, fill=OUTLINE_COLOR)

        # outline for location text
        for x in range(-OUTLINE_WIDTH, OUTLINE_WIDTH + 1):
            for y in range(-OUTLINE_WIDTH, OUTLINE_WIDTH + 1):
                if x * x + y * y <= OUTLINE_WIDTH * OUTLINE_WIDTH:
                    outline_pos = (loc_pos[0] + x, loc_pos[1] + y)
                    draw.text(outline_pos, loc_text, font=loc_font, fill=OUTLINE_COLOR)

        # main text
        draw.text(main_pos, ip_text, font=font, fill=TEXT_COLOR)
        draw.text(loc_pos, loc_text, font=loc_font, fill=TEXT_COLOR)

        # rotation
        rotated_text_img = text_img.rotate(ROTATION_ANGLE, expand=True)
        paste_x = (width - rotated_text_img.width) // 2
        paste_y = (height - rotated_text_img.height) // 2
        img.alpha_composite(rotated_text_img, (paste_x, paste_y))

        return img
    except Exception as e:
        print(f"error generating image: {e}")
        return None
    except Exception as e:
        print(f"error generating image: {e}")
        return None

def gen_video(gen_image,output):
  try:
    img_arr = np.array(gen_image)
    output_path = os.path.join(GENERATED_DIR,output)

    with VideoFileClip(VIDEO_FILE) as clip, AudioFileClip(AUDIO_FILE) as audio, ImageClip(img_arr) as img:
      final_duration = audio.duration
      img_duration = final_duration - clip.duration
      img_clip = img.with_duration(img_duration).with_fps(clip.fps).resized(clip.size)
      final_video = concatenate_videoclips([clip,img_clip])
      final_w_audio = final_video.with_audio(audio)
      final_w_audio = final_w_audio.with_duration(final_duration)
      final_w_audio.write_videofile(output_path,codec="libx264",audio_codec="aac",fps=clip.fps,preset="ultrafast")
      return output
  except Exception as e:
    print(f"error generating video: {e}")
    return None

@app.route("/wits.mp4", methods=["GET","POST"])
def index():
  #client_ip = request.remote_addr                # UNCOMMENT THIS IF YOU'RE NOT USING CLOUDFLARE
  client_ip = request.headers['Cf-Connecting-Ip'] # COMMENT THIS IF YOU'RE NOT USING CLOUDFLARE
  cached_filename = f"video_{sha256(client_ip.encode('utf-8')).hexdigest()}.mp4"
  cached_path = os.path.join(GENERATED_DIR, cached_filename)
  if os.path.exists(cached_path):
    return send_from_directory(GENERATED_DIR, cached_filename)
  city, country = get_location(client_ip)
  generated_image = gen_image(INPUT_IMAGE_PATH, client_ip, city, country)
  if generated_image:
    result_filename = gen_video(generated_image, cached_filename)
    if result_filename:
      return send_from_directory(GENERATED_DIR, result_filename)
  return "Please try again later.", 500

# debug stuff, you can remove these
@app.route("/headers")
def debug_headers():
  return {headers: dict(request.headers)}

# debug stuff, it can be useful sometimes, plus it
# would be pretty hard to bruteforce the filenames.
@app.route('/generated/<filename>')
def generated_files(filename):
    return send_from_directory(GENERATED_DIR, filename)

@app.errorhandler(404)
def notfound(e):
    return "404", 404

if __name__ == '__main__':
    app.run(debug=True) # we're running this in a docker instance, it doesn't *really* matter, does it?
