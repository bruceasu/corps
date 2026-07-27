import re
import os
import json
import time
import hashlib
from typing import List, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

# 依赖
# pip install youtube-transcript-api yt-dlp

# =========================
# 🔧 基础工具
# =========================

def extract_video_id(input_str: str) -> str:
    patterns = [
        r"(?:v=)([0-9A-Za-z_-]{11})",
        r"(?:youtu\.be/)([0-9A-Za-z_-]{11})",
        r"(?:shorts/)([0-9A-Za-z_-]{11})",
        r"(?:embed/)([0-9A-Za-z_-]{11})"
    ]
    for p in patterns:
        m = re.search(p, input_str)
        if m:
            return m.group(1)

    if re.match(r"^[0-9A-Za-z_-]{11}$", input_str):
        return input_str

    raise ValueError(f"Invalid input: {input_str}")


# =========================
# 📺 获取播放列表 / 频道视频
# =========================

def fetch_video_ids_from_url(url: str) -> List[str]:
    ydl_opts = {
        "quiet": True,
        "extract_flat": True
    }

    video_ids = []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

        if "entries" in info:
            for entry in info["entries"]:
                if entry and "id" in entry:
                    video_ids.append(entry["id"])
        else:
            if "id" in info:
                video_ids.append(info["id"])

    return video_ids


# =========================
# 🧠 缓存系统
# =========================

CACHE_FILE = "cache.json"

def load_cache() -> Set[str]:
    if not os.path.exists(CACHE_FILE):
        return set()
    with open(CACHE_FILE, "r") as f:
        return set(json.load(f))


def save_cache(cache: Set[str]):
    with open(CACHE_FILE, "w") as f:
        json.dump(list(cache), f)


# =========================
# 📜 获取字幕（带重试）
# =========================

def get_transcript_with_retry(video_id, languages, retries=3):
    for attempt in range(retries):
        try:
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)

            # 人工优先
            for lang in languages:
                try:
                    return transcripts.find_transcript([lang]).fetch()
                except:
                    pass

            # 自动字幕
            for lang in languages:
                try:
                    return transcripts.find_generated_transcript([lang]).fetch()
                except:
                    pass

        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
            else:
                raise e

    return None


# =========================
# 💾 保存 & 日志
# =========================

def save_transcript(video_id, transcript, out_dir="output"):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{video_id}.txt")

    with open(path, "w", encoding="utf-8") as f:
        for item in transcript:
            f.write(f"[{item['start']:.2f}] {item['text']}\n")


def log_failure(video_id, error):
    with open("error.log", "a", encoding="utf-8") as f:
        f.write(f"{video_id}\t{error}\n")


# =========================
# 🚀 单任务
# =========================

def process_video(video_id, languages, cache: Set[str]):
    if video_id in cache:
        print(f"[跳过] {video_id}")
        return "skipped"

    try:
        transcript = get_transcript_with_retry(video_id, languages)

        if transcript:
            save_transcript(video_id, transcript)
            cache.add(video_id)
            print(f"[成功] {video_id}")
            return "success"
        else:
            print(f"[无字幕] {video_id}")
            return "no_sub"

    except Exception as e:
        log_failure(video_id, str(e))
        print(f"[失败] {video_id}")
        return "fail"


# =========================
# ⚡ 并发调度
# =========================

def run_batch(inputs: List[str], languages, max_workers=8):
    cache = load_cache()

    # 收集所有 video_id
    all_video_ids = []

    for item in inputs:
        try:
            if "youtube.com" in item or "youtu.be" in item:
                ids = fetch_video_ids_from_url(item)
                all_video_ids.extend(ids)
            else:
                all_video_ids.append(extract_video_id(item))
        except Exception as e:
            print(f"[解析失败] {item}: {e}")

    # 去重
    all_video_ids = list(set(all_video_ids))

    print(f"总视频数: {len(all_video_ids)}")

    results = {"success": 0, "fail": 0, "skipped": 0, "no_sub": 0}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_video, vid, languages, cache): vid
            for vid in all_video_ids
        }

        for future in as_completed(futures):
            r = future.result()
            if r:
                results[r] += 1

    save_cache(cache)

    print("\n=== 统计 ===")
    print(results)


# =========================
# ▶️ 入口
# =========================

if __name__ == "__main__":
    languages = ['zh-Hans', 'zh', 'en', 'ja']

    inputs = [
        "https://www.youtube.com/watch?v=LA5yHm01S8c", 
        
        # 单视频
        #"https://www.youtube.com/watch?v=dQw4w9WgXcQ",

        # 播放列表
        #"https://www.youtube.com/playlist?list=PLxxxx",

        # 频道
        #"https://www.youtube.com/@channelname/videos"
    ]

    run_batch(inputs, languages, max_workers=10)