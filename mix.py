import os
import subprocess


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _is_image(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in IMAGE_EXTENSIONS


def create_mix(track_paths: list[str], media_path: str, output_dir: str, crossfade: int = 3) -> str:
    """
    Crea un mix audio con crossfade e genera un video finale.
    media_path può essere un video (.mp4) oppure un'immagine (.jpg/.png).
    """

    os.makedirs(output_dir, exist_ok=True)

    output_mix = os.path.join(output_dir, "mix.mp3")
    visual_video = os.path.join(output_dir, "visual.mp4")
    final_video = os.path.join(output_dir, "final_video.mp4")

    # -----------------------------
    # 1. Normalizza tracce audio
    # -----------------------------
    normalized_tracks = []

    for i, track in enumerate(sorted(track_paths)):
        norm_path = os.path.join(output_dir, f"norm_{i}.mp3")

        subprocess.run([
            "ffmpeg", "-y",
            "-i", track,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            norm_path
        ], check=True, capture_output=True)

        normalized_tracks.append(norm_path)

    # -----------------------------
    # 2. Crossfade audio
    # -----------------------------
    num_tracks = len(normalized_tracks)

    if num_tracks == 1:
        subprocess.run([
            "ffmpeg", "-y",
            "-i", normalized_tracks[0],
            "-c:a", "libmp3lame",
            "-q:a", "2",
            output_mix
        ], check=True, capture_output=True)

    else:
        inputs = []
        filter_parts = []
        last_label = "[0:a]"

        for track in normalized_tracks:
            inputs += ["-i", track]

        for i in range(1, num_tracks):
            current_label = f"[{i}:a]"
            output_label = "[out]" if i == num_tracks - 1 else f"[a{i}]"

            filter_parts.append(
                f"{last_label}{current_label}acrossfade=d={crossfade}:c1=tri:c2=tri{output_label}"
            )

            last_label = output_label

        filter_complex = ";".join(filter_parts)

        subprocess.run([
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:a", "libmp3lame",
            "-q:a", "2",
            output_mix
        ], check=True, capture_output=True)

    # -----------------------------
    # 3. Durata audio
    # -----------------------------
    result = subprocess.run([
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        output_mix
    ], capture_output=True, text=True, check=True)

    audio_duration = float(result.stdout.strip())

    # -----------------------------
    # 4. Generazione video
    # -----------------------------
    if _is_image(media_path):

        filter_complex = (
            "[0:v]scale=1920:-1:force_original_aspect_ratio=increase,"
            "crop=1920:1080,"
            "boxblur=20:1[bg];"
            "[0:v]scale=1920:-1:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )

        subprocess.run([
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", media_path,
            "-t", str(audio_duration),
            "-filter_complex", filter_complex,
            "-r", "30",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            visual_video
        ], check=True, capture_output=True)

    else:

        subprocess.run([
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", media_path,
            "-t", str(audio_duration),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            visual_video
        ], check=True, capture_output=True)

    # -----------------------------
    # 5. Merge audio + video
    # -----------------------------
    subprocess.run([
        "ffmpeg", "-y",
        "-i", visual_video,
        "-i", output_mix,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        final_video
    ], check=True, capture_output=True)

    return final_video




if __name__ == "__main__":
    result = create_mix(
        track_paths=[
            "energy_drift/tracks/_ (1).mp3",
            "energy_drift/tracks/_ (2).mp3"
        ],
        media_path="energy_drift/b-unit.jpg",
        output_dir="output"
    )

    print("Video creato:", result)