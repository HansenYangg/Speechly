#!/usr/bin/env python3
"""
AI-powered Speech Evaluator
main application entry point
"""

from speech_evaluator import SpeechEvaluator
from ui import UserInterface

def main():
    """Main application function"""
    # Initialize the speech evaluator
    speech_evaluator = SpeechEvaluator()
    
    # Initialize the user interface
    ui = UserInterface(speech_evaluator)
    
    # Start the application
    ui.select_language()
    ui.main_menu()



if __name__ == "__main__":
    main()
