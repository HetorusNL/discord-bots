FROM hetorusnl/python-poetry

# add the report manager bot python files to the docker
COPY poetry.lock /code
COPY pyproject.toml /code
COPY report-manager-bot/ /code

# add/update the container labels
LABEL org.label-schema.vcs-ref=$VCS_REF
LABEL org.label-schema.vcs-url=https://github.com/HetorusNL/discord-bots
LABEL org.opencontainers.image.authors=tim@hetorus.nl
LABEL org.opencontainers.image.source=https://github.com/HetorusNL/discord-bots
LABEL org.opencontainers.image.description="Report manager - discord server administration bot"
LABEL org.opencontainers.image.licenses=MIT
