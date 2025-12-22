FROM python:3.10-slim

WORKDIR /app

# install runtime deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy app code
COPY . .

# run app
CMD ["python", "-m", "app.cmd.main"]