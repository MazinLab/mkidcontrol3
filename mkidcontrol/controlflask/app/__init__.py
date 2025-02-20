import logging
import os
from flask import Flask, request, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_bootstrap import Bootstrap4
from flask_moment import Moment
from flask_babel import Babel, lazy_gettext as _l
import mkidcontrol.mkidredis as redis
from mkidcontrol.util import setup_logging
import threading
import queue
import time
import logging
import datetime
from astropy.io import fits
import click
import sys
import numpy as np

from mkidcontrol.config import REDIS_TS_KEYS

from mkidcontrol.config import Config

from mkidcore.config import load as loadcfg
import mkidcore.corelog
from mkidcore.corelog import create_log
from mkidcore.objects import Beammap

from mkidcontrol.packetmaster3.sharedmem import ImageCube

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = 'auth.login'
login.login_message = _l('Please log in to access this page.')
mail = Mail()
bootstrap = Bootstrap4()
moment = Moment()
babel = Babel()


def event_stream():
    for _, v in current_app.redis.listen('chat'):
        yield f'data: {v}\n\n'


class MessageAnnouncer:
    def __init__(self):
        self.listeners = []

    def listen(self):
        self.listeners.append(queue.Queue(maxsize=5))
        return self.listeners[-1]

    def announce(self, msg):
        # We go in reverse order because we might have to delete an element, which will shift the
        # indices backward
        # getLogger(__name__).info(f'Announcing {msg}')
        for i in reversed(range(len(self.listeners))):
            try:
                self.listeners[i].put_nowait(msg)
            except queue.Full:
                del self.listeners[i]

from mkidcontrol.controlflask.live_image import live_image_fetcher

def create_app(config_class=Config, cliargs=None):
    # TODO: Login db stuff and mail stuff can reasonably go
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    mail.init_app(app)
    bootstrap.init_app(app)
    moment.init_app(app)
    babel.init_app(app)
    redis.setup_redis(ts_keys=REDIS_TS_KEYS)
    app.redis = redis

    dashcfg = loadcfg(redis.read('gen2:dashboard-yaml'))
    app.base_dir = app.config.get('XKID_BASE_DIR')
    app.array_view_params = {'int_time': 1, 'min_cts': 0,
                             'max_cts': 2500, 'changed': False}

    app.latest_image = np.zeros_like(dashcfg.beammap.failmask, dtype=float)
    app.image_events = set()
    app.thread = threading.Thread(target=live_image_fetcher, args=(app, redis, dashcfg))
    app.thread.daemon = True
    app.thread.start()

    from .errors import bp as errors_bp
    app.register_blueprint(errors_bp)

    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .main import bp as main_bp
    app.register_blueprint(main_bp)

    from .api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    if not app.debug and not app.testing:
        if app.config['LOG_TO_STDOUT']:
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.INFO)
            app.logger.addHandler(stream_handler)
        else:
            setup_logging('controlDirector')

        app.logger.info('MKID Control startup')

    with app.app_context():
        db.create_all()

    return app


@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(current_app.config['LANGUAGES'])


from . import models
# try:
#     from ..app import models
# except:
#     from app import models

def create_dither_log(log_path):
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M")
    create_log('dither',
               logfile=os.path.join(log_path, 'dither_{}.log'.format(timestamp)),
               console=False, mpsafe=True, propagate=False,
               fmt='%(asctime)s %(message)s',
               level=mkidcore.corelog.DEBUG)
