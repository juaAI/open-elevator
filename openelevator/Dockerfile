FROM ubuntu:latest

WORKDIR /tmp

# install dependencies
RUN apt-get update -y && apt-get upgrade -y && apt-get install wget bzip2 sudo git -y

# get miniconda 
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
RUN chmod -X Miniconda3-latest-Linux-x86_64.sh
RUN bash Miniconda3-latest-Linux-x86_64.sh -b

# install env
WORKDIR /app
ENV PATH /root/miniconda3/bin:$PATH
COPY env/environment.yml .
RUN conda update -n base -c defaults conda
RUN conda env create -f environment.yml
COPY /. .

# download & prepare initial data
RUN /root/miniconda3/envs/open-elevator/bin/python openelevator.py

# get args from docker-compose.yml
ARG ssl
ARG cert
ARG cert-key
ARG host
ARG port
ARG rate-limit
ARG rate-reset

# copy ssl cert
ADD ${cert} ${cert}
ADD ${certkey} ${certkey}

# port expose
EXPOSE 443

ENTRYPOINT ["/root/miniconda3/envs/open-elevator/bin/python", "server.py"]
