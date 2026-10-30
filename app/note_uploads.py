"""Safe, bounded extraction for meeting-note uploads and ZIP demo bundles."""
from io import BytesIO
from pathlib import PurePosixPath
import zipfile

from pypdf import PdfReader

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_EXPANDED_BYTES = 8 * 1024 * 1024
MAX_FILES = 8
MAX_TEXT_CHARS = 30_000
SUPPORTED = {".txt", ".md", ".pdf"}


def _safe_name(name: str) -> str:
    return PurePosixPath(name.replace("\\", "/")).name[:180] or "notes.txt"


def _decode(name: str, data: bytes) -> tuple[str, str]:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"{name} is too large (5 MB maximum).")
    suffix = PurePosixPath(name.lower()).suffix
    if suffix not in SUPPORTED:
        raise ValueError(f"Unsupported file type for {name}. Use .txt, .md, or .pdf files.")
    if suffix == ".pdf":
        try:
            reader = PdfReader(BytesIO(data), strict=False)
            if len(reader.pages) > 40:
                raise ValueError(f"{name} has too many pages (40 maximum).")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Could not read {name} as a PDF.") from exc
    else:
        text = data.decode("utf-8-sig", errors="replace")
    text = "".join(ch for ch in text if ch in "\n\r\t" or (ord(ch) >= 32 and ord(ch) != 127)).strip()
    if not text:
        raise ValueError(f"{name} contains no readable text.")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(f"{name} is too long (30,000 extracted characters maximum).")
    return _safe_name(name), text


def extract_note_upload(name: str, data: bytes) -> list[tuple[str, str]]:
    """Return extracted (filename, text) pairs from a single file or ZIP archive."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Each upload must be 5 MB or smaller.")
    if PurePosixPath(name.lower()).suffix != ".zip":
        return [_decode(name, data)]
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("The ZIP file is damaged or invalid.") from exc
    extracted: list[tuple[str, str]] = []
    expanded = 0
    with archive:
        files = [info for info in archive.infolist() if not info.is_dir()
                 and not PurePosixPath(info.filename).name.startswith("__MACOSX")
                 and PurePosixPath(info.filename).name != ".DS_Store"]
        if not files:
            raise ValueError("The ZIP contains no supported note files.")
        if len(files) > MAX_FILES:
            raise ValueError(f"A ZIP can contain at most {MAX_FILES} note files.")
        for info in files:
            if info.flag_bits & 0x1:
                raise ValueError("Password-protected ZIP files are not supported.")
            expanded += info.file_size
            if expanded > MAX_EXPANDED_BYTES:
                raise ValueError("The ZIP expands beyond the 8 MB total limit.")
            try:
                data = archive.read(info)
            except Exception as exc:
                raise ValueError("Could not read a file inside the ZIP.") from exc
            extracted.append(_decode(info.filename, data))
    return extracted
