FROM python:3.9-slim

WORKDIR /app

# Install dependencies
RUN pip install requests pymongo urllib3 dotenv

COPY collector.py .
COPY .env .

CMD ["python", "collector.py"]

# Default environment variables
ENV ILO_HOST=your-ilo-address \
    ILO_USER=admin \
    ILO_PASSWORD=your-password \