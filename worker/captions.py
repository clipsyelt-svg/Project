import os, subprocess, tempfile, pysrt

def transcribe_and_make_srt(in_mp4, srt_path, model_size="small"):
    # Whisper CPU mode
    import whisper
    model = whisper.load_model(model_size)
    result = model.transcribe(in_mp4, fp16=False, language=None)
    subs = pysrt.SubRipFile()
    def to_ts(sec):
        if sec < 0: sec = 0
        ms = int((sec - int(sec)) * 1000)
        s = int(sec) % 60
        m = (int(sec) // 60) % 60
        h = int(sec) // 3600
        return pysrt.SubRipTime(hour=h, minute=m, second=s, microsecond=ms*1000)
    for i, seg in enumerate(result["segments"], 1):
        item = pysrt.SubRipItem(index=i, start=to_ts(seg["start"]), end=to_ts(seg["end"]), text=seg["text"].strip())
        subs.append(item)
    subs.clean_indexes()
    subs.save(srt_path, encoding="utf-8")
    # Return the transcript text (joined)
    return " ".join([s.text for s in subs])
