import subprocess
import sys
from pathlib import Path

from PIL import Image

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "make-icon.py"


def test_writes_each_size(tmp_path):
    subprocess.run([sys.executable, str(SCRIPT), "sun", str(tmp_path),
                    "icon-512.png:512", "favicon-32.png:32"], check=True)
    for name, size in (("icon-512.png", 512), ("favicon-32.png", 32)):
        with Image.open(tmp_path / name) as img:
            assert img.size == (size, size) and img.mode == "RGBA"
            assert img.getpixel((size // 2, size // 2))[3] == 255   # opaque centre


def test_rejects_unknown_glyph(tmp_path):
    done = subprocess.run([sys.executable, str(SCRIPT), "nope", str(tmp_path), "a.png:32"])
    assert done.returncode == 2
