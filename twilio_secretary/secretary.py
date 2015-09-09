import uuid
import random
import time
import twilio_api
import os

from .datediff import differ


class SecretaryState(object):
    # oh jeez man don't use class members as a state store it's not persistent *crying*
    # oh man oh jeez TODO
    SUBSCRIBERS = set()
    UPDATES = []
    # list of tuples of number, name
    NUMBER_MAP = []

    @classmethod
    def remove_subscriber(cls, number):
        if number in cls.SUBSCRIBERS:
            cls.SUBSCRIBERS.remove(number)
            return True
        else:
            return False

    @classmethod
    def add_subscriber(cls, number):
        if number in cls.SUBSCRIBERS:
            return False
        else:
            cls.SUBSCRIBERS.add(number)
            return True

    @classmethod
    def add_update(cls, update_text):
        cls.UPDATES.append((time.time(), update_text))

    @classmethod
    def format_update(cls, update):
        ts, text = update
        return '%s ago: %s' % (differ(int(time.time() - ts)), text)

    @classmethod
    def current_update(cls):
        if len(cls.UPDATES) == 0:
            return 'There is no info saved right now.'
        else:
            return cls.format_update(cls.UPDATES[-1])

    @classmethod
    def recent_updates(cls, count=3):
        updates = cls.UPDATES[-count:]
        updates.reverse()
        return updates

    @classmethod
    def get_number_name(cls, number, generate_name=True):
        seen_names = set()
        for (stored_number, stored_name) in cls.NUMBER_MAP:
            if number == stored_number:
                return stored_name
            seen_names.add(stored_name.lower())

        if not generate_name:
            return None

        namefrags = ['red', 'pup', 'rocket', 'turtle', 'blue']
        random.shuffle(namefrags)
        # ok we didn't get a name for this person.
        name = None
        for i in range(1, 1000):
            for prefix in namefrags:
                potential_name = '%s%d' % (prefix, i)
                if potential_name not in seen_names:
                    name = potential_name
                    break
            if name is not None:
                break

        if name is None:
            name = str(uuid.uuid4())[0:8]

        cls.NUMBER_MAP.append((number, name))

        return name

    @classmethod
    def rename(cls, old_name, new_name):
        old_name = old_name.lower()
        for i in range(len(cls.NUMBER_MAP)):
            existing_number, existing_name = cls.NUMBER_MAP[i]
            if old_name.lower() == existing_name.lower():
                cls.NUMBER_MAP[i] = (existing_number, new_name)
                return True
        return False

    @classmethod
    def name(cls, number, name):
        for i in range(len(cls.NUMBER_MAP)):
            existing_number, existing_name = cls.NUMBER_MAP[i]
            if number == existing_number:
                cls.NUMBER_MAP[i] = (existing_number, name)
                return True
        cls.NUMBER_MAP.append((number, name))
        return True

    @classmethod
    def get_name_number(cls, name):
        for (stored_number, stored_name) in cls.NUMBER_MAP:
            if name.lower() == stored_name.lower():
                return stored_number


class TwilioSecretary(twilio_api.Twilio):

    def __init__(self):
        twilio_api.Twilio.__init__(self, os.getenv('SETTINGS_JSON'))

    def on_sms(self, from_number, text):
        print 'hey handling text from %s, text is %s' % (from_number, text)

        send_help = False
        is_admin = self.is_master(from_number)

        tokens = text.split(' ', 1)
        if len(tokens) < 1 or tokens[0].lower() == 'help':
            send_help = True

        if not send_help:
            command = tokens[0].lower()
            argument = None
            if len(tokens) == 2:
                argument = tokens[1]

            if command in ['update', 'tell', 'rename', 'name', 'subscribers']:
                if not is_admin:
                    self.send_sms(from_number, "You can't use that feature, sorry.")
                    return

                if command == 'update':
                    if argument is None:
                        self.send_sms(from_number, "Hey, give some text after Update to send an update.")
                        return
                    SecretaryState.add_update(argument)
                    sent = 0
                    for sub_number in SecretaryState.SUBSCRIBERS:
                        self.send_sms(sub_number, "Broadcast: " + argument)
                        sent += 1
                    self.send_sms(from_number, "Sent update to %d subscribers." % sent)
                    return
                elif command == 'subscribers':
                    subscribers = []
                    for sub_number in SecretaryState.SUBSCRIBERS:
                        sub_name = SecretaryState.get_number_name(sub_number, generate_name=False)
                        if sub_name is None:
                            sub_name = sub_number
                        else:
                            sub_name = '%s (%s)' % (sub_name, sub_number)
                        subscribers.append(sub_name)

                    if not subscribers:
                        self.send_sms(from_number, 'There are no subscribers.')
                        return

                    sub_text = subscribers[0]
                    for subscriber in subscribers[1:]:
                        if sub_text + len(subscriber) + 2 > 160:
                            self.send_sms(from_number, sub_text)
                            sub_text = subscriber
                        else:
                            sub_text += ', ' + subscriber
                    self.send_sms(from_number, sub_text)
                    return
                elif command in ['tell', 'rename', 'name']:
                    arguments_needed = {
                        'tell': "name and a message",
                        'rename': "oldname and newname",
                        'name': 'number and name'
                    }[command]

                    if argument is None:
                        self.send_sms(from_number, "Send %s" % arguments_needed)
                        return
                    frags = argument.split(' ', 1)
                    if len(frags) == 1:
                        self.send_sms(from_number, "You have to send %s." % arguments_needed)
                        return

                    if command == 'tell':
                        name, text = frags
                        number = SecretaryState.get_name_number(name)
                        if number is None:
                            self.send_sms(from_number, "Sorry, I don't know who %s is." % name)
                            return

                        self.send_sms(number, text)
                        return
                    elif command == 'rename':
                        oldname, newname = frags
                        newname = newname.split(' ', 1)[0]  # in case we were silly and sent a name with a space in it
                        if SecretaryState.rename(oldname, newname):
                            self.send_sms(from_number, "Renamed %s to %s." % (oldname, newname))
                        else:
                            self.send_sms(from_number, "I don't know who %s is." % oldname)
                        return
                    elif command == 'name':
                        number, name = frags
                        name = name.split(' ', 1)[0]  # in case we have a space in a name, cut it
                        if SecretaryState.name(number, name):
                            self.send_sms(from_number, "Stored name %s for number %s." % (name, number))
                        return
            elif command == 'msg':
                if argument is None:
                    self.send_sms(from_number, "Hey, give some text after MSG to send a message.")
                else:
                    from_name = SecretaryState.get_number_name(from_number)
                    self.send_sms_to_masters("From %s (%s): %s" % (from_name, from_number, argument))
                    self.send_sms(from_number, "Passed that along for you!")
                return
            elif command == 'info':
                self.send_sms(from_number, SecretaryState.current_update())
                return
            elif command == 'subscribe':
                if SecretaryState.add_subscriber(from_number):
                    self.send_sms(from_number, "Subscribed. Current info: %s" % SecretaryState.current_update())
                else:
                    self.send_sms(from_number, "You are already subscribed!")
                return
            elif command == 'stop':
                if SecretaryState.remove_subscriber(from_number):
                    self.send_sms(from_number, "You are now unsubscribed!")
                else:
                    self.send_sms(from_number, "You are already unsubscribed!")
                return

        help_text = 'Text options:\nSUBSCRIBE (Get text updates)\nMSG [Followed by message for %s]\nSTOP (Stop text updates)' % self.settings[
            'MASTERS_NAME']

        if is_admin:
            help_text += '\nUPDATE [Followed by broadcast message]\nTELL [name] [message]\nRENAME [oldname] [newname]\nNAME [number] [name]\nSUBSCRIBERS (lists subscribers)'

        print 'sending help to %s' % from_number
        self.send_sms(from_number, help_text)

    def is_master(self, number):
        return number in self.settings['MASTERS']

    def send_sms_to_masters(self, text):
        self.send_sms(self.settings['MASTERS'], text)
