import os, tempfile, subprocess, uuid, datetime, json
from supabase import create_client
from highlight import find_highlights
from captions import transcribe_and_make_srt
from hooks import make_hook

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

BUCKET = "clips"
MAX_CLIPS = 6  # keep under GitHub runner time

def run(cmd):
    print("RUN:", cmd)
    subprocess.check_call(cmd, shell=True)

def download_vod(url, out_path):
    # best mp4 if possible
    run(f'yt-dlp -o "{out_path}" -f "mp4/best" "{url}"')

def cut_and_format(src, start_s, dur_s, out_mp4):
    # 9:16 vertical safe scale/pad, 30fps, reasonable bitrate
    vf = 'scale=1080:1920:force_original_aspect_ratio=decrease,' \
         'pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p'
    run(f'ffmpeg -y -ss {start_s} -i "{src}" -t {dur_s} -vf "{vf}" -r 30 -c:v libx264 -preset veryfast -crf 22 -c:a aac -b:a 128k "{out_mp4}"')

def burn_subs(in_mp4, srt_path, out_mp4):
    # If ASS style present, map via subtitles filter (ffmpeg will merge .srt into style)
    run(f'ffmpeg -y -i "{in_mp4}" -vf "subtitles={srt_path}:force_style=\'FontName=Inter,Fontsize=48,MarginV=96,Outline=4\'" -c:a copy "{out_mp4}"')

def upload(path, dest_key):
    with open(path, "rb") as f:
        sb.storage.from_(BUCKET).upload(dest_key, f, {"content-type":"video/mp4"})

def claim_job():
    resp = sb.table("jobs").select("*").eq("status","pending").order("created_at").limit(1).execute()
    if not resp.data:
        return None
    job = resp.data[0]
    sb.table("jobs").update({"status":"processing"}).eq("id", job["id"]).execute()
    return job

def complete_job(job_id, status="done"):
    sb.table("jobs").update({"status":status, "finished_at":str(datetime.datetime.utcnow())}).eq("id", job_id).execute()

def main():
    job = claim_job()
    if not job:
        print("No pending jobs.")
        return
    url = job["url"]
    print("Processing:", url)

    try:
        with tempfile.TemporaryDirectory() as td:
            vod = os.path.join(td, "vod.mp4")
            download_vod(url, vod)

            segments = find_highlights(vod, target_duration=60, max_segments=MAX_CLIPS)
            if not segments:
                segments = [(0, 60)]

            for i, (start, dur) in enumerate(segments, 1):
                raw = os.path.join(td, f"c{i}_raw.mp4")
                cut_and_format(vod, start, dur, raw)

                srt = os.path.join(td, f"c{i}.srt")
                transcript = transcribe_and_make_srt(raw, srt)

                hook = make_hook(transcript)

                out = os.path.join(td, f"c{i}_cap.mp4")
                burn_subs(raw, srt, out)

                key = f'{job["id"]}/clip_{i}.mp4'
                upload(out, key)

                sb.table("clips").insert({
                    "job_id": job["id"],
                    "idx": i,
                    "path": key,
                    "hook": hook
                }).execute()

        complete_job(job["id"], "done")
    except Exception as e:
        print("Error:", e)
        complete_job(job["id"], "error")

if __name__ == "__main__":
    main()
