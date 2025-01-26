# Build a custom kasmweb image following guidelines from https://kasmweb.com/docs/latest/how_to/building_images.html
FROM kasmweb/ubuntu-jammy-desktop:1.16.0
USER root

ENV HOME=/home/kasm-default-profile
ENV STARTUPDIR=/dockerstartup
ENV INST_SCRIPTS=$STARTUPDIR/install
WORKDIR $HOME

######### Customize Container Here ###########

# Install dependencies for OpenAdapt

RUN curl -fsSL https://deb.nodesource.com/setup_21.x | bash
RUN apt-get update && \
    apt-get install -y nodejs tesseract-ocr portaudio19-dev && \
    apt-get clean

# Disable ssl and basic auth and enable sudo as this will be a developer container

ENV VNCOPTIONS=-disableBasicAuth
RUN sed -i '/  ssl:/a\    require_ssl: false' /etc/kasmvnc/kasmvnc.yaml
# https://github.com/kasmtech/workspaces-core-images/issues/2
RUN sed -i 's/-sslOnly//g' /dockerstartup/vnc_startup.sh
RUN echo 'kasm-user ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

######### End Customizations ###########


RUN chown 1000:0 $HOME
RUN $STARTUPDIR/set_user_permission.sh $HOME

ENV HOME=/home/kasm-user
WORKDIR $HOME
RUN mkdir -p $HOME && chown -R 1000:0 $HOME

USER 1000


######### Customize Container Here ###########

WORKDIR $HOME

ENV PATH=$HOME/.local/bin:$PATH \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache
RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=1.8.5 python3 -

RUN git clone https://github.com/bard/OpenAdapt
WORKDIR $HOME/OpenAdapt
RUN poetry install

# replace torch and torchvision with cpu-only versions
RUN poetry source add --priority explicit pytorch_cpu https://download.pytorch.org/whl/cpu
RUN poetry add --source pytorch_cpu torch==2.0.1+cpu torchvision==0.15.2+cpu

# install prebuilt cpu-only detectron
RUN poetry source add --priority explicit torch_packages https://miropsota.github.io/torch_packages_builder
RUN poetry add --source torch_packages detectron2==0.6+2a420edpt2.0.1cpu

# for some reason, pyaudio either doesn't get installed, or it gets removed in the steps above
RUN poetry remove pyaudio && poetry add pyaudio

# restrict python compatibliity to accommodate pyside6.2
# RUN sed -i 's/python = ">=3.10,<3.12/python = ">=3.10,<3.11/' pyproject.toml
# install a pyside version compatible with system-installed qt
# RUN poetry add pyside6==6.2

RUN cd openadapt && poetry run alembic upgrade head
RUN cd openadapt/app/dashboard && npm install

######### End Customizations ###########

