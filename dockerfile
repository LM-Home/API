FROM python:slim-buster

WORKDIR /PythonT4
COPY . /PythonT4
RUN pip install -r /PythonT4/requirements.txt \
    && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo 'Asia/Shanghai' >/etc/timezone
CMD ["python", "main.py"]