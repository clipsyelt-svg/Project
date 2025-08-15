import os
import tempfile
import subprocess
import datetime
from supabase import create_client
from highlight import find_highlights
from captions import transcribe_and_make_srt
from hooks import make_hook

# ── Config from environment ────────────────────────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]                      # e.g. https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]  # service_role secret
STREAM_URL = os.getenv("STREAM_URL")                           # optional (passed from Actions)
MAX_CLIPS = int(os.getenv("MAX_CLIPS", "6"))                   # optional; default 6

# Storage bucket where MP4s are uploaded
BUCKET = "clips"

# Supabase client (service role bypasses RLS; NEVER expose this key client-side)
sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


# ── Helpers ────────────────────────────────────────────────────────────────────
def run(cmd: str):
    """Run a shell command and stream output."""
    print("RUN:", cmd, flush=True)
    subprocess.check_call(cmd, shell=True)


def download_vod(url: str, out_path: str):
    """
    Download the best MP4 rendition if possible.
    yt-dlp handles YouTube/Twitch/Kick VODs (subject to availability/ToS).
    """
    # Try MP4 first, fall back to best if MP4 not available
    try:
        run(f'yt-dlp -o "{out_path}" -f "mp4/best" "{url}"')
    except subprocess.CalledProcessError:
        run(f'yt-dlp -o "{out_path}" -f "best" "{url}"')


def cut_and_format(src: str, start_s: float, dur_s: float, out_mp4: str):
    """
    Make 9:16 vertical video, center-padded, 1080x1920, 30fps, H.264 + AAC.
    """
    vf = (
        'scale=1080:1920:force_original_aspect_ratio=decrease,'
        'pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p'
    )
    run(
        f'ffmpeg -y -ss {start_s} -i "{src}" -t {dur_s} -vf "{vf}" '
        f'-r 30 -c:v libx264 -preset veryfast -crf 22 -c:a aac -b:a 128k "{out_mp4}"'
    )


def burn_subs(in_mp4: str, srt_path: str, out_mp4: str):
    """
    Burn subtitles with a readable style.
    """
    style = "FontName=Inter,Fontsize=48,MarginV=96,Outline=4"
    run(
        f'ffmpeg -y -i "{in_mp4}" -vf "subtitles={srt_path}:force_style=\'{style}\'" '
        f'-c:a copy "{out_mp4}"'
    )


def upload(path: str, dest_key: str):
    """
    Upload to Supabase Storage (public bucket). Upsert to avoid conflicts.
    """
    with open(path, "rb") as f:
        sb.storage.from_(BUCKET).upload(
            dest_key,
            f,
            {"content-type": "video/mp4", "x-upsert": "true"},
        )
    print("Uploaded:", dest_key, flush=True)


def claim_job():
    """
    Claim the oldest pending job and mark it processing.
    """
    resp = sb.table("jobs").select("*").eq("status", "pending").order("created_at").limit(1).execute()
    if not resp.data:
        return None
    job = resp.data[0]
    sb.table("jobs").update({"status": "processing"}).eq("id", job["id"]).execute()
    return job


def complete_job(job_id, status="done"):
    sb.table("jobs").update(
        {"status": status, "finished_at": str(datetime.datetime.utcnow())}
    ).eq("id", job_id).execute()


# ── Main flow ──────────────────────────────────────────────────────────────────
def main():
    """
    If STREAM_URL is provided (from GitHub Actions inputs), create a one-off job
    for that URL and process it immediately. Otherwise, pop the next pending job.
    """
    global MAX_CLIPS

    # Optional override from Actions input
    if STREAM_URL:
        ins = sb.table("jobs").insert({"url": STREAM_URL, "status": "pending"}).execute()
        job = ins.data[0]
        print("Created on-demand job for:", STREAM_URL, flush=True)
    else:
        job = claim_job()

    if not job:
        print("No pending jobs.", flush=True)
        return

    # Allow MAX_CLIPS override via env
    try:
        mc = int(os.getenv("MAX_CLIPS", str(MAX_CLIPS)))
        MAX_CLIPS = max(1, min(mc, 12))
    except Exception:
        pass

    url = job["url"]
    print(f"Processing: {url}  |  MAX_CLIPS={MAX_CLIPS}", flush=True)

    try:
        with tempfile.TemporaryDirectory() as td:
            vod_path = os.path.join(td, "vod.mp4")
            download_vod(url, vod_path)

            # 1) Detect highlight segments (~60s each)
            segments = find_highlights(vod_path, target_duration=60, max_segments=MAX_CLIPS)
            if not segments:
                segments = [(0, 60)]

            # 2) Produce, caption, and upload each clip
            for i, (start, dur) in enumerate(segments, 1):
                print(f"--> Clip {i}: start={start}s dur={dur}s", flush=True)

                raw = os.path.join(td, f"clip_{i}_raw.mp4")
                cut_and_format(vod_path, start, dur, raw)

                srt = os.path.join(td, f"clip_{i}.srt")
                transcript = transcribe_and_make_srt(raw, srt)

                hook = make_hook(transcript)

                out = os.path.join(td, f"clip_{i}_captioned.mp4")
                burn_subs(raw, srt, out)

                # Storage key: <job_id>/clip_i.mp4
                key = f'{job["id"]}/clip_{i}.mp4'
                upload(out, key)

                # Save metadata row
                sb.table("clips").insert(
                    {
                        "job_id": job["id"],
                        "idx": i,
                        "path": key,
                        "hook": hook,
                    }
                ).execute()
                print(f"Saved metadata for clip {i}", flush=True)

        complete_job(job["id"], "done")
        print("Job complete ✔", flush=True)

    except subprocess.CalledProcessError as e:
        print("Command failed:", e, flush=True)
        complete_job(job["id"], "error")
        raise
    except Exception as e:
        print("Error:", e, flush=True)
        complete_job(job["id"], "error")
        raise


if __name__ == "__main__":
    main()

