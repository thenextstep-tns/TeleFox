import os
import tarfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "telefox-bundle.tar.gz"

FILES_TO_INCLUDE = [
    "main.py",
    "server.py",
    "telefox_service.py",
    "config.py",
    "db.py",
    "rules.py",
    "rules.json",
    "uploader.py",
    "accounts.json",
    ".env",
    "notification_settings.json"
]

DIRS_TO_INCLUDE = [
    "sessions",
    "web"
]

def make_bundle():
    print(f"[*] Сборка архива TeleFox: {OUTPUT_FILE}...")
    with tarfile.open(OUTPUT_FILE, "w:gz") as tar:
        for file_name in FILES_TO_INCLUDE:
            file_path = BASE_DIR / file_name
            if file_path.exists():
                print(f"  + Файл: {file_name}")
                tar.add(file_path, arcname=file_name)
            else:
                print(f"  - Пропуск (отсутствует): {file_name}")

        for dir_name in DIRS_TO_INCLUDE:
            dir_path = BASE_DIR / dir_name
            if dir_path.exists():
                print(f"  + Каталог: {dir_name}/")
                for root, _, files in os.walk(dir_path):
                    for f in files:
                        full_p = Path(root) / f
                        rel_p = full_p.relative_to(BASE_DIR)
                        tar.add(full_p, arcname=str(rel_p))

    size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)
    print(f"[+] Архив telefox-bundle.tar.gz успешно создан! Размер: {size_mb:.2f} MB")

if __name__ == "__main__":
    make_bundle()
