"""一键启动 Web 界面"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app.web import build_ui

if __name__ == "__main__":
    print("\U0001f916 启动 Research Agent Web 界面...")
    print("  \U0001f310 http://127.0.0.1:7860");
    print("  Press Ctrl+C to stop\n")
    demo = build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)