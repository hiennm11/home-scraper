FROM cloakhq/cloakbrowser

WORKDIR /app

RUN pip install --no-cache-dir flask markdownify

COPY server.py .

EXPOSE 8899

CMD ["python3", "/app/server.py"]
