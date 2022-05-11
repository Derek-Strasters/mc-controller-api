FROM python:3.10.4

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt
COPY ./pyproject.toml /code/pyproject.toml

RUN pip install --no-cache-dir -r /code/requirements.txt

COPY ./main.py /code/main.py

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]