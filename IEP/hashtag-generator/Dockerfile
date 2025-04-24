# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
# Specify the path relative to the build context root
COPY IEP/hashtag-generator/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code from the specific IEP directory into the container at /app
COPY IEP/hashtag-generator/ .

# Make port 5002 available (using a different port than Caption Gen)
EXPOSE 5002

# Define the command to run the application
CMD ["python", "app.py"]
