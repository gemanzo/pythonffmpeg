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
    video_file: UploadFile = File(..., description="File video di loop .mp4"),
):
    # Validazione estensioni
    for audio in audio_files:
        if not audio.filename.lower().endswith(".mp3"):
            raise HTTPException(status_code=400, detail=f"File audio non valido: {audio.filename}. Sono accettati solo .mp3")

    if not video_file.filename.lower().endswith(".mp4"):
        raise HTTPException(status_code=400, detail=f"File video non valido: {video_file.filename}. Sono accettati solo .mp4")

    if len(audio_files) == 0:
        raise HTTPException(status_code=400, detail="Fornire almeno un file audio.")

    # Directory temporanea isolata per ogni richiesta
    job_id = uuid.uuid4().hex
    work_dir = os.path.join(tempfile.gettempdir(), f"mix_{job_id}")
    os.makedirs(work_dir, exist_ok=True)

    try:
        # Salva file caricati
        video_path = os.path.join(work_dir, "input_video.mp4")
        await _save_upload(video_file, video_path)

        track_paths = []
        for i, audio in enumerate(audio_files):
            audio_path = os.path.join(work_dir, f"track_{i}.mp3")
            await _save_upload(audio, audio_path)
            track_paths.append(audio_path)

        # Esegui il mix
        output_dir = os.path.join(work_dir, "output")
        final_video = create_mix(
            track_paths=track_paths,
            video_path=video_path,
            output_dir=output_dir,
        )

        # Pulizia directory temporanea dopo l'invio della risposta
        background_tasks.add_task(shutil.rmtree, work_dir, True)

        # Restituisce il video come file da scaricare
        return FileResponse(
            path=final_video,
            media_type="video/mp4",
            filename="final_video.mp4",
            background=background_tasks,
        )

    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))
