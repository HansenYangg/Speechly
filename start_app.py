#!/usr/bin/env python3
"""
Startup script for AI Speech Evaluator
Starts both backend API and frontend servers
"""
import subprocess
import sys
import threading
import time
import webbrowser
import os
from logger import setup_logger

logger = setup_logger(__name__)

def start_backend():
    """Start the backend API server"""
    try:
        print("🚀 Starting backend API server...")
        
        # In production, use Popen instead of run to avoid blocking
        if os.environ.get("PORT"):
            process = subprocess.Popen([sys.executable, 'web_api.py'])
            process.wait()
        else:
            result = subprocess.run([sys.executable, 'web_api.py'], check=True)
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Backend server failed: {e}")
        print(f"❌ Backend server failed to start: {e}")
    except KeyboardInterrupt:
        print("\n🛑 Backend server stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error in backend: {e}")
        print(f"❌ Unexpected backend error: {e}")

def start_frontend():
    """Start the frontend HTML server"""
    # Skip frontend in production (served by backend)
    if os.environ.get("PORT"):
        print("🌐 Production mode: Frontend served by backend")
        return
        
    try:
        print("🌐 Starting frontend server...")
        result = subprocess.run([sys.executable, 'html_server.py'], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Frontend server failed: {e}")
        print(f"❌ Frontend server failed to start: {e}")
    except KeyboardInterrupt:
        print("\n🛑 Frontend server stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error in frontend: {e}")
        print(f"❌ Unexpected frontend error: {e}")

def open_browser():
    """Open browser after servers start"""
    # Don't open browser in production
    if os.environ.get("PORT"):
        return
        
    time.sleep(3)
    try:
        webbrowser.open('http://localhost:3000')
        print("🌍 Opened web browser automatically")
    except Exception as e:
        print(f"Could not open browser automatically: {e}")
        print("Please manually open http://localhost:3000")

def check_dependencies():
    """Check if all required files exist"""
    required_files = [
        'web_api.py',
        'html_server.py',
        'speech_evaluator.py',
        'config.py',
        'requirements.txt'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("❌ Missing required files:")
        for file in missing_files:
            print(f" - {file}")
        print("\nPlease ensure all files are in the same directory.")
        return False
    return True

def main():
    """Main startup function"""
    print("=" * 60)
    print("🎤 AI SPEECH EVALUATOR")
    print("=" * 60)
    print()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    print("✅ All required files found")
    print()
    
    try:
        if os.environ.get("PORT"):
            # Production mode: just start backend
            print("🌐 Production mode detected")
            start_backend()
        else:
            # Local development mode
            print("🏠 Local development mode")
            
            # Start backend in a separate thread
            backend_thread = threading.Thread(target=start_backend)
            backend_thread.daemon = True
            backend_thread.start()
            
            # Give backend time to start
            time.sleep(2)
            
            # Start browser in background
            browser_thread = threading.Thread(target=open_browser)
            browser_thread.daemon = True
            browser_thread.start()
            
            # Start frontend (this blocks)
            print("🌐 Starting frontend server...")
            start_frontend()
            
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("🛑 APPLICATION STOPPED")
        print("=" * 60)
        print("Both servers have been stopped.")
        print("Thank you for using AI Speech Evaluator!")
    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)
        print(f"❌ Failed to start application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()