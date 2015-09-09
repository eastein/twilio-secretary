from flask import request, Flask, render_template

from .secretary import TwilioSecretary, SecretaryState

SecretaryState.from_disk()

app = Flask(__name__)


@app.route('/')
def root():
    return 'Hello, you have reached a place you do not belong. Revel in your rebellious nature.'


@app.route('/inbound-sms/', methods=['POST'])
def inbound_sms():
    try:
        tws = TwilioSecretary()
        if not tws.check_sid(request.form['AccountSid']):
            return 'sorry but i dunno who you are buddy', 403

        tws.on_sms(request.form['From'], request.form['Body'])
        tws.write_if_dirty()
        return "OK", 200
    except:
        import traceback
        traceback.print_exc()


@app.route('/inbound-call/', methods=['POST'])
def inbound_call():
    try:
        tws = TwilioSecretary()

        return '<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="woman">%s. To find out more, text this number.</Say></Response>' % SecretaryState.current_update(), 200
    except:
        import traceback
        traceback.print_exc()


@app.route('/updates/')
def updates():
    try:
        updates = [SecretaryState.format_update(update) for update in SecretaryState.recent_updates(count=5)]
        tws = TwilioSecretary()
        return render_template('latest.html', phone_number=tws.settings['PHONE_NUMBER'], updates=updates,
                               master_name=tws.settings['MASTERS_NAME'],
                               subscriber_count=SecretaryState.subscriber_count())
    except:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    app.run('0.0.0.0')
