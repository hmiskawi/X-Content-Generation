import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash # Added flash for messages
from werkzeug.utils import secure_filename
from pathlib import Path
import sys
import uuid # For unique temporary filenames
import json # For pretty printing in logs if needed

# --- Configuration ---
UPLOAD_FOLDER = Path("./tmp_uploads") # Create this folder or change path
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024 # 16 MB upload limit

# --- Add orchestrator to sys.path ---
# Assumes ui_app.py is in the project root, and orchestrator is ./orchestrator/
PROJECT_ROOT = Path(__file__).resolve().parent
ORCHESTRATOR_DIR = PROJECT_ROOT / "orchestrator"
sys.path.insert(0, str(PROJECT_ROOT)) # Add root to path

# --- Import Orchestrator Logic ---
try:
    # Import the necessary functions from the refactored main_generator
    from orchestrator.main_generator import generate_post_candidates, select_best_candidate
    orchestrator_imported = True
except ImportError as e:
    logging.error(f"Failed to import orchestrator functions: {e}. Check sys.path and file structure.", exc_info=True)
    orchestrator_imported = False
    # Define dummy functions if import fails, so app can still start (with errors on use)
    def generate_post_candidates(username, keyword, image_path): return [], {"error": "Orchestrator not loaded"}
    def select_best_candidate(candidates): return None

# --- Flask App Setup ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_default_development_secret_key") # Needed for flash messages

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Integrate Flask's logger with basicConfig
app.logger.setLevel(logging.INFO)

# --- Helper Function ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Routes ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if not orchestrator_imported:
        flash("ERROR: Orchestrator module could not be loaded. Check server logs.", "error")
        return render_template('index.html', error="Application configuration error.")

    suggestion = None
    error_message = None
    processing_message = None # Message to show during processing

    if request.method == 'POST':
        processing_message = "Starting generation..."
        app.logger.info("Received POST request.")

        # Get form data
        username = request.form.get('username')
        keyword = request.form.get('keyword') or None # Treat empty string as None
        num_captions_str = request.form.get('num_captions', '3')
        theme = request.form.get('theme', 'casual')

        try:
             num_captions = int(num_captions_str)
             if not 1 <= num_captions <= 10: # Add sensible limits
                 raise ValueError("Number of captions must be between 1 and 10.")
             # Update the orchestrator's setting if possible (depends on how it's structured)
             # For now, we'll just log it, assuming the orchestrator uses its default or is refactored to accept it
             app.logger.info(f"Requested {num_captions} captions.")
        except ValueError as e:
             flash(f"Invalid number of captions: {e}", "error")
             return render_template('index.html') # Render form again

        image_file = request.files.get('image')
        temp_image_path = None
        upload_error = False

        # Validate username
        if not username:
            flash("Username is required.", "error")
            return render_template('index.html') # Show form again

        # --- Handle File Upload ---
        if image_file and image_file.filename:
            if allowed_file(image_file.filename):
                try:
                    UPLOAD_FOLDER.mkdir(exist_ok=True) # Ensure upload folder exists
                    filename = secure_filename(f"{uuid.uuid4()}_{image_file.filename}")
                    temp_image_path = UPLOAD_FOLDER / filename
                    image_file.save(str(temp_image_path))
                    app.logger.info(f"Image '{filename}' saved temporarily to {temp_image_path}")
                except Exception as e:
                    app.logger.error(f"Failed to save uploaded image: {e}", exc_info=True)
                    flash(f"Error saving uploaded image: {e}", "error")
                    temp_image_path = None
                    upload_error = True # Flag error but might still proceed without image
            else:
                flash("Invalid image file type. Allowed types: png, jpg, jpeg, gif", "error")
                return render_template('index.html') # Show form again with error

        if upload_error and not temp_image_path: # If saving failed critically
             error_message = "Processing cannot continue due to image upload error."
        else:
            # --- Call Orchestrator ---
            try:
                processing_message = "Gathering context and generating candidates..."
                app.logger.info(f"Calling orchestrator for user='{username}', keyword='{keyword}', image_path='{temp_image_path}'")

                # NOTE: Pass the *path* to the temporarily saved image
                # The orchestrator simulation currently just uses this path as a reference
                all_candidates, context_results = generate_post_candidates(
                    username=username,
                    keyword=keyword,
                    image_path=str(temp_image_path) if temp_image_path else None
                    # TODO: Refactor orchestrator to accept num_captions if desired
                )

                processing_message = "Selecting best candidate..."
                app.logger.info(f"Orchestrator generated {len(all_candidates)} candidates. Selecting best...")
                suggestion = select_best_candidate(all_candidates)

                if suggestion:
                    app.logger.info(f"Best candidate selected: {suggestion.get('candidate_id')}")
                    processing_message = None # Clear processing message on success
                else:
                    app.logger.warning("Orchestrator did not return a suitable suggestion.")
                    error_message = "Failed to generate a suitable post suggestion. No candidates passed filters or scoring."
                    processing_message = None

            except Exception as e:
                app.logger.error(f"Error during orchestrator execution: {e}", exc_info=True)
                error_message = f"An unexpected error occurred during generation: {e}"
                processing_message = None # Clear processing message on error

        # --- Cleanup Temporary File ---
        if temp_image_path and temp_image_path.exists():
            try:
                temp_image_path.unlink()
                app.logger.info(f"Cleaned up temporary image: {temp_image_path}")
            except OSError as e:
                app.logger.error(f"Error removing temporary file {temp_image_path}: {e}")

    # Render the template, passing results/errors
    return render_template('index.html', suggestion=suggestion, error=error_message, processing_message=processing_message)

# --- Run the App ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5050)) # Use a different port for the UI
    app.logger.info(f"Starting EEP UI Flask application on port {port}")
    # Use debug=True only for local development, NEVER in production
    app.run(debug=True, host='0.0.0.0', port=port)
