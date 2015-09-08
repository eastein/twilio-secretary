import os
import twilio_api


class TwilioActions(twilio_api.Twilio):

    def __init__(self):
        twilio_api.Twilio.__init__(self, os.getenv('SETTINGS_JSON'))

    def response_say(self, phrase):
        # TODO fix this insecure garbage, what a hack
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say>%s</Say>
        </Response>''' % phrase, 200
