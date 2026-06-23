"""快速测试脚本 - 在 conda ai-video 环境中运行

用法:
    conda activate ai-video
    cd D:\AI\Projects\aiVideoAgent
    python run_test.py
"""

import sys
from pathlib import Path

# 确保项目根目录在路径中
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.main import app

if __name__ == "__main__":
    app()
