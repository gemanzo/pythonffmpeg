import os
import shutil
import tempfile
import uuid

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from mix import create_mix

app = FastAPI(title="Audio/Video Mix Service")


async def _save_upload(upload: UploadFile, dest_path: str) -> None:
    with open(dest_path, "wb") as f:
        content = await upload.read()
        f.write(content)


@app.post("/mix")
async def mix(
    background_tasks: BackgroundTasks,
    audio_files: list[UploadFile] = File(..., description="Uno o più file audio .mp3"),
    media_file: UploadFile = File(..., description="Video .mp4 oppure immagine .jpg/.png"),
):
    # Validazione audio
    if len(audio_files) == 0:
        raise HTTPException(status_code=400, detail="Fornire almeno un file audio.")

    for audio in audio_files:
        if not audio.filename.lower().endswith(".mp3"):
            raise HTTPException(
                status_code=400,
                detail=f"File audio non valido: {audio.filename}. Sono accettati solo .mp3",
            )

    # Validazione media
    allowed_media = (".mp4", ".jpg", ".jpeg", ".png")

    if not media_file.filename.lower().endswith(allowed_media):
        raise HTTPException(
            status_code=400,
            detail="Media non valido. Accettati: .mp4 .jpg .jpeg .png",
        )

    # Directory temporanea isolata per ogni richiesta
    job_id = uuid.uuid4().hex
    work_dir = os.path.join(tempfile.gettempdir(), f"mix_{job_id}")
    os.makedirs(work_dir, exist_ok=True)

    try:
        # Salva media (video o immagine)
        media_ext = os.path.splitext(media_file.filename)[1].lower()
        media_path = os.path.join(work_dir, f"input_media{media_ext}")
        await _save_upload(media_file, media_path)

        # Salva tracce audio
        track_paths = []

        for i, audio in enumerate(audio_files):
            audio_path = os.path.join(work_dir, f"track_{i}.mp3")
            await _save_upload(audio, audio_path)
            track_paths.append(audio_path)

        # Esegui il mix
        output_dir = os.path.join(work_dir, "output")

        final_video = create_mix(
            track_paths=track_paths,
            media_path=media_path,
            output_dir=output_dir,
        )

        # Pulizia directory temporanea dopo risposta
        background_tasks.add_task(shutil.rmtree, work_dir, True)

        return FileResponse(
            path=final_video,
            media_type="video/mp4",
            filename="final_video.mp4",
            background=background_tasks,
        )

    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))