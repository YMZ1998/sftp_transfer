from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sftp_transfer.cli import main

#python run.py download --host 172.16.9.185 --username zhangcheng --password zyloxtb0226 --remote /home/zhangcheng/code/2D-Image-Segmentation/data/input.png --local D:\Data
if __name__ == "__main__":
    raise SystemExit(main())
