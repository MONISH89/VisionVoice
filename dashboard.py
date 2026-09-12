#!/usr/bin/env python3
"""
VisionVoice — Web Command Center & Real-Time Telemetry Dashboard Launcher.
Starts the FastAPI web server on http://localhost:8000 and optionally
opens the web dashboard in the default browser.

Usage:
  python3 dashboard.py
  python3 dashboard.py --port 8080 --open
"""

import os
import sys
import socket
import argparse
import webbrowser
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


def get_local_ip():
    """Gets the local IP address for remote device access (e.g. mobile/tablet)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def print_banner(host: str, port: int):
    local_ip = get_local_ip()
    print("=" * 72)
    print("      👁️  VISIONVOICE — WEB COMMAND CENTER & TELEMETRY DASHBOARD")
    print("=" * 72)
    print("  Real-time Camera Stream | Alignment HUD | Multilingual OCR & TTS")
    print("  Persistent Memory DB    | Voice Simulator | Subsystem Diagnostics")
    print("=" * 72)
    print(f"  ➜  Local Dashboard   : http://localhost:{port}/")
    print(f"  ➜  Network / Mobile  : http://{local_ip}:{port}/")
    print(f"  ➜  API Documentation : http://localhost:{port}/docs")
    print("=" * 72)
    print("  Press Ctrl+C to stop the dashboard server.\n")


def main():
    parser = argparse.ArgumentParser(description="VisionVoice Web Command Center")
    parser.add_argument("--host", default="0.0.0.0", help="Host IP to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8050, help="Port to listen on (default: 8050)")
    parser.add_argument("--open", action="store_true", default=True, help="Open dashboard in browser automatically")
    parser.add_argument("--no-open", dest="open", action="store_false", help="Do not open browser automatically")
    args = parser.parse_args()

    print_banner(args.host, args.port)

    if args.open:
        def open_browser():
            time.sleep(1.0)
            webbrowser.open(f"http://localhost:{args.port}/")
        threading.Thread(target=open_browser, daemon=True).start()

    import uvicorn
    uvicorn.run("dashboard_server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
