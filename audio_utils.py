from __future__ import annotations

import mimetypes
import os
import re
from pathlib import Path

from google import genai

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


class AudioTranscriptionError(RuntimeError):
    pass


def _guess_mime_type(file_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        return mime_type

    suffix = Path(file_path).suffix.lower()
    if suffix in {".ogg", ".oga"}:
        return "audio/ogg"
    if suffix == ".mp3":
        return "audio/mpeg"
    if suffix == ".wav":
        return "audio/wav"
    if suffix == ".m4a":
        return "audio/mp4"
    if suffix == ".webm":
        return "audio/webm"

    return "application/octet-stream"


def _clean_transcript(text: str) -> str:
    clean = (text or "").strip()
    if not clean:
        return ""

    clean = re.sub(r"^```(?:text|markdown)?", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"```$", "", clean).strip()
    clean = re.sub(r"^(trascrizione|transcript)\s*:\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+", " ", clean).strip()

    for prefix in ["ecco la trascrizione", "di seguito la trascrizione"]:
        if clean.lower().startswith(prefix):
            colon_index = clean.find(":")
            if colon_index != -1:
                clean = clean[colon_index + 1 :].strip()
            break

    return clean


def transcribe_audio(file_path: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise AudioTranscriptionError("GEMINI_API_KEY non trovata nel file .env")

    path = Path(file_path)
    if not path.exists():
        raise AudioTranscriptionError(f"File audio non trovato: {file_path}")

    prompt = (
        "Trascrivi questo audio in italiano restituendo solo il testo trascritto, "
        "senza commenti, senza markdown, senza interpretazione."
    )

    try:
        client = genai.Client(api_key=api_key)
        mime_type = _guess_mime_type(str(path))

        try:
            uploaded = client.files.upload(
                file=str(path),
                config={"mime_type": mime_type},
            )
        except TypeError:
            uploaded = client.files.upload(file=str(path))

        response = client.models.generate_content(
            model=MODEL,
            contents=[prompt, uploaded],
        )

        text = _clean_transcript(getattr(response, "text", ""))
        if not text:
            raise AudioTranscriptionError("Trascrizione vuota restituita da Gemini.")

        return text
    except AudioTranscriptionError:
        raise
    except Exception as exc:
        raise AudioTranscriptionError(f"Errore durante la trascrizione audio: {exc}") from exc
