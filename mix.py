import os
import subprocess


def create_mix(track_paths: list[str], video_path: str, output_dir: str, crossfade: int = 3) -> str:
    """
    Normalizza le tracce audio, le unisce con crossfade, fa loop del video
    per tutta la durata dell'audio e combina video + audio.

    Args:
        track_paths: Lista di path ai file MP3 da mixare.
        video_path: Path al file video di loop (.mp4).
        output_dir: Directory dove salvare i file intermedi e il risultato.
        crossfade: Durata in secondi del crossfade tra le tracce.

    Returns:
        Path al file video finale.
    """
    os.makedirs(output_dir, exist_ok=True)

    output_mix = os.path.join(output_dir, "mix.mp3")
    looped_video = os.path.join(output_dir, "looped_video.mp4")
    final_video = os.path.join(output_dir, "final_video.mp4")

    # 1. Normalizza tutte le tracce
    normalized_tracks = []
    for i, track in enumerate(sorted(track_paths)):
        norm_path = os.path.join(output_dir, f"norm_{i}.mp3")
        subprocess.run([
            "ffmpeg", "-y", "-i", track,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            norm_path
        ], check=True, capture_output=True)
        normalized_tracks.append(norm_path)

    # 2. Prepara input e filter_complex per crossfade
    num_tracks = len(normalized_tracks)

    if num_tracks == 1:
        # Nessun crossfade necessario con una sola traccia
        subprocess.run([
            "ffmpeg", "-y", "-i", normalized_tracks[0],
            "-c:a", "libmp3lame", "-q:a", "2",
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

    # 3. Calcola durata audio
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        output_mix
    ], capture_output=True, text=True, check=True)
    audio_duration = float(result.stdout.strip())

    # 4. Loop video per tutta la durata audio
    subprocess.run([
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", video_path,
        "-t", str(audio_duration),
        "-c:v", "libx264",
        "-crf", "23",
        "-preset", "medium",
        looped_video
    ], check=True, capture_output=True)

    # 5. Combina video e audio
    subprocess.run([
        "ffmpeg", "-y",
        "-i", looped_video,
        "-i", output_mix,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        final_video
    ], check=True, capture_output=True)

    return final_video
