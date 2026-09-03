import os
from typing import Tuple
from app.config import settings
from app.utils.security import generate_stored_filename

ALLOWED_JD_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
ALLOWED_CV_EXTENSIONS = {".pdf", ".docx"}

class StorageService:
    @staticmethod
    def validate_file_size(file_bytes: bytes) -> bool:
        return len(file_bytes) <= settings.max_file_size_bytes

    @staticmethod
    def validate_extension(filename: str, allowed_extensions: set) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        return ext in allowed_extensions

    @staticmethod
    def validate_file_header(file_bytes: bytes, filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".pdf":
            return file_bytes.startswith(b"%PDF-")
        elif ext == ".docx":
            return file_bytes.startswith(b"PK\x03\x04")
        elif ext == ".txt":
            try:
                file_bytes[:1024].decode("utf-8")
                return True
            except UnicodeDecodeError:
                try:
                    file_bytes[:1024].decode("latin-1")
                    return True
                except Exception:
                    return False
        elif ext == ".doc":
            ole_header = bytes([0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1])
            return file_bytes.startswith(ole_header) or len(file_bytes) > 0
        return False

    @staticmethod
    def save_file(file_bytes: bytes, original_filename: str, category: str = "jds") -> Tuple[str, str, int, str]:
        if not StorageService.validate_file_size(file_bytes):
            raise ValueError(f"File size exceeds limit of {settings.MAX_FILE_SIZE_MB}MB")

        allowed = ALLOWED_JD_EXTENSIONS if category == "jds" else ALLOWED_CV_EXTENSIONS
        if not StorageService.validate_extension(original_filename, allowed):
            raise ValueError(f"File format not supported. Allowed formats: {', '.join(sorted(allowed))}")

        if not StorageService.validate_file_header(file_bytes, original_filename):
            raise ValueError("File content header does not match expected file type.")

        target_dir = settings.jd_storage_path if category == "jds" else settings.cv_storage_path
        os.makedirs(target_dir, exist_ok=True)

        stored_filename = generate_stored_filename(original_filename)
        stored_path = os.path.join(target_dir, stored_filename)

        with open(stored_path, "wb") as f:
            f.write(file_bytes)

        ext = os.path.splitext(original_filename)[1].lower()
        if ext == ".pdf":
            mime_type = "application/pdf"
        elif ext == ".docx":
            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif ext == ".doc":
            mime_type = "application/msword"
        else:
            mime_type = "text/plain"

        return stored_path, stored_filename, len(file_bytes), mime_type

storage_service = StorageService()
