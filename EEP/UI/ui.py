import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, get_flashed_messages
from werkzeug.utils import secure_filename
from pathlib import Path
import sys
import uuid
import json

# --- Configuration ---
# Define upload folder INSIDE the container
UPLOAD_FOLDER = Path("/tmp_uploads")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024 # 16 MB upload limit

# --- Add orchestrator location to sys.path ---
# Assuming Dockerfile copies EEP/UI/* into /app
# ui.py will be at /app/ui.py
# orchestrator will be at /app/orchestrator/main_generator.py
# So, the relative path works if WORKDIR is /app
try:
    # Import directly using the relative path established by the COPY command
    from orchestrator.main_generator import generate_post_candidates, select_best_candidate
    orchestrator_imported = True
    logging.info("Successfully imported orchestrator functions.")
except ImportError as e:
    logging.error(f"Failed to import orchestrator functions: {e}. Check Dockerfile COPY and file structure.", exc_info=True)
    orchestrator_imported = False
    # Define dummy functions if import fails
    def generate_post_candidates(username, keyword, image_path, theme): # Added theme
        return [], {"error": "Orchestrator not loaded"}
    def select_best_candidate(candidates): return None

# --- Flask App Setup ---
app = Flask(__name__, static_folder='static', template_folder='templates') # Explicitly set folders
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_default_development_secret_key")

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
app.logger.setLevel(logging.INFO) # Integrate logger

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
    processing_message = None

    if request.method == 'POST':
        processing_message = "Starting generation..."
        app.logger.info("Received POST request.")

        username = request.form.get('username')
        keyword = request.form.get('keyword') or None
        theme = request.form.get('theme', 'casual') # Get theme
        image_file = request.files.get('image')
        temp_image_path = None
        upload_error = False

        if not username:
            flash("Username is required.", "error")
            return render_template('index.html', suggestion=None, error=None, processing_message=None)

        if image_file and image_file.filename:
            if allowed_file(image_file.filename):
                try:
                    UPLOAD_FOLDER.mkdir(exist_ok=True) # Ensure upload folder exists in container
                    filename = secure_filename(f"{uuid.uuid4()}_{image_file.filename}")
                    temp_image_path = UPLOAD_FOLDER / filename
                    image_file.save(str(temp_image_path))
                    app.logger.info(f"Image '{filename}' saved temporarily to {temp_image_path}")
                except Exception as e:
                    app.logger.error(f"Failed to save uploaded image: {e}", exc_info=True)
                    flash(f"Error saving uploaded image: {e}", "error")
                    temp_image_path = None
                    upload_error = True
            else:
                flash("Invalid image file type. Allowed types: png, jpg, jpeg, gif", "error")
                return render_template('index.html', suggestion=None, error=None, processing_message=None)

        if upload_error and not temp_image_path:
             error_message = "Processing cannot continue due to image upload error."
             processing_message = None
        else:
            try:
                processing_message = "Gathering context and generating candidates..."
                app.logger.info(f"Calling orchestrator for user='{username}', keyword='{keyword}', theme='{theme}', image_path='{temp_image_path}'")

                # NOTE: Pass the path *inside the container*
                # Pass theme to orchestrator if it accepts it (modify orchestrator needed)
                all_candidates, context_results = generate_post_candidates(
                    username=username,
                    keyword=keyword,
                    image_path=str(temp_image_path) if temp_image_path else None
                    # theme=theme # Add theme here if orchestrator handles it
                )

                processing_message = "Selecting best candidate..."
                app.logger.info(f"Orchestrator generated {len(all_candidates)} candidates. Selecting best...")
                best_suggestion_raw = select_best_candidate(all_candidates)

                if best_suggestion_raw:
                    app.logger.info(f"Best candidate selected: {best_suggestion_raw.get('candidate_id')}")
                    # Prepare suggestion for template (e.g., simplify structure)
                    suggestion = {
                         "status": "Success",
                         "username": best_suggestion_raw.get("username"),
                         "selected_keyword": best_suggestion_raw.get("selected_keyword"),
                         "predicted_relative_engagement": best_suggestion_raw.get("predicted_relative_engagement"),
                         "filter_status": best_suggestion_raw.get("filter_status"),
                         "filter_reason": best_suggestion_raw.get("filter_reason"),
                         "final_text_suggestion": best_suggestion_raw.get("final_text"),
                         "generated_caption": best_suggestion_raw.get("generated_caption"),
                         "generated_hashtags": best_suggestion_raw.get("generated_hashtags", []),
                         "has_media": best_suggestion_raw.get("has_media"),
                         "final_image_reference": best_suggestion_raw.get("image_reference"), # URL or input path
                         "image_description": best_suggestion_raw.get("image_description"),
                         "full_json": best_suggestion_raw # Keep raw for details view
                    }
                    processing_message = None
                else:
                    app.logger.warning("Orchestrator did not return a suitable suggestion.")
                    error_message = "Failed to generate a suitable post suggestion. No candidates passed filters or scoring."
                    # Include context errors if helpful
                    if context_results.get("user_profile_analysis", {}).get("error"):
                        error_message += f" | Profile Error: {context_results['user_profile_analysis']['error']}"
                    if context_results.get("trend_analysis", {}).get("error"):
                         error_message += f" | Trend Error: {context_results['trend_analysis']['error']}"
                    processing_message = None


            except Exception as e:
                app.logger.error(f"Error during orchestrator execution: {e}", exc_info=True)
                error_message = f"An unexpected error occurred during generation: {e}"
                processing_message = None

        if temp_image_path and temp_image_path.exists():
            try:
                temp_image_path.unlink()
                app.logger.info(f"Cleaned up temporary image: {temp_image_path}")
            except OSError as e:
                app.logger.error(f"Error removing temporary file {temp_image_path}: {e}")

    # Use flashed messages if available, otherwise use error_message
    final_error = None
    if get_flashed_messages(category_filter=["error"]):
        pass # Flashed messages will be handled by the template
    else:
        final_error = error_message # Pass direct error if no flash message

    return render_template('index.html',
                           suggestion=suggestion,
                           error=final_error,
                           processing_message=processing_message)


# --- Run the App ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5050))
    app.logger.info(f"Starting EEP UI Flask application on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False) # Set debug=False for container