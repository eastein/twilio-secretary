import uuid
import random
import time
import twilio_api
import os
import re
import copy

import json
import threading

from .datediff import differ


class SecretaryState(object):
    LOCK = threading.Lock()
    DIRTY = False

    # set of text formatted phone numbers
    SUBSCRIBERS = set()
    # list of tuples of time, text
    UPDATES = []
    # list of tuples of number, name
    NUMBER_MAP = []
    # polls are like this:
    """
    [
        {
            'question': 'text here?',
            'answers': ["answer1", "answer2"],
            'responses': {
                '312.......': <integer answer, translated from based on 1 to base 0>,
                ...
            }
        },
        ...
    ]
    """
    POLLS = []

    @classmethod
    def to_doc(cls):
        return {
            'subscribers': list(cls.SUBSCRIBERS),
            'updates': [list(u) for u in cls.UPDATES],
            'number_map': [list(nn) for nn in cls.NUMBER_MAP],
            'polls': cls.POLLS
        }

    @classmethod
    def from_doc(cls, doc):
        cls.SUBSCRIBERS = set(doc['subscribers'])
        cls.UPDATES = [tuple(u) for u in doc['updates']]
        cls.NUMBER_MAP = [tuple(nn) for nn in doc['number_map']]
        if 'polls' in doc:
            cls.POLLS = doc['polls']
        cls.DIRTY = False

    @classmethod
    def from_disk(cls):
        fn = SecretarySettings.get_settings()['STORE_JSON']
        if os.path.exists(fn):
            cls.from_doc(json.load(open(fn)))

    @classmethod
    def remove_subscriber(cls, number):
        with cls.LOCK:
            if number in cls.SUBSCRIBERS:
                cls.SUBSCRIBERS.remove(number)
                cls.DIRTY = True
                return True
            else:
                return False

    @classmethod
    def add_subscriber(cls, number):
        with cls.LOCK:
            if number in cls.SUBSCRIBERS:
                return False
            else:
                cls.SUBSCRIBERS.add(number)
                cls.DIRTY = True
                return True

    @classmethod
    def add_poll(cls, question, answers):
        with cls.LOCK:
            cls.POLLS.append({
                'question': question,
                'answers': answers,
                'responses': {},
            })
            cls.DIRTY = True
            return "Poll: %s\n%s\nReply with answer number to vote" % (question, '\n'.join([
                '%d: %s' % (i + 1, answers[i])
                for i in range(len(answers))
            ]))

    @classmethod
    def get_poll(cls):
        with cls.LOCK:
            if len(cls.POLLS) > 0:
                return copy.deepcopy(cls.POLLS[-1])
            else:
                return None

    @classmethod
    def answer_poll(cls, phone_number, answer_number):
        with cls.LOCK:
            if len(cls.POLLS) == 0:
                return 'There is no poll to answer. Text HELP for help.'

            poll = cls.POLLS[-1]

            if answer_number < 1 or answer_number > len(poll['answers']):
                return 'Poll answers range from %d to %d.. sorry.' % (1, len(poll['answers']))

            # 0 base
            answer_number -= 1

            existing_answer = poll['responses'].get(phone_number)

            if existing_answer is None:
                poll['responses'][phone_number] = answer_number
                cls.DIRTY = True
                return 'OK!'
            elif existing_answer == answer_number:
                return 'That was already your answer :)'
            else:
                poll['responses'][phone_number] = answer_number
                cls.DIRTY = True
                return 'OK, changed your answer!'

    @classmethod
    def subscriber_count(cls):
        with cls.LOCK:
            return len(cls.SUBSCRIBERS)

    @classmethod
    def add_update(cls, update_text):
        with cls.LOCK:
            cls.UPDATES.append((time.time(), update_text))
            cls.DIRTY = True

    @classmethod
    def format_update(cls, update):
        ts, text = update
        return '%s ago: %s' % (differ(int(time.time() - ts)), text)

    @classmethod
    def current_update(cls):
        if len(cls.UPDATES) == 0:
            return 'There is no info saved right now.'
        else:
            with cls.LOCK:
                return cls.format_update(cls.UPDATES[-1])

    @classmethod
    def recent_updates(cls, count=3):
        with cls.LOCK:
            updates = cls.UPDATES[-count:]
            updates.reverse()
            return updates

    @classmethod
    def get_number_name(cls, number, generate_name=True):
        with cls.LOCK:
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
            cls.DIRTY = True

            return name

    @classmethod
    def rename(cls, old_name, new_name):
        with cls.LOCK:
            old_name = old_name.lower()
            for i in range(len(cls.NUMBER_MAP)):
                existing_number, existing_name = cls.NUMBER_MAP[i]
                if old_name.lower() == existing_name.lower():
                    cls.NUMBER_MAP[i] = (existing_number, new_name)
                    cls.DIRTY = True
                    return True
            return False

    @classmethod
    def name(cls, number, name):
        for i in range(len(cls.NUMBER_MAP)):
            existing_number, existing_name = cls.NUMBER_MAP[i]
            if number == existing_number:
                cls.NUMBER_MAP[i] = (existing_number, name)
                cls.DIRTY = True
                return True
        cls.NUMBER_MAP.append((number, name))
        cls.DIRTY = True
        return True

    @classmethod
    def sanitize_number(cls, num):
        num = re.compile('[^0-9]').sub('', num)
        nlen = len(num)
        if nlen < 11:
            return num

        if nlen == 11 and num[0] == '1':
            return num[1:]

        return num

    @classmethod
    def get_name_number(cls, name):
        for (stored_number, stored_name) in cls.NUMBER_MAP:
            if name.lower() == stored_name.lower():
                return stored_number


class SecretarySettings(object):
    SETTINGS_DATA = None
    SETTINGS_RDLOCK = threading.Lock()

    @classmethod
    def get_settings(cls):
        if cls.SETTINGS_DATA is None:
            with cls.SETTINGS_RDLOCK:
                cls.SETTINGS_DATA = json.load(open(os.getenv('SETTINGS_JSON')))
        return cls.SETTINGS_DATA


class TwilioSecretary(twilio_api.Twilio):

    def __init__(self):
        twilio_api.Twilio.__init__(self, SecretarySettings.get_settings())

    def write_if_dirty(self):
        with SecretaryState.LOCK:
            if SecretaryState.DIRTY:
                fn = self.settings['STORE_JSON']
                fn_inprog = fn + '.inprog-%s' % str(uuid.uuid4())
                fh = open(fn_inprog, 'w')

                json.dump(SecretaryState.to_doc(), fh)
                fh.close()

                os.rename(fn_inprog, fn)
                SecretaryState.DIRTY = False

                print 'wrote json to disk'
            else:
                print 'nothing to write, no change'

    def broadcast_msg(self, argument):
        sent = 0
        failed_send = 0
        for sub_number in SecretaryState.SUBSCRIBERS:
            try:
                self.send_sms(sub_number, argument)
                sent += 1
            except:
                # TODO Log exception
                failed_send += 1
        send_msg = "Sent to %d subscribers." % sent
        if failed_send > 0:
            send_msg += " Failed to send to %d." % failed_send

        return send_msg

    def get_descriptor(self, phone_number):
        sub_name = SecretaryState.get_number_name(phone_number, generate_name=False)
        if sub_name is None:
            return phone_number
        else:
            return '%s (%s)' % (sub_name, phone_number)

    def poll_summary(self, detailed=False):
        current_poll = SecretaryState.get_poll()
        if current_poll is None:
            return 'There is no poll to have responses.'

        n_answers = len(current_poll['answers'])
        respondents = [list() for i in range(n_answers)]
        for phone_number, answer_number in current_poll['responses'].items():
            descriptor = self.get_descriptor(phone_number)
            respondents[answer_number].append(descriptor)

        if detailed:
            response_text = '\n'.join([
                '%d: %s: %s' % (anum + 1, current_poll['answers'][anum],
                                ', '.join(respondents[anum]) if respondents[anum] else 'nobody')
                for anum in range(n_answers)
            ])
        else:
            response_text = '\n'.join([
                '%d: %s: %d responses' % (anum + 1, current_poll['answers'][anum], len(respondents[anum]))
                for anum in range(n_answers)
            ])

        return '%s\n%s' % (current_poll['question'], response_text)

    def on_sms(self, from_number, text):
        text = text.strip()

        print 'hey handling text from %s, text is %s' % (from_number, text)

        send_help = False
        is_admin = self.is_master(from_number)

        tokens = text.split(' ', 1)
        if len(tokens) < 1 or tokens[0].lower() == 'help':
            send_help = True

        if not send_help:
            command = re.compile('[^a-zA-Z0-9]').sub('', tokens[0].lower())

            argument = None
            if len(tokens) == 2:
                argument = tokens[1]

            if command in ['update', 'tell', 'rename', 'name', 'subscribers', 'poll', 'responses']:
                if not is_admin:
                    self.send_sms(from_number, "You can't use that feature, sorry.")
                    return

                if command == 'update':
                    if argument is None:
                        self.send_sms(from_number, "Hey, give some text after Update to send an update.")
                        return
                    SecretaryState.add_update(argument)

                    reply_msg = self.broadcast_msg("Broadcast: " + argument)
                    self.send_sms(from_number, reply_msg)
                    return
                elif command == 'subscribers':
                    subscribers = []
                    for sub_number in SecretaryState.SUBSCRIBERS:
                        sub_name = self.get_descriptor(sub_number)
                        subscribers.append(sub_name)

                    if not subscribers:
                        self.send_sms(from_number, 'There are no subscribers.')
                        return

                    sub_text = subscribers[0]
                    for subscriber in subscribers[1:]:
                        if len(sub_text) + len(subscriber) + 2 > 160:
                            self.send_sms(from_number, sub_text)
                            sub_text = subscriber
                        else:
                            sub_text += ', ' + subscriber
                    self.send_sms(from_number, sub_text)
                    return
                elif command == 'poll':
                    if argument is None:
                        self.send_sms(from_number, "Usage: poll question text? answer1 / answer2/answer3")
                        return

                    last_q = argument.rfind('?')
                    question = argument[:last_q + 1]
                    answers = [a.strip() for a in argument[last_q + 1:].split('/')]
                    poll_msg = SecretaryState.add_poll(question, answers)
                    reply_msg = self.broadcast_msg(poll_msg)
                    self.send_sms(from_number, reply_msg)
                    return
                elif command == 'responses':
                    detailed = False
                    if argument:
                        if argument.strip().lower() == 'detail':
                            detailed = True
                    self.send_sms(from_number, self.poll_summary(detailed=detailed))
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
                        number = SecretaryState.sanitize_number(number)
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
            elif re.compile('^[0-9]+$').match(command):
                answer_number = int(command)
                self.send_sms(from_number, SecretaryState.answer_poll(from_number, answer_number))
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
