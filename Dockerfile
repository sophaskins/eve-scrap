FROM ubuntu:16.04

MAINTAINER Sophie Haskins
RUN apt-get -y update
RUN apt-get install -y python3 python3-pip
COPY . /app
RUN pip3 install -r /app/requirements.txt

WORKDIR /app
CMD ["/usr/bin/python3", "/app/app.py"]
EXPOSE 8080
