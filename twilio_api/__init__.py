from twilio.rest import TwilioRestClient
import json

class Twilio(object) :
    def process_number(self, num) :
        num = str(num)
        num = num.replace('-', '').replace(' ', '').replace('(', '').replace(')', '').replace('+', '')
        if len(num) == 10 :
            # behold my amero-centrism
            num = '1' + num
        return '+' + num

    def __init__(self, settings_filename=None) :
        if settings_filename is None:
            raise RuntimeError("Need a settings filename.")
        self.settings = json.load(open(settings_filename))
        self.client = TwilioRestClient(self.settings['SID'], self.settings['TOKEN'])

    def send_sms(self, to, text) :
        if not isinstance(to, list):
            to = [to]

        for to_number in to:
            self.client.messages.create(body=text, to=self.process_number(to_number),
                                        from_=self.settings['PHONE_NUMBER'])

    def check_sid(self, sid):
        # ugh constant time attack TODO
        return sid == self.settings['SID']