"""
TODO: Condense/make more sensible validation handling
TODO: Try to remove hardcoding as best as possible

TODO: Integrate Jeb's flask changes
TODO: Incorporate power on/off into the monitoring/control panel
 - Related: Fix errors if redis range is empty (i.e. no values reported since the device was off)

TODO (FOR ALL DEVICES): Enable graceful power on/off handling (i.e. don't error out if device is purposely switched off)

Note to the user, the actual body of the app and the stuff that makes everything 'go' is in /mkidcontrol/controlflask/app/
"""
from mkidcontrol.controlflask.app import create_app, db, cli
from mkidcontrol.controlflask.app.models import User, Post, Message, Notification, Task
from mkidcontrol.util import setup_logging

import sys

log = setup_logging('controlDirector')

cliargs = sys.argv

app = create_app(cliargs=cliargs)
cli.register(app)


@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Post': Post, 'Message': Message,
            'Notification': Notification, 'Task': Task}


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)
