"""
3 January 2023
Author: Noah Swimmer

Agent for controlling the CONEX-AG-M100D Piezo Motor Mirror Mount (https://www.newport.com/p/CONEX-AG-M100D) that serves
as a tip/tilt mirror for XKID aiding in both alignment and dithering.

Axis syntax is: U -> rotation around the y-axis, V -> rotation around the x-axis

Commands sent to conex for dithering/moving are dicts converted to strings via the json.dumps() to conveniently send
complicated dicts over redis pubsub connections
"""

import logging
import os
import sys
import json
import numpy as np
import time
import threading
from serial import SerialException
from datetime import datetime

import mkidcore
from mkidcore.corelog import create_log, getLogger
from mkidcontrol.mkidredis import RedisError
import mkidcontrol.mkidredis as redis
import mkidcontrol.util as util
from mkidcontrol.commands import COMMANDSCONEX, LakeShoreCommand
from mkidcontrol.devices import Conex
from mkidcontrol.agents.xkid.observingAgent import OBSERVING_EVENT_KEY


logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("conexAgent")

QUERY_INTERVAL = 1
TIMEMOUT = 2  # Timeout for query request

STATUS_KEY = "status:device:conex:status"
SN_KEY = "status:device:conex:sn"
FIRMWARE_KEY = "status:device:conex:firmware"

MOVE_COMMAND_KEY = "conex:move"
DITHER_COMMAND_KEY = "conex:dither"
STOP_COMMAND_KEY = "conex:stop"

ENABLE_CONEX_KEY = "device-settings:conex:enabled"

CONEX_CONTROLLER_STATUS_KEY = "status:device:conex:controller-status"
CONEX_CONTROLLER_STATE_KEY = "status:device:conex:controller-state"
CONEX_X = "status:device:conex:position-x"
CONEX_Y = "status:device:conex:position-y"

CONEX_REF_X_KEY = "instrument:conex-ref-x"
CONEX_REF_Y_KEY = "instrument:conex-ref-y"
PIXEL_REF_X_KEY = "instrument:pixel-ref-x"
PIXEL_REF_Y_KEY = "instrument:pixel-ref-y"

OBSERVING_REQUEST_CHANNEL = 'command:observation:request'
OBSERVING_KEYS = (OBSERVING_REQUEST_CHANNEL, OBSERVING_EVENT_KEY)

CONEX_COMMANDS = tuple([MOVE_COMMAND_KEY, DITHER_COMMAND_KEY, STOP_COMMAND_KEY])

SETTING_KEYS = tuple(COMMANDSCONEX.keys())
COMMAND_KEYS = tuple([f"command:{key}" for key in list(SETTING_KEYS) + list(CONEX_COMMANDS)]) + OBSERVING_KEYS

DATA_PATH_DIR_KEY = "paths:data-dir"
DITHER_LOG_KEY = "paths:logs-folder-name"


class ConexController:
    """
    The ConexController manages the Conex() base class

    It also implements a thread safe dither routine

    Possible states:
    - "Unknown"
    - "Offline"
    - "Idle"
    - "Stopped"
    - "Moving"
    - "Dither"
    - "Error"
    """

    def __init__(self, port, redis=None):
        self.conex = Conex(port=port)
        self._completed_dithers = []  # list of completed dithers
        self._movement_thread = None  # thread for moving/dithering
        self._halt_dither = True
        self._rlock = threading.RLock()
        self._startedMove = 0  # number of times start_move was called (not dither). Reset in queryMove and start_dither
        self._completedMoves = 0  # number of moves completed (not dither)
        self.thread_pool = np.asarray([])
        self.redis = redis

        self.state = ('Unknown', 'Unknown')
        try:
            if self.conex.ready():
                self._updateState('Idle')
        except:
            pass
        self.cur_status = self.status()

    def _updateState(self, newState):
        with self._rlock:
            self.state = (self.state[1], newState)
            log.info(f"{CONEX_CONTROLLER_STATE_KEY}, {json.dumps(self.state)}")
            self.redis.publish(CONEX_CONTROLLER_STATE_KEY, json.dumps(self.state))

    def _update_cur_status(self, s):
        with self._rlock:
            self.cur_status = s
            log.info(f"{CONEX_CONTROLLER_STATUS_KEY}, {s}")
            self.redis.publish(CONEX_CONTROLLER_STATUS_KEY, s)

    def status(self):
        pos = (np.NaN, np.NaN)
        status = ''
        try:
            status = self.conex.status()
            pos = self.conex.position()
            log.debug(f"Conex: {status[1]} @ pos {pos}")
            self.redis.store({CONEX_X: pos[0], CONEX_Y: pos[1]})
        except (IOError, SerialException):
            log.error('Unable to get conex status', exc_info=True)
            self._halt_dither = True
            self._updateState('Offline')
        log.info(f"CONEX X: {pos[0]}, CONEX Y: {pos[1]}")
        return json.dumps({'state': self.state, 'pos': pos, 'conexstatus': status[2], 'limits': self.conex.limits})

    def do_go_to(self, x, y):
        log.info(f"Starting move to ({x}, {y})")
        started = self.start_move(x, y)
        if started:
            self.thread_pool = self.thread_pool[[t.is_alive() for t in self.thread_pool]]
            thread = threading.Thread(target=self._wait4move, name="Move wait thread")
            thread.daemon = True
            self.thread_pool=np.append(self.thread_pool,thread)
            thread.start()

    def do_dither(self, dither_dict):
        log.info("Starting dither")
        started = self.start_dither(dither_dict)
        if started:
            self.thread_pool = self.thread_pool[[t.is_alive() for t in self.thread_pool]]
            thread = threading.Thread(target=self._wait4dither, name="Dithering wait thread")
            thread.daemon = True
            self.thread_pool = np.append(self.thread_pool, thread)
            thread.start()

    def do_halt(self):
        log.info('Conex Movement Stopped by user.')
        s = self.stop(wait=False)  # blocking
        with self._rlock:
            self._update_cur_status(s)

    def _wait4dither(self):
        d = self.queryDither()
        with self._rlock:
            self._update_cur_status(d['status'])
        pos_tolerance = 0.003
        while not d['completed']:
            time.sleep(1)
            try:
                d = self.queryDither()

                oldPos = json.loads(self.cur_status)['pos']
                newPos = json.loads(d['status'])['pos']
                posNear = (np.abs(newPos[0] - oldPos[0]) <= pos_tolerance) and (
                        np.abs(newPos[1] - oldPos[1]) <= pos_tolerance)
                with self._rlock:
                    self._update_cur_status(d['status'])
                if not posNear:  # If the position changed
                    pass
            except:
                d = {'completed': False}
        self.logdither(d)
        log.info('Finished dither')

    def _wait4move(self):
        d = self.queryMove()
        self._update_cur_status(d['status'])
        while not d['completed']:
            time.sleep(.05)
            try:
                d = self.queryMove()
                self._update_cur_status(d['status'])
            except:
                d={'completed':False}
        log.info('Finished conex GOTO')

    def queryMove(self):
        """
        Checks to see if move completed

        It should be thread safe. Even if you hit the move button several times really fast

        OUTPUTS:
            dictionary {'completed':True/False, 'status':self.cur_status}
        """
        if self._completedMoves > 0:  # don't lock if no moves completed. Reading is thread safe
            with self._rlock:  # if at least one move completed then lock
                if self._completedMoves > 0:  # need to check again for thread safety (maybe started two moves but only 1 completed)
                    self._completedMoves -= 1
                    self._startedMove -= 1
                    self._startedMove = max(0, self._startedMove)
                    return {'completed': True, 'status': self.cur_status}
        return {'completed': False, 'status': self.cur_status}

    def queryDither(self):
        """
        returns the dictionary containing information about an ongoing or completed dither

        keys:
            status - The current status of the conex manager
            estTime - ?? Not implemented right now
            dither - A dictionary containing the oldest completed dither that hasn't been popped yet
                     see dither() output
                     If no completed dithers then None
            completed - True or False
        """
        dith = None
        estTime = 0
        completed = False
        if len(self._completed_dithers) > 0:  # Reading is thread safe
            with self._rlock:  # only lock if at least one dither completed
                try:
                    dith = self._completed_dithers.pop(0)
                    completed = True
                except IndexError:
                    pass
        if dith is None:  # check if a dither was popped
            estTime = datetime.utcnow().timestamp() + 1  # estimated unix time of when dither will complete
        return {'status': self.cur_status, 'estTime': estTime, 'dither': dith, 'completed': completed}

    def stop(self, wait=False):
        """
        stops the current movement or dither

        if wait is False then it forcibly writes to the conex to tell it to stop motion

        after that it waits for the movement thread to finish
        """
        log.debug('stopping conex')

        if self._movement_thread is not None and self._movement_thread.is_alive():
            with self._rlock:
                self._halt_dither = True
                if not wait:
                    self.conex.stop()  # puts conex in ready state so that _movement thread will finish
                self._updateState('Stopped')
                self._update_cur_status(self.status())
            self._movement_thread.join()  # not in rlock
            with self._rlock:
                self._update_cur_status(self.status())  # could change in other thread
        else:
            with self._rlock:
                self._update_cur_status(self.status())
        return self.cur_status

    def start_dither(self, dither_dict):
        """
        Starts dither in a new thread
        """
        log.debug('starting dither')
        self.stop(wait=False)  # stop whatever we were doing before (including a previous dither)
        with self._rlock:
            self._update_cur_status(self.status())
            if json.loads(self.cur_status)['state'] == 'Offline': return False
            self._halt_dither = False
            self._startedMove = 0
        self._preDitherPos = json.loads(self.cur_status)['pos']
        self._movement_thread = threading.Thread(target=self.dither_two_point, args=(dither_dict,), name="Dithering thread")
        self._movement_thread.daemon = True
        self._movement_thread.start()
        return True

    def dither_two_point(self, dither_dict):
        """
        INPUTS:
            dither_dict - dictionary with keys:
                        name: (str) Name of dither, will be passed to observingAgent for storage & logging
                        startx: (float) start x loc in conex degrees
                        endx: (float) end x loc
                        starty: (float) start y loc
                        endy: (float) end y loc
                        n: (int) number of steps in square grid
                        t: (float) dwell time in seconds
                        subStep: (float) degrees to offset for subgrid pattern
                        subT: (float) dwell time for subgrid

                        subStep and subT are optional

        appends a dictionary to the self._completed_dithers attribute
            keys - same as dither_dict but additionally
                   it has keys (xlocs, ylocs, startTimes, endTimes)

        """
        points = dither_two_point_positions(dither_dict['startx'], dither_dict['starty'], dither_dict['stopx'],
                                            dither_dict['stopy'], dither_dict['n'])
        len_dith = len(points)

        subDither = 'subStep' in dither_dict.keys() and dither_dict['subStep'] > 0 and \
                    'subT' in dither_dict.keys() and dither_dict['subT'] > 0

        x_locs = []
        x_locs_reported = []
        y_locs = []
        y_locs_reported = []
        startTimes = []
        endTimes = []
        for i, p in enumerate(points):
            # TODO: DEBUG WHY Reported values are not the same as target values
            startTime, endTime = self._dither_move(p[0], p[1], dither_dict['t'], dither_dict['name'], i, len_dith)
            if startTime is not None:
                x_locs.append(p[0])
                y_locs.append(p[1])
                x_locs_reported.append(json.loads(self.cur_status)['pos'][0])
                y_locs_reported.append(json.loads(self.cur_status)['pos'][1])
                startTimes.append(startTime)
                endTimes.append(endTime)
            if self._halt_dither: break

            # do sub dither if neccessary
            if subDither:
                x_sub = [-dither_dict['subStep'], 0, dither_dict['subStep'], 0]
                y_sub = [0, dither_dict['subStep'], 0, -dither_dict['subStep']]
                for i in range(len(x_sub)):
                    if self.conex.in_bounds((p[0] + x_sub[i], p[1] + y_sub[i])):
                        startTime, endTime = self._dither_move(p[0] + x_sub[i], p[1] + y_sub[i], dither_dict['subT'])
                        if startTime is not None:
                            x_locs.append(json.loads(self.cur_status)['pos'][0])
                            y_locs.append(json.loads(self.cur_status)['pos'][1])
                            startTimes.append(startTime)
                            endTimes.append(endTime)
                    if self._halt_dither: break
            if self._halt_dither: break

        # Dither has completed (or was stopped prematurely)
        if not self._halt_dither:  # no errors and not stopped
            self.move(*self._preDitherPos)
            with self._rlock:
                if not self._halt_dither:  # still no errors nor stopped
                    self._updateState("Idle")
                self._update_cur_status(self.status())

        dith = dither_dict.copy()
        dith['xlocs'] = x_locs  # could be empty if errored out or stopped too soon
        dith['xlocs_reported'] = x_locs_reported  # could be empty if errored out or stopped too soon
        dith['ylocs'] = y_locs
        dith['ylocs_reported'] = y_locs_reported
        dith['startTimes'] = startTimes
        dith['endTimes'] = endTimes

        # self.logdither(dith)
        with self._rlock:
            self._completed_dithers.append(dith)

    def _dither_move(self, x, y, t, name, move_num, seq_len):
        """
            Helper function for dither()

            The state after this function call will be one of:
                "error: ..." - If there there was an error during the move
                "processing" - If everything worked
        """
        polltime = 0.1  # wait for dwell time but have to check if stop was pressed periodically
        self.move(x, y)
        time.sleep(0.25)
        if self._halt_dither: return None, None  # Stopped or error during move
        self._updateState(f"Dither dwell for {t} seconds")
        # dwell at position
        startTime = datetime.utcnow().timestamp()
        obs_dict = {'name': name, 'type': 'dwell',
                       'seq_i': move_num, 'seq_n': seq_len,
                       'duration': t, 'start': startTime}
        self.redis.publish("command:observation-request", json.dumps(obs_dict), store=False)
        dwell_until = startTime + t
        endTime = datetime.utcnow().timestamp()

        with self._rlock:
            self._update_cur_status(self.status())
        while self._halt_dither == False and endTime < dwell_until:
            # TODO CHECK FOR "OBSERVATION STOPPED"
            sleep = min(polltime, dwell_until - endTime)
            time.sleep(max(sleep, 0))
            endTime = datetime.utcnow().timestamp()
        time.sleep(1) # NB Give the observing agent extra time so that you don't start moving before the dwell step ends
        return startTime, endTime

    def start_move(self, x, y):
        """
        Starts move in new thread
        """
        self.stop(wait=False)  # If the user wants to move, then forcibly stop whatever we were doing before (indcluding dithers)
        with self._rlock:
            self._update_cur_status(self.status())
            if json.loads(self.cur_status)['state'] == 'Offline': return False
            self._startedMove += 1
        self._movement_thread = threading.Thread(target=self.move, args=(x, y,),
                                       name=f'Move to ({x}, {y})')
        self._movement_thread.daemon = True
        self._movement_thread.start()

        return True

    def move(self, x:float, y:float):
        """
        Tells conex to move and collects errors
        """
        x = float(x)
        y = float(y)
        self._updateState(f'Moving to {x}, {y}')
        try:
            self.conex.move((x, y), blocking=True)  # block until conex is done moving (or stopped)
            self._updateState('Idle')
            log.debug(f'moved to ({x}, {y})')
        except (IOError, SerialException) as e:  # on timeout it raise IOError
            self._updateState(f'Error: move to {x:.2f}, {y:.2f} failed')
            self._halt_dither = True
            log.error('Error on move', exc_info=True)
        except:  # I dont think this should happen??
            self._updateState(f'Error: move to {x:.2f}, {y:.2f} failed')
            self._halt_dither = True
            log.error('Unexpected error on move', exc_info=True)
        if self._startedMove > 0:
            with self._rlock:
                self._update_cur_status(self.status())
                self._completedMoves += 1

    def logdither(self, d):
        print("LOGGING DITHER!!")
        state = json.loads(d['status'])['state'][1]
        if state == 'Stopped':
            log.error("Dither aborted early by user STOP. Conex Status=" + str(json.loads(d['status'])['conexstatus']))
        elif state.startswith('Error'):
            log.error("Dither aborted from error. Conex State=" + state + " Conex Status=" + str(json.loads(d['status'])['conexstatus']))
        dither_dict = d['dither']
        msg = "Dither Path: ({}, {}) --> ({}, {}), {} steps {} seconds".format(
            dither_dict['startx'], dither_dict['starty'],
            dither_dict['stopx'], dither_dict['stopy'],
            dither_dict['n'], dither_dict['t'])
        if 'subStep' in dither_dict.keys() and dither_dict['subStep'] > 0 and \
            'subT' in dither_dict.keys() and dither_dict['subT'] > 0:
            msg = msg + " +/-{} for {} seconds".format(dither_dict['subStep'], dither_dict['subT'])
        msg = msg + f"\n\tstarts={dither_dict['startTimes']}\n\tends={dither_dict['endTimes']}\n\t" \
                    f"path={list(zip(dither_dict['xlocs'], dither_dict['ylocs']))}\n\t" \
                    f"reported_path={list(zip(dither_dict['xlocs_reported'], dither_dict['ylocs_reported']))}"
        getLogger('dither').info(msg)


def dither_two_point_positions(start_x, start_y, stop_x, stop_y, user_n_steps, single_pixel_move=0.015):
    if user_n_steps == 1:
        log.error('Number of steps must be greater than one!')
        return
    if stop_y == start_y and stop_x == start_x:
        log.error('No movement specified in x or y')
        return

    n_steps = user_n_steps - 1
    points = []
    interval_x = ((stop_x - (0.5 * single_pixel_move)) - start_x) / (n_steps / 2)
    interval_y = ((stop_y - (0.5 * single_pixel_move)) - start_y) / (n_steps / 2)

    x_list = np.arange(start_x, stop_x, interval_x)
    y_list = np.arange(start_y, stop_y, interval_y)
    if start_x == stop_x:
        x_list = np.zeros(n_steps)
    if start_y == stop_y:
        y_list = np.zeros(n_steps)

    offset_x = np.round(x_list + (interval_x / 2 + 0.5 * single_pixel_move), 3)
    offset_y = np.round(y_list + (interval_y / 2 + 0.5 * single_pixel_move), 3)
    x_grid = np.round(np.sort(np.concatenate((x_list, offset_x[offset_x <= round(stop_x, 4)]))), 3)
    y_grid = np.round(np.sort(np.concatenate((y_list, offset_y[offset_y <= round(stop_y, 4)]))), 3)
    cycle = 1

    if not (np.all(x_grid == 0) or np.all(y_grid == 0)):
        points.append((start_x, start_y))

    while cycle <= n_steps:
        for i in range(cycle + 1):
            rev = cycle - i
            points.append((x_grid[i], y_grid[rev]))
        cycle += 1
    cycle = 1
    second_points = []
    while cycle <= (n_steps - 1):
        for i in range(cycle + 1):
            rev = cycle - i
            second_points.insert(0, (x_grid[-1 - i], y_grid[-1 - rev]))
        cycle += 1
    points = points + second_points
    if not (np.all(x_grid == 0) or np.all(y_grid == 0)):
        points.append((x_grid[-1], y_grid[-1]))
    return points


if __name__ == "__main__":

    redis.setup_redis()
    util.setup_logging('conexAgent')

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M")
    create_log('dither',
               logfile=os.path.join(redis.read(DATA_PATH_DIR_KEY), redis.read(DITHER_LOG_KEY), f'dither_{timestamp}.log'),
               console=False, mpsafe=True, propagate=False,
               fmt='%(asctime)s %(message)s',
               level=mkidcore.corelog.DEBUG)

    try:
        cc = ConexController(port='/dev/conex', redis=redis)
        redis.store({SN_KEY: cc.conex.id_number})
        redis.store({FIRMWARE_KEY: cc.conex.firmware})
        redis.store({STATUS_KEY: "OK"})
    except RedisError as e:
        log.error(f"Redis server error! {e}")
        sys.exit(1)
    except Exception as e:
        log.critical(f"Could not connect to the conex! Error {e}")
        redis.store({STATUS_KEY: f"Error: {e}"})
        sys.exit(1)

    # N.B. Conex movement/dither commands will be dicts turned into strings via json.dumps() for convenient sending and
    # ultimately reformatting over redis and flask connections.
    # TODO: Listen for observation requests, specifically of 'type':'abort'
    try:
        while True:
            for key, val in redis.listen(COMMAND_KEYS):
                log.debug(f"conexAgent received {key}: {val}.")
                if key in OBSERVING_KEYS:
                    val = json.loads(val)
                else:
                    key = key.removeprefix("command:")
                try:
                    if key in SETTING_KEYS:
                        try:
                            cmd = LakeShoreCommand(key, val)
                        except ValueError as e:
                            log.warning(f"Ignoring invalid command ('{key}={val}'): {e}")
                            continue
                        log.info(f"Processing command {cmd}")
                        if key == ENABLE_CONEX_KEY:
                            if val.lower() == 'enabled':
                                log.debug("Enabling Conex...")
                                cc.conex.enable()
                                log.info("Conex enabled")
                            elif val.lower() == 'disabled':
                                log.debug("Disabling Conex")
                                cc.conex.disable()
                                log.info("Conex disabled")
                            redis.store({cmd.setting: cmd.value})
                            redis.store({STATUS_KEY: "OK"})
                    elif key == MOVE_COMMAND_KEY:
                        log.debug(f"Starting conex move...")
                        val = json.loads(val)
                        cc.do_go_to(val['x'], val['y'])
                        redis.store({STATUS_KEY: "OK"})
                        log.info(f"Conex move to ({val['x']}, {val['y']}) successful")
                    elif key == DITHER_COMMAND_KEY:
                        log.debug(f"Starting dither...")
                        val = json.loads(val)
                        cc.do_dither(val)
                        redis.store({STATUS_KEY: "OK"})
                        log.info(f"Started dither with params: {val}")
                    elif key == STOP_COMMAND_KEY or key == OBSERVING_REQUEST_CHANNEL and val['type'] == "abort":
                        log.debug("Stopping conex")
                        cc.do_halt()
                        redis.store({STATUS_KEY: "OK"})
                        log.info("Conex stopped!")
                except IOError as e:
                    redis.store({STATUS_KEY: f"Error {e}"})
                    log.error(f"Comm error: {e}")
    except RedisError as e:
        log.error(f"Redis server error! {e}")
        sys.exit(1)

