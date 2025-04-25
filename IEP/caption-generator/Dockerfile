# Use an official Python runtime as a parent image
# Using a specific version like 3.10 is recommended for stability
# Using the 'slim' variant reduces the final image size
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY IEP/caption-generator/requirements.txt .

# Install any needed packages specified in requirements.txt
# --no-cache-dir: Disables the pip cache, reducing image size
# --upgrade pip: Ensures pip is up-to-date before installing packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code (e.g., app.py) into the container at /app
COPY IEP/caption-generator/ .

# Make port 5011 available to the network outside this container (but not necessarily to the host)
# This is the port Flask app listens on as defined in app.py
EXPOSE 5001

# Define the command to run the application
# This runs the Flask development server (suitable for many scenarios, but consider Gunicorn/uWSGI for high-load production)
# It uses the same command as in the app.py's __main__ block
CMD ["python", "app.py"]
