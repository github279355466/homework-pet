import uvicorn
import os
import sys

# 切换到 app 目录（确保数据库路径正确）
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_THIS_DIR)

# 添加 app 目录到路径
sys.path.insert(0, _THIS_DIR)

from main import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5001, log_level="info")
