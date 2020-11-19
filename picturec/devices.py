import numpy as np
import logging
import time
import sys
import picturec.agent as agent
from picturec.pcredis import PCRedis, RedisError
import threading
import os
import picturec.util as util

log = logging.getLogger(__name__)

COMMANDS921 = {'device-settings:sim921:resistance-range': {'command': 'RANG', 'vals': {'20e-3': '0', '200e-3': '1', '2': '2',
                                                                                        '20': '3', '200': '4', '2e3': '5',
                                                                                        '20e3': '6', '200e3': '7',
                                                                                        '2e6': '8', '20e6': '9'}},
                'device-settings:sim921:excitation-value': {'command': 'EXCI', 'vals': {'0': '-1', '3e-6': '0', '10e-6': '1',
                                                                                        '30e-6': '2', '100e-6': '3',
                                                                                        '300e-6': '4', '1e-3': '5',
                                                                                        '3e-3': '6', '10e-3': '7', '30e-3': '8'}},
                'device-settings:sim921:excitation-mode': {'command': 'MODE', 'vals': {'passive': '0', 'current': '1',
                                                                                       'voltage': '2', 'power': '3'}},
                'device-settings:sim921:time-constant': {'command': 'TCON', 'vals': {'0.3': '0', '1': '1', '3': '2', '10': '3',
                                                                                     '30': '4', '100': '5', '300': '6'}},
                'device-settings:sim921:temp-offset': {'command': 'TSET', 'vals': [0.050, 40]},
                'device-settings:sim921:resistance-offset': {'command': 'RSET', 'vals': [1049.08, 63765.1]},
                'device-settings:sim921:temp-slope': {'command': 'VKEL', 'vals': [0, 1e-2]},
                'device-settings:sim921:resistance-slope': {'command': 'VOHM', 'vals': [0, 1e-5]},
                'device-settings:sim921:output-mode': {'command': 'AMAN', 'vals': {'scaled': '0', 'manual': '1'}},
                'device-settings:sim921:manual-vout': {'command': 'AOUT', 'vals': [-10, 10]},
                'device-settings:sim921:curve-number': {'command': 'CURV', 'vals': {1: '1', 2: '2', 3: '3'}},
                }

COMMANDS960 = {'device-settings:sim960:mode': {'command': 'AMAN', 'vals': {'manual': '0', 'pid': '1'}},
                'device-settings:sim960:vout-value': {'command': 'MOUT', 'vals': [-10, 10]},
                'device-settings:sim960:vout-min-limit': {'command': 'LLIM', 'vals': [-10, 10]},
                'device-settings:sim960:vout-max-limit': {'command': 'ULIM', 'vals': [-10, 10]},
                'device-settings:sim960:setpoint-mode': {'command': 'INPT', 'vals': {'internal': '0', 'external': '1'}},
                'device-settings:sim960:pid-control-vin-setpoint': {'command': 'SETP', 'vals': [-10, 10]},
                'device-settings:sim960:pid-p:value': {'command': 'GAIN', 'vals': [-1e3, -1e-1]},
                'device-settings:sim960:pid-i:value': {'command': 'INTG', 'vals': [1e-2, 5e5]},
                'device-settings:sim960:pid-d:value': {'command': 'DERV', 'vals': [0, 1e1]},
                'device-settings:sim960:setpoint-ramp-enable': {'command': 'RAMP', 'vals': {'off': '0', 'on': '1'}},  # Note: Internal setpoint ramp, NOT magnet ramp
                'device-settings:sim960:setpoint-ramp-rate': {'command': 'RATE', 'vals': [1e-3, 1e4]},  # Note: Internal setpoint ramp rate, NOT magnet ramp
                'device-settings:sim960:pid-p:enabled': {'command': 'PCTL', 'vals': {'off': '0', 'on': '1'}},
                'device-settings:sim960:pid-i:enabled': {'command': 'ICTL', 'vals': {'off': '0', 'on': '1'}},
                'device-settings:sim960:pid-d:enabled': {'command': 'DCTL', 'vals': {'off': '0', 'on': '1'}},
                }

COMMAND_DICT={}
COMMAND_DICT.update(COMMANDS960)
COMMAND_DICT.update(COMMANDS921)


class SimCommand(object):
    def __init__(self, schema_key, value):
        """
        Initializes a SimCommand. Takes in a redis device-setting:* key and desired value an evaluates it for its type,
        the mapping of the command, and appropriately sets the mapping|range for the command. If the setting is not
        supported, raise a ValueError.
        """
        self.setting_value = value

        if schema_key not in COMMAND_DICT.keys():
            raise ValueError(f'Unknown command: {schema_key}')

        self.range = None
        self.mapping = None
        self.setting = schema_key

        self.command = COMMAND_DICT[self.setting]['command']
        setting_vals = COMMAND_DICT[self.setting]['vals']

        if isinstance(setting_vals, dict):
            self.mapping = setting_vals
            if value not in self.mapping:
                raise ValueError(f'Invalid value {value}. Options are: {list(self.mapping.keys())}.')
        else:
            self.range = setting_vals
            try:
                self.value = float(value)
            except ValueError:
                ValueError(f'Invalid value {value}, must be castable to float.')
            if not self.range[0] <= self.value <= self.range[1]:
                raise ValueError(f'Invalid value {value}, must in {self.range}.')

    def __str__(self):
        return f"{self.setting}->{self.setting_value}: {self.sim_string}"

    @property
    def sim_string(self):
        """
        Returns the command string for the SIM.
        """
        v = self.mapping[self.value] if self.range is None else self.value
        return f"{self.command} {v}"


class SimDevice(agent.SerialDevice):
    def __init__(self, name, port, baudrate=9600, timeout=0.1, connect=True, connection_callback=None):
        super().__init__(port, baudrate, timeout, name=name)

        self.sn = None
        self.firmware = None
        self.mainframe_slot = None
        self.mainframe_exitstring = 'xyz'
        self.connection_callback = connection_callback
        self._monitor_thread = None
        if connect:
            self.connect(raise_errors=False)

    def _walk_mainframe(self, name):
        """
        Walk the mainframe to find self.name in the device models

        raise KeyError if not present
        raise RuntimeError if not in mainframe mode

        will populate self.firmware and self.sn on success
        """
        id_msg = self.query("*IDN?", connect=False)
        manufacturer, model, _, _ = id_msg.split(",")
        if model != 'SIM900':
            raise RuntimeError('Mainframe not present')

        for slot in range(1, 9):
            self.send(f"CONN {slot}, '{self.mainframe_exitstring}'")
            id_msg = self.query("*IDN?", connect=False)
            try:
                manufacturer, model, _, _ = id_msg.split(",")
            except Exception:
                raise IOError(f"Bad response to *IDN?: '{id_msg}'")
            if model == name:
                self.mainframe_slot=slot
                return slot
            else:
                self.send(f"{self.mainframe_exitstring}\n", connect=False)
        raise KeyError(f'{name} not found in any mainframe slot')

    def _predisconnect(self):
        if self.mainframe_slot is not None:
            self.send(f"{self.mainframe_exitstring}\n", connect=False)

    def reset(self):
        """
        Send a reset command to the SIM device. This should not be used in regular operation, but if the device is not
        working it is a useful command to be able to send.
        BE CAREFUL - This will reset certain parameters which are set for us to read out the thermometer in the
        PICTURE-C cryostat (as of 2020, a LakeShore RX102-A).
        If you do perform a reset, it will then be helpful to restore the 'default settings' which we have determined
        to be the optimal to read out the hardware we have.
        """
        log.info(f"Resetting the SIM921!")
        self.send("*RST")

    def format_msg(self, msg: str):
        super(self).format_msg(msg.strip().upper())
        return super(self).format_msg(msg.strip().upper())

    def _simspecificconnect(self):
        pass

    def _postconnect(self):
        try:
            self._walk_mainframe(self.name)
        except RuntimeError:
            pass

        id_msg = self.query("*IDN?", connect=False)
        try:
            manufacturer, model, self.sn, self.firmware = id_msg.split(",")  # See manual page 2-20
        except ValueError:
            log.debug(f"Unable to parse IDN response: '{id_msg}'")
            manufacturer, model, self.sn, self.firmware = [None]*4

        if not (manufacturer == "Stanford_Research_Systems" and model == self.name):
            msg = f"Unsupported device: {manufacturer}/{model} (idn response = '{id_msg}')"
            log.critical(msg)
            raise IOError(msg)

        self._simspecificconnect()

        if self.connection_callback is not None:
            self.connection_callback(self)

    @property
    def device_info(self):
        self.connect()
        return dict(model=self.name, firmware=self.firmware, sn=self.sn)

    def initialize_sim(self, settings_to_load):
        """ Initialize the sim with the settings per the picturec schema keys

        In the event of an IO error during configuration XXX
        In the even that a setting is not taken XXX

        Returns the sim settings and the values per the schema

        #TODO JB: whats the return if they only get partially set? do we need to take action?
        # what about if there are IO errors?
        """
        for setting, value in settings_to_load.items():
            cmd = SimCommand(setting, value)
            log.debug(cmd)
            self.send(cmd.sim_string)
            time.sleep(0.1)
        return settings_to_load

    def monitor(self, interval: float, monitor_func: (callable, tuple), value_callback: (callable, tuple) = None):
        """
        TODO JB: This is a first stab at a quasi-general purpose monitoring function that fixes some of the issues we
         discussed.
        Given a monitoring function (or is of the same) and either one or the same number of optional callback
        functions call the monitors every interval. If one callback it will get all the values in the order of the
        monitor funcs, if a list of the same number as of monitorables each will get a single value.

        Monitor functions may not return None.

        When there is a 1-1 correspondence the callback is not called in the event of a monitoring error.
        If a single callback is present for multiple monitor functions values that had errors will be sent as None.
        Function must accept as many arguments as monitor functions.
        """
        if not isinstance(monitor_func, (list, tuple)):
            monitor_func = (monitor_func,)
        if value_callback is not None and not isinstance(value_callback, (list, tuple)):
            value_callback = (value_callback,)
        if not (value_callback is None or len(monitor_func) == len(value_callback) or len(value_callback) == 1):
            raise ValueError('When specified, the number of callbacks must be one or the number of monitor functions')

        def f():
            while True:
                vals = []
                for func in monitor_func:
                    try:
                        vals.append(func())
                    except IOError as e:
                        log.error(f"Failed to poll {func}: {e}")
                        vals.append(None)

                if value_callback is not None:
                    if len(value_callback) > 1 or len(monitor_func) == 1:
                        for v, cb in zip(vals, value_callback):
                            if v is not None:
                                try:
                                    cb(v)
                                except Exception as e:
                                    log.error(f"Callback {cb} raised {e} when called with {v}.")
                    else:
                        cb = value_callback[0]
                        try:
                            cb(*vals)
                        except Exception as e:
                            log.error(f"Callback {cb} raised {e} when called with {v}.")

                time.sleep(interval)

        self._monitor_thread = threading.Thread(target=f, name='Monitor Thread')
        self._monitor_thread.daemon = True
        self._monitor_thread.start()


class SIM960(SimDevice):
    def __init__(self, port, baudrate=9600, timeout=0.1, connect=True, connection_callback=None):
        """
        Initializes SIM960 agent. First hits the superclass (SerialDevice) init function. Then sets class variables which
        will be used in normal operation. If connect mainframe is True, attempts to connect to the SIM960 via the SIM900
        in mainframe mode. Raise IOError if an invalid slot or exit string is given (or if no exit string is given).
        """
        super().__init__('SIM960', port, baudrate, timeout, connect=connect, connection_callback=connection_callback)
        self.polarity = 'negative'
        self.last_input_voltage = None
        self.last_output_voltage = None
        self._monitor_thread = None

    def _simspecificconnect(self):
        # Set polarity to negative here. This is a non-redis controlled setting (not modifiable during normal operation).
        self.send("APOL 0", connect=False)
        polarity = self.query("APOL?", connect=False)
        if polarity != '0':
            msg = f"Polarity query returned {polarity}. Setting PID loop polarity to negative failed."
            log.critical(msg)
            raise IOError(msg)

    def input_voltage(self):
        """Read the voltage being sent to the input monitor of the SIM960 from the SIM921"""
        iv = self.query("MMON?")
        self.last_input_voltage = iv
        return iv

    def output_voltage(self):
        """Report the voltage at the output of the SIM960. In manual mode, this will be explicitly controlled using MOUT
        and in PID mode this will be the value set by the function Output = P(e + I * int(e) + D * derv(e)) + Offset"""
        ov = self.query("OMON?")
        self.last_output_voltage = ov
        return ov


class SIM921(SimDevice):
    def __init__(self, port, baudrate=9600, timeout=0.1, connect=True, connection_callback=None):
        super().__init__('SIM921', port, baudrate, timeout, connect=connect, connection_callback = connection_callback)
        self.scale_units = 'resistance'
        self.last_voltage = None
        self.last_monitored_values = None
        self._monitor_thread = None
        self.last_voltage_read = None
        self.last_temp_read = None
        self.last_resistance_read = None

    def _simspecificconnect(self):
        # Ensure that the scaled output will be proportional to the resistance error. NOT the temperature error. The
        # resistance spans just over 1 order of magnitude (~1-64 kOhms) while temperature spans 4 (5e-2 - 4e2 K).
        self.send("ATEM 0", connect=False)
        atem = self.query("ATEM?", connect=False)
        if atem != '0':
            msg = (f"Setting ATEM=0 failed, got '{atem}'. Zero, indicating voltage scale units are in resistance, "
                   "is required. DO NOT OPERATE! Exiting.")
            log.critical(msg)
            raise IOError(msg)

        # Make sure that the excitation is turned on. If not successful, exit the program
        self.send("EXON 1", connect=False)
        exon = self.query("EXON?", connect=False)
        if exon != '1':
            msg = f"EXON=1 failed, got '{exon}'. Unable to enable excitation and unable to operate!"
            log.critical(msg)
            raise IOError(msg)

    def temp(self):
        temp = self.query("TVAL?")
        self.last_temp_read = temp
        return temp

    def resistance(self):
        res = self.query("RVAL?")
        self.last_resistance_read = res
        return res

    def output_voltage(self):
        voltage = None
        if self.query("AMAN?") == "1":
            log.debug("SIM921 voltage output is in manual mode!")
            voltage = self.query("AOUT?")
        elif self.query("AMAN?") == "0":
            log.debug("SIM921 voltage output is in scaled mode!")
            voltage = float(self.query("VOHM?")) * float(self.query("RDEV?"))
        #TODO can AMAN take on other values? There isn't harm in this (it protects you from SRS not adhering to THEIR
        # API, another option would be to raise an error if it took another value since that probably means
        # something major is wrong.
        self.last_voltage_read = voltage
        return voltage

    def temp_and_resistance(self):
        return {'temperature': self.temp, 'resistance': self.resistance}

    def _load_calibration_curve(self, curve_num: int, curve_type, curve_name: str, file:str=None):
        """
        This is an engineering function for the SIM921 device. In normal operation of the fridge, the user should never
        have to load a curve in. This should only ever be used if (1) a new curve becomes available, (2) the
        thermometer used by the SIM921 is changed out for a new one, or (3) the original curve becomes corrupted.
        Currently (21 July 2020) designed specifically to read in the LakeShore RX-102-A calibration curve, but can be
        modified without difficulty to take in other curves. The command syntax will not change for loading the curve
        onto the SIM921, only the np.loadtxt() and data manipulation of the curve data itself. As long as the curve
        is in a format where resistance[n] < resistance[n+1] for all points n on the curve, it can be loaded into the
        SIM921 instrument.
        """
        if curve_num not in (1, 2, 3):
            log.error(f"SIM921 only accepts 1, 2, or 3 as the curve number")
            return None

        CURVE_TYPE_DICT = {'linear': '0', 'semilogt': '1', 'semilogr': '2', 'loglog': '3'}
        if curve_type not in CURVE_TYPE_DICT.keys():
            log.error(f"Invalid calibration curve type for SIM921. Valid types are {CURVE_TYPE_DICT.keys()}")
            return None

        if file is None:
            import pkg_resources as pkg
            file = pkg.resource_filename('hardware.thermometry.RX-102A', 'RX-102A_Mean_Curve.tbl')

        log.info(f"Curve data at {file}")

        try:
            curve_data = np.loadtxt(file)
            temp_data = np.flip(curve_data[:, 0], axis=0)
            res_data = np.flip(curve_data[:, 1], axis=0)
        except OSError:
            log.error(f"Could not find curve data file.")
            raise ValueError(f"{file} couldn't be loaded.")
        except IndexError:
            raise ValueError(f"{file} couldn't be loaded.")

        log.info(f"Attempting to initialize curve {curve_num}, type {curve_type}")
        try:
            # curve_init_str = "CINI "+str(curve_num)+", "+str(CURVE_TYPE_DICT[curve_type]+", "+curve_name)
            self.send(f"CINI {curve_num}, {CURVE_TYPE_DICT[curve_type]}, {curve_name}")
            for t, r in zip(temp_data, res_data):
                # self.send("CAPT"+str(curve_num)+", "+str(r)+", "+str(t))
                self.send(f"CAPT {curve_num}, {r}, {t}")
                time.sleep(0.1)
        except IOError as e:
            raise e
        log.info(f"Successfully loaded curve {curve_num} - '{curve_name}'!")
