# Use an official Python runtime as the base image
FROM python:3.10

ADD --chmod=755 https://astral.sh/uv/install.sh /install.sh
RUN /install.sh && rm /install.sh

# Set the working directory in the container
WORKDIR /app

# First, copy only the requirements file to leverage Docker cache
COPY requirements.txt .

RUN /root/.cargo/bin/uv pip install --system --no-cache -r requirements.txt

# Copy the rest of the application code
COPY . .

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Run FastAPI when the container launches
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]