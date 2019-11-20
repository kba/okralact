FROM ocrd/core
MAINTAINER OCR-D
ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONIOENCODING utf8
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

WORKDIR /build-okralact
COPY lib ./lib
COPY app ./app
COPY evaluate ./evaluate
COPY engines ./engines
COPY static ./static/

COPY Makefile .
COPY requirements.txt .

RUN make deps-ubuntu deps

COPY ocrd.py .

CMD ["python3", "ocrd.py"]
