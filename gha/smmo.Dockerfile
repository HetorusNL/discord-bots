FROM hetorusnl/python-poetry

# add the smmo bot python files to the docker
COPY poetry.lock /code
COPY pyproject.toml /code
COPY smmo-bot/ /code

# add/update the container labels
LABEL org.label-schema.vcs-ref=$VCS_REF
LABEL org.label-schema.vcs-url=https://github.com/HetorusNL/discord-bots
LABEL org.opencontainers.image.authors=tim@hetorus.nl
LABEL org.opencontainers.image.source=https://github.com/HetorusNL/discord-bots
LABEL org.opencontainers.image.description="SMMO game discord bot"
LABEL org.opencontainers.image.licenses=MIT
