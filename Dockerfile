FROM continuumio/miniconda2 as conda

RUN conda install jupyter numpy matplotlib h5py

###############################################################################
FROM metsi/ats:latest as ats
LABEL Description="Amanzi-ATS: a container for demos."

USER root

# Set up conda in this environment
COPY --from=conda /opt/conda /opt/conda
# Add a line activating our environment to the .bashrc
RUN echo "source /opt/conda/bin/activate" >> ~/.bashrc
SHELL ["/bin/bash", "-c"]

ENV ATS_SRC_DIR=/home/amanzi_user/amanzi/src/physics/ats


WORKDIR /home/amanzi_user/
COPY . /home/amanzi_user/ats-demos/
WORKDIR /home/amanzi_user/ats-demos
