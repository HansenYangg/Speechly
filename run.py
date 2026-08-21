"""
Main entry point for the refactored Speechly application.

This uses the new Flask app factory pattern with dependency injection.
"""
import os
from app import create_app

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    # Get port from environment or use default
    port = int(os.getenv('PORT', 5001))
    debug = os.getenv('FLASK_ENV', 'development') == 'development'

    print(f"""
===============================================================
           Speechly - AI Speech Evaluator

  Server running at: http://localhost:{port}
  Environment: {os.getenv('FLASK_ENV', 'development')}

  Press Ctrl+C to stop the server
===============================================================
    """)

    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        threaded=True
    )
