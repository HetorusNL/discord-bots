# Discord Bots

Repository url: https://github.com/HetorusNL/discord-bots

## Repository information:

This repository contains a collection of discord bots.
Each bot is made with a specific function in mind, so might not be directly useful.
The bots, with their functions, are listed below.
To run the bots, use the docker images shown in the 'Packages' section of this repository.
The bots are also available on docker hub at: https://hub.docker.com/u/hetorusnl

### Kotatsu bot

This bot started as a joke in the Kotatsu (Japanese learning discord server) discord.

The functions consist of:

- Extracting the profile picture of users
- Calculating the 'ship' value of mentions or strings passed to the command.

### Report manager bot

This bot is used to administer a discord server with banned words and to parse reports sent by users.

The functions consist of:

- Configure a 'reports' channel where users can report behavior/complaints of other users
- Configure an 'admin-reports' channel where the bot sends messages to
- Setting a list of 'banned words' in a discord server
- When messages contain the 'banned words', the bot sends a message with additional information to the admin-reports channel for the admins to review
- When a user files a report in the 'reports' channel, the bot deletes this message and forwards it to the 'admin-reports' channel for the admins to review

### SMMO bot

This bot is created for the SMMO game (Simple MMO), and aids with game-specific information.

The functions consist of:

- SMMO-specific functions:
  - Ping the members when the next 'world boss' is nearly ready to be attacked
  - Show a list of 'world bosses' for the current ingame week
  - Fetch the 'world boss' information from the SMMO API ( https://api.simple-mmo.com/v1/worldboss/all , but this needs an API key to use)
- Convert messages to morse code (with configurable 'dot' and 'dash' symbol)
- Extracting the profile picture of users
- Calculating the 'ship' value of mentions or strings passed to the command.
- As a joke, it responds to messages containing coffee or コーヒー and such
- As another joke, it can repeat messages sent by the creator (and delete the original message)

### Translate bot

This bot is created to add translate functionality to discord servers and WOTD (Word Of The Day) functionality.

The functions consist of:

- Translate words using the google translate API from and to any language supported
- Set the 'server language' so 'translate' commands will translate from that language to english without specifying languages
- set WOTD channel, so the WOTD will be sent to that specific channel
- Set WOTD so every day (at 12 local time) a random word from a list will be shown, including translation (currently only Swedish/Finnish is supported)
- Additional languages can be supported by adding one of the following to the `translate-bot/data/` directory (where xx is the language):
  - A `wotd-list-xx.txt` file containing a list of words in the specific language where xx is the country code of the specific language; This uses the google translate API to translate the words
  - A `wotd-list-xx-yy.tsv` file containing a list of `language-from <TAB> language-to` lines, where xx is the country code of language-from and yy is the country code of language-to; This shows the words as is (no translation needed), as both languages are provided in the file
- Generate an (additional) WOTD command
- Show how many WOTD words are left in the current collection
- This bot has a configurable command prefix

## Info regarding the google translate API

- https://www.labnol.org/code/19909-google-translate-api
- https://stackoverflow.com/questions/37667671/is-it-possible-to-access-to-google-translate-api-for-free
- https://cloud.google.com/translate/pricing

## FAQ

## License

MIT License, Copyright (c) 2023 Tim Klein Nijenhuis <tim@hetorus.nl>
