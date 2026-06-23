"""
AI迷宫玩家 - 一键启动脚本
运行此脚本后，在浏览器中打开 http://localhost:8000 即可使用
"""
import os
import webbrowser
import threading
import time

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from uvicorn import run

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    print("=" * 50)
    print("  AI迷宫玩家 - 全栈Web应用")
    print("  算法课设 - 路径规划与Boss战斗优化")
    print("=" * 50)
    print()
    print("  启动中... 浏览器将自动打开 http://localhost:8000")
    print("  按 Ctrl+C 停止服务")
    print()

    threading.Thread(target=open_browser, daemon=True).start()
    run("app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
