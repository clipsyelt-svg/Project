import subprocess, json, numpy as np

def _get_audio_rms(path):
    # Extract mono wav via ffmpeg pipe, compute frame-wise RMS
    cmd = [
        "ffmpeg", "-i", path, "-f", "wav", "-ac", "1", "-ar", "16000", "pipe:1"
    ]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    import wave, io
    raw = p.stdout.read()
    wf = wave.open(io.BytesIO(raw))
    frames = wf.readframes(wf.getnframes())
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    wf.close()

    win = 16000 // 4  # 0.25s window
    rms = np.sqrt(np.convolve(audio**2, np.ones(win)/win, mode="valid"))
    hop = 0.25
    times = np.arange(len(rms)) * (1/16000)
    return times[:len(rms):int(16000*hop)], rms[::int(16000*hop)]

def _peak_indices(times, rms, min_gap_s=70.0):
    # Normalize, pick top peaks, enforce spacing
    if len(rms) == 0: return []
    r = (rms - rms.min()) / (rms.max() - rms.min() + 1e-6)
    order = np.argsort(-r)
    chosen = []
    for idx in order:
        t = times[idx]
        if all(abs(t - times[c]) >= min_gap_s for c in chosen):
            chosen.append(idx)
        if len(chosen) >= 12: break
    chosen.sort()
    return chosen

def find_highlights(path, target_duration=60, max_segments=8):
    times, rms = _get_audio_rms(path)
    if len(times) == 0:
        return [(0, target_duration)]
    peaks = _peak_indices(times, rms)
    segs = []
    for i in peaks[:max_segments]:
        center = times[i]
        start = max(0.0, center - target_duration/2)
        segs.append( (round(start,2), target_duration) )
    # Deduplicate overlaps (simple)
    cleaned = []
    last_end = -1
    for s,d in sorted(segs):
        if s >= last_end - 5:
            cleaned.append((s,d))
            last_end = s + d
    return cleaned
