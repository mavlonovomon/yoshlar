import os
import sys
from pathlib import Path


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    default_file = Path(r"C:\Users\Genius007\Desktop\RP.xlsx")
    file_path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else default_file

    if not file_path.exists():
        print(f"Fayl topilmadi: {file_path}")
        return 1

    from django.core.management import execute_from_command_line

    sys.argv = [
        "manage.py",
        "import_maktab_oquvchilar_from_rp",
        "--file",
        str(file_path),
    ]
    os.chdir(base_dir)
    execute_from_command_line(sys.argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
