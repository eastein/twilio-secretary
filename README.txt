# Twilio Secretary

Twilio Secretary is an SMS robot (so far).  People can subscribe to receive SMS updates from it, and people on
the Masters list can send those updates out to all the subscribers. Anyone can text all the Masters of the
robot and receive responses.

# Requirements

Install everything in the requirements.txt. Straightforward.

# WSGI

No provision has been made for running as a WSGI script yet. The module that causes flask to run is
`twilio_secretary.web` which will need adaptation.

# Config

Set the environment variable `SETTINGS_JSON` to the path of a JSON file containing something like the following:

    {
        "SID": "twilio SID here",
        "TOKEN": "twilio Token here",
        "PHONE_NUMBER": "+19118675309",
        "MASTERS": ["list", "of", "ten", "digit", "phones"]
    }

The config keys are:

* `SID`: the Twilio account's SID
* `TOKEN`: the Twilio account's token
* `PHONE_NUMBER`: the twilio phone number that the bot should be texted at and will send texts from. Use +1 format.
* `MASTERS`: the list of phone numbers that the people in charge of the bot use. Do not use +1 format.