import numpy as np

from wtforms.fields import *
from wtforms.fields.html5 import *
from wtforms.validators import *
from flask_wtf import FlaskForm


class EmptyForm(FlaskForm):
    submit = SubmitField('Submit')


class DataPathForm(FlaskForm):
    new_night = SubmitField("Create New Night")
    data_dir = StringField("Current Data Directory")
    dark_file = StringField("Active Dark File")
    flat_file = StringField("Active Flat File")
    dark_template_file = StringField("Template Dark File")
    flat_template_file = StringField("Template Flat File")
    sci_template_file = StringField("Template Sci File")
    beammap_file = StringField("Beammap File", render_kw={'disabled': True})
    update_paths = SubmitField("Update Paths")


class ConexForm(FlaskForm):
    start_pos = StringField("Start (x, y)", default="0.000, 0.000")
    stop_pos = StringField("Stop (x, y)", default="0.000, 0.000")
    n_steps = IntegerField("N Steps", default=5)
    dwell_time = IntegerField("Dwell (s)", default=30)
    dither_start = SubmitField("Dither")
    conex_position = StringField("Position (x, y)", default="0.000, 0.000")
    conex_stop = SubmitField("Stop")


class ConexNormalizationForm(FlaskForm):
    conex_ref_x = FloatField("Conex X Reference", default=0.000)
    conex_ref_y = FloatField("Conex Y Reference", default=0.000)
    pixel_ref_x = FloatField("Pixel X Reference", default=0)
    pixel_ref_y = FloatField("Pixel Y Reference", default=0)
    update_conex_refs = SubmitField("Update Conex References")


class FilterWheelForm(FlaskForm):
    from mkidcontrol.commands import FILTERS
    filter = SelectField("Filter", choices=[f"{f[0]}:{f[1]}" for f in FILTERS.items()])


class LaserBoxForm(FlaskForm):
    power808 = FloatField("808 nm", default=0)
    power904 = FloatField("904 nm", default=0)
    power980 = FloatField("980 nm", default=0)
    power1120 = FloatField("1120 nm", default=0)
    power1310 = FloatField("1310 nm", default=0)
    update_all_lasers = SubmitField("Update Powers")
    flipperposition = SelectField("Mirror Position", choices=["Up", "Down"])
    all_lasers_off = SubmitField("All Lasers Off")


class FocusForm(FlaskForm):
    focus_position = FloatField("Focus Position (0-50 mm)", default=0)  # Allowed values run from 0-50 mm
    home_focus = SubmitField("Calibrate")
    jogforward = SubmitField("Jog Forward")
    jogbackward = SubmitField("Jog Backward")


class ObsControlForm(FlaskForm):
    obsStartStop = SubmitField("")
    obsName = StringField("Name", default='')
    wavecal = SubmitField("Wavecal")
    obs_duration = FloatField("Duration (s):", default=60)
    flat = SubmitField("Flat")
    dark = SubmitField("Dark")
    apply_flat = SubmitField("Apply Flat")
    apply_dark = SubmitField("Apply Dark")
    min_cts = IntegerField("Min:", default=0)
    max_cts = IntegerField("Max:", default=2500)
    int_time = FloatField("Integrate (s):", default=1.0)


class HeatSwitchForm(FlaskForm):
    # Heatswitch form
    from mkidcontrol.devices import HeatswitchMotor
    max_velocity = FloatField("Max Velocity", default=HeatswitchMotor.DEFAULT_MAX_VELOCITY, validators=[NumberRange(0, 1e4)])
    running_current = FloatField("Running Current", default=HeatswitchMotor.DEFAULT_RUNNING_CURRENT, validators=[NumberRange(10, 127)])
    acceleration = FloatField("Acceleration", default=HeatswitchMotor.DEFAULT_ACCELERATION, validators=[NumberRange(0, 100)])
    hs_update = SubmitField("Update")
    hs_open = SubmitField("Open")
    hs_close = SubmitField("Close")
    hs_stop = SubmitField("Stop")


class Input372FilterForm(FlaskForm):
    from mkidcontrol.commands import LS372_INPUT_FILTER_STATES
    channel = HiddenField("")
    state = SelectField("State", default="Off", choices=list(LS372_INPUT_FILTER_STATES.keys()))
    settle_time = FloatField("Settle Time", default=5, validators=[NumberRange(1, 200)])
    window = FloatField("Window", default=10, validators=[NumberRange(1, 80)])
    update = SubmitField("Update")


class ControlSensorForm(FlaskForm):
    # Lakeshore 372 Form
    from mkidcontrol.commands import LS372_SENSOR_MODE, LS372_AUTORANGE_VALUES, LS372_CONTROL_INPUT_CURRENT_RANGE, \
        LS372_CURRENT_SOURCE_SHUNTED_VALUES, LS372_INPUT_SENSOR_UNITS, LS372_RESISTANCE_RANGE, LS372_ENABLED_VALUES, \
        LS372_CURVE_COEFFICIENTS
    channel = HiddenField("")
    name = StringField("Name")
    mode = SelectField("Sensor Mode", default="Current", choices=list(LS372_SENSOR_MODE.keys()), render_kw={'disabled': True})
    excitation_range = SelectField("Excitation Current", choices=list(LS372_CONTROL_INPUT_CURRENT_RANGE.keys()))
    curve_number = SelectField("Curve", choices=np.arange(1, 60))
    auto_range = SelectField("Autorange Enable", choices=list(LS372_AUTORANGE_VALUES.keys()))
    current_source_shunted = SelectField("Current Source Shunted", choices=list(LS372_CURRENT_SOURCE_SHUNTED_VALUES.keys()))
    units = SelectField("Units", choices=list(LS372_INPUT_SENSOR_UNITS.keys()))
    resistance_range = SelectField("Resistance Range", default='63.2 k\u03A9', choices=list(LS372_RESISTANCE_RANGE.keys()), render_kw={'disabled': True})
    dwell_time = IntegerField("Dwell Time", default=1.0, validators=[NumberRange(1, 200)])
    pause_time = IntegerField("Pause Time", default=3.0, validators=[NumberRange(3, 200)])
    temperature_coefficient = SelectField("Temperature Coefficient", choices=list(LS372_CURVE_COEFFICIENTS.keys()))
    enable = SelectField("Enable", choices=list(LS372_ENABLED_VALUES.keys()))
    update = SubmitField("Update")


class DiasbledControlSensorForm(FlaskForm):
    # Lakeshore 372 Form
    from mkidcontrol.commands import LS372_SENSOR_MODE, LS372_AUTORANGE_VALUES, LS372_CONTROL_INPUT_CURRENT_RANGE, \
        LS372_CURRENT_SOURCE_SHUNTED_VALUES, LS372_INPUT_SENSOR_UNITS, LS372_RESISTANCE_RANGE, LS372_ENABLED_VALUES, \
        LS372_CURVE_COEFFICIENTS
    channel = HiddenField("")
    name = StringField("Name", render_kw={'disabled': True})
    mode = SelectField("Sensor Mode", default="Current", choices=list(LS372_SENSOR_MODE.keys()), render_kw={'disabled': True})
    excitation_range = SelectField("Excitation Current", choices=list(LS372_CONTROL_INPUT_CURRENT_RANGE.keys()), render_kw={'disabled': True})
    curve_number = SelectField("Curve", choices=np.arange(1, 60), render_kw={'disabled': True})
    auto_range = SelectField("Autorange Enable", choices=list(LS372_AUTORANGE_VALUES.keys()), render_kw={'disabled': True})
    current_source_shunted = SelectField("Current Source Shunted", choices=list(LS372_CURRENT_SOURCE_SHUNTED_VALUES.keys()), render_kw={'disabled': True})
    units = SelectField("Units", choices=list(LS372_INPUT_SENSOR_UNITS.keys()), render_kw={'disabled': True})
    resistance_range = SelectField("Resistance Range", choices=list(LS372_RESISTANCE_RANGE.keys()), render_kw={'disabled': True})
    dwell_time = IntegerField("Dwell Time", default=1, validators=[NumberRange(1, 200)], render_kw={'disabled': True})
    pause_time = IntegerField("Pause Time", default=3, validators=[NumberRange(3, 200)], render_kw={'disabled': True})
    temperature_coefficient = SelectField("Temperature Coefficient", choices=list(LS372_CURVE_COEFFICIENTS.keys()), render_kw={'disabled': True})
    enable = SelectField("Enable", choices=list(LS372_ENABLED_VALUES.keys()))
    update = SubmitField("Update")


class Input372SensorForm(FlaskForm):
    # Lakeshore 372 Form
    from mkidcontrol.commands import LS372_SENSOR_MODE, LS372_AUTORANGE_VALUES, LS372_MEASUREMENT_INPUT_VOLTAGE_RANGE, \
        LS372_MEASUREMENT_INPUT_CURRENT_RANGE, LS372_CURRENT_SOURCE_SHUNTED_VALUES, LS372_INPUT_SENSOR_UNITS, \
        LS372_RESISTANCE_RANGE, LS372_ENABLED_VALUES, LS372_CURVE_COEFFICIENTS
    channel = HiddenField("")
    name = StringField("Name")
    mode = SelectField("Sensor Mode", default="Current", choices=list(LS372_SENSOR_MODE.keys()), render_kw={'disabled':True})
    excitation_range = SelectField("Excitation Current", choices=list(LS372_MEASUREMENT_INPUT_CURRENT_RANGE.keys()))
    curve_number = SelectField("Curve", choices=np.arange(1, 60))
    auto_range = SelectField(label="Autorange Enable", choices=list(LS372_AUTORANGE_VALUES.keys()))
    current_source_shunted = SelectField(label="Current Source Shunted", choices=list(LS372_CURRENT_SOURCE_SHUNTED_VALUES.keys()))
    units = SelectField(label="Units", choices=list(LS372_INPUT_SENSOR_UNITS.keys()))
    resistance_range = SelectField(label="Resistance Range", choices=list(LS372_RESISTANCE_RANGE.keys()))
    dwell_time = IntegerField(label="Dwell Time", default=1, validators=[NumberRange(1, 200)])
    pause_time = IntegerField(label="Pause Time", default=3, validators=[NumberRange(3, 200)])
    temperature_coefficient = SelectField(label="Temperature Coefficient", choices=list(LS372_CURVE_COEFFICIENTS))
    enable = SelectField(label="Enable", choices=list(LS372_ENABLED_VALUES.keys()))
    update = SubmitField("Update")


class DisabledInput372SensorForm(FlaskForm):
    # Lakeshore 372 Form
    from mkidcontrol.commands import LS372_SENSOR_MODE, LS372_AUTORANGE_VALUES, LS372_MEASUREMENT_INPUT_VOLTAGE_RANGE, \
        LS372_MEASUREMENT_INPUT_CURRENT_RANGE, LS372_CURRENT_SOURCE_SHUNTED_VALUES, LS372_INPUT_SENSOR_UNITS, \
        LS372_RESISTANCE_RANGE, LS372_ENABLED_VALUES, LS372_CURVE_COEFFICIENTS

    channel = HiddenField("")
    name = StringField("Name")
    mode = SelectField("Sensor Mode", choices=list(LS372_SENSOR_MODE.keys()))
    excitation_range = SelectField("Excitation Current", choices=list(LS372_MEASUREMENT_INPUT_CURRENT_RANGE.keys()))
    curve_number = SelectField("Curve", choices=np.arange(1, 60))
    auto_range = SelectField(label="Autorange Enable", choices=list(LS372_AUTORANGE_VALUES.keys()))
    current_source_shunted = SelectField (label="Current Source Shunted",choices=list(LS372_CURRENT_SOURCE_SHUNTED_VALUES.keys()))
    units = SelectField(label="Units", choices=list(LS372_INPUT_SENSOR_UNITS.keys()))
    resistance_range = SelectField(label="Resistance Range", choices=list(LS372_RESISTANCE_RANGE.keys()))
    dwell_time = IntegerField(label="Dwell Time", default=1, validators=[NumberRange(1, 200)])
    pause_time = IntegerField(label="Pause Time", default=3, validators=[NumberRange(3, 200)])
    temperature_coefficient = SelectField(label="Temperature Coefficient", choices=list(LS372_CURVE_COEFFICIENTS))
    enable = SelectField(label="Enable", choices=list(LS372_ENABLED_VALUES.keys()))
    update = SubmitField("Update")


class OutputHeaterForm(FlaskForm):
    # Lakeshore 372 Form
    from mkidcontrol.commands import LS372_HEATER_OUTPUT_MODE, LS372_HEATER_INPUT_CHANNEL, \
        LS372_HEATER_POWERUP_ENABLE, LS372_HEATER_READING_FILTER, LS372_OUTPUT_POLARITY, LS372_HEATER_CURRENT_RANGE

    channel = HiddenField("")
    name = StringField("Name", render_kw={'disabled': True})
    output_mode = SelectField("Output Mode", choices=list(LS372_HEATER_OUTPUT_MODE.keys()))
    input_channel = SelectField("Input Channel", choices=list(LS372_HEATER_INPUT_CHANNEL.keys()))
    powerup_enable = SelectField("Powerup Enable", choices=list(LS372_HEATER_POWERUP_ENABLE.keys()))
    reading_filter = SelectField("Reading Filter", choices=list(LS372_HEATER_READING_FILTER.keys()))
    delay = IntegerField("Delay", default=1, validators=[NumberRange(1, 255)])
    polarity = SelectField("Polarity", choices=list(LS372_OUTPUT_POLARITY.keys()))
    setpoint = FloatField("Temperature Setpoint (K)", default=0.100,  validators=[NumberRange(0,300)])
    gain = FloatField("PID Gain (P)", default=0,  validators=[NumberRange()])  # TODO: Find values allowable
    integral = FloatField("PID Integral (I)", default=0,  validators=[NumberRange()])  # TODO: Find values allowable
    ramp_rate = FloatField("PID Ramp Rate (D)", default=0,  validators=[NumberRange()])  # TODO: Find values allowable
    range = SelectField("Range", choices=list(LS372_HEATER_CURRENT_RANGE))
    update = SubmitField("Update")


class DisabledOutputHeaterForm(FlaskForm):
    # Lakeshore 372 Form
    from mkidcontrol.commands import LS372_HEATER_OUTPUT_MODE, LS372_HEATER_INPUT_CHANNEL, \
        LS372_HEATER_POWERUP_ENABLE, LS372_HEATER_READING_FILTER, LS372_OUTPUT_POLARITY, LS372_HEATER_CURRENT_RANGE
    channel = HiddenField("")
    name = StringField("Name", render_kw={'disabled': True})
    output_modemode = SelectField("Output Mode", choices=list(LS372_HEATER_OUTPUT_MODE.keys()))
    input_channel = SelectField("Input Channel", choices=list(LS372_HEATER_INPUT_CHANNEL.keys()), render_kw={'disabled': True})
    powerup_enable = SelectField("Powerup Enable", choices=list(LS372_HEATER_POWERUP_ENABLE.keys()), render_kw={'disabled': True})
    reading_filter = SelectField("Reading Filter", choices=list(LS372_HEATER_READING_FILTER.keys()), render_kw={'disabled': True})
    delay = IntegerField("Delay", default=1, validators=[NumberRange(1, 255)], render_kw={'disabled': True})
    polarity = SelectField("Polarity", choices=list(LS372_OUTPUT_POLARITY.keys()), render_kw={'disabled': True})
    setpoint = FloatField("Temperature Setpoint (K)", default=0.100, validators=[NumberRange(0, 300)], render_kw={'disabled': True})
    gain = FloatField("PID Gain (P)", default=0, validators=[NumberRange()], render_kw={'disabled': True})  # TODO: Find values allowable
    integral = FloatField("PID Integral (I)", default=0, validators=[NumberRange()], render_kw={'disabled': True})  # TODO: Find values allowable
    ramp_rate = FloatField("PID Ramp Rate (D)", default=0, validators=[NumberRange()], render_kw={'disabled': True})  # TODO: Find values allowable
    range = SelectField("Range", choices=list(LS372_HEATER_CURRENT_RANGE), render_kw={'disabled': True})
    update = SubmitField("Update")


class Input336SensorForm(FlaskForm):
    # Lakeshore 336 form
    from mkidcontrol.commands import LS336_INPUT_SENSOR_TYPES, LS336_INPUT_SENSOR_UNITS, LS336_AUTORANGE_VALUES, \
        LS336_COMPENSATION_VALUES
    channel = HiddenField("")
    name = StringField("Name")
    sensor_type = SelectField("Sensor Type", choices=list(LS336_INPUT_SENSOR_TYPES.keys()))
    units = SelectField("Units", choices=list(LS336_INPUT_SENSOR_UNITS.keys()))
    curve = SelectField("Curve", choices=np.arange(1, 60))
    autorange = SelectField(label="Autorange Enable", choices=list(LS336_AUTORANGE_VALUES.keys()))
    compensation = SelectField(label="Compensation", choices=list(LS336_COMPENSATION_VALUES.keys()))


class DiodeForm(Input336SensorForm):
    # Lakeshore 336 form
    from mkidcontrol.commands import LS336_DIODE_RANGE
    input_range = SelectField("Input Range", choices=list(LS336_DIODE_RANGE.keys()))
    update = SubmitField("Update")


class RTDForm(Input336SensorForm):
    # Lakeshore 336 form
    from mkidcontrol.commands import LS336_RTD_RANGE
    input_range = SelectField("Input Range", choices=list(LS336_RTD_RANGE.keys()))
    update = SubmitField("Update")


class DisabledInput336Form(FlaskForm):
    # Lakeshore 336 form
    from mkidcontrol.commands import LS336_INPUT_SENSOR_TYPES, LS336_INPUT_SENSOR_UNITS, LS336_INPUT_SENSOR_RANGE, \
        LS336_AUTORANGE_VALUES, LS336_COMPENSATION_VALUES
    channel = HiddenField()
    name = StringField("Name")
    sensor_type = SelectField("Sensor Type", choices=list(LS336_INPUT_SENSOR_TYPES.keys()))
    units = SelectField("Units", choices=list(LS336_INPUT_SENSOR_UNITS.keys()), render_kw={'disabled':True})
    curve = SelectField("Curve", choices=np.arange(1, 60), render_kw={'disabled':True})
    autorange = SelectField("Autorange Enable", choices=list(LS336_AUTORANGE_VALUES.keys()))
    compensation = SelectField("Compensation", choices=list(LS336_COMPENSATION_VALUES.keys()))
    input_range = SelectField("Input Range", choices=list(LS336_INPUT_SENSOR_RANGE.keys()), render_kw={'disabled':True})
    enable = SubmitField("Enable")


class Lakeshore625ControlForm(FlaskForm):
    # Lakeshore 625 form
    from mkidcontrol.commands import COMMANDS625
    desired_current = FloatField("Set Current (Manual)", default=0, validators=[NumberRange(0, 7.88)])
    magnetic_field_parameter = FloatField("Magnetic Field Parameter (kG/A)", default=4.0609, validators=[NumberRange(0, 10)])
    ramp_rate = FloatField("Ramp Rate (A/s)", default=0.005, validators=[NumberRange(0, 0.020)])
    compliance_voltage = FloatField("Compliance Voltage", default=2.5, validators=[NumberRange(0.1, 5.0)])
    control_mode = SelectField("Control Mode", choices=list(COMMANDS625['device-settings:ls625:control-mode']['vals'].keys()))
    quench_ramp_rate = FloatField("Quench Ramp Rate (A/s)", default=0.020, validators=[NumberRange(0.01, 10)])
    baud_rate = SelectField("Baud Rate", choices=list(COMMANDS625['device-settings:ls625:baud-rate']['vals'].keys()), render_kw={'disabled': True})
    current_limit = FloatField("Current Limit", default=0.44, validators=[NumberRange(0, 10.0)])
    compliance_voltage_limit = FloatField("Comliance Voltage Limit", default=2.5, validators=[NumberRange(0.1, 5.0)])
    rate_limit = FloatField("Ramp Rate Limit (A/s)", default=0.250, validators=[NumberRange(0, 0.500)])
    update = SubmitField("Update")


class MagnetCycleSettingsForm(FlaskForm):
    # Magnet controller form
    # TODO: Turn this into something that can be used to either modify the standard/fast cycle OR run a custom cycle
    soak_current = FloatField("Soak Current (A)", default=9.44, validators=[NumberRange(0, 10.0)])
    soak_time = FloatField("Soak Time (minutes)", default=60, validators=[NumberRange(0, 240)])
    ramp_rate = FloatField("Ramp rate (A/s)", default=0.005, validators=[NumberRange(0, 0.100)])
    deramp_rate = FloatField("Deramp rate (A/s)", default=0.005, validators=[NumberRange(0, 0.100)])
    update = SubmitField("Update")


class MagnetCycleForm(FlaskForm):
    # Magnet controller form
    start_cycle = SubmitField("Start Cycle")
    abort_cycle = SubmitField("Abort Cooldown")
    schedule_at = DateTimeLocalField('Schedule cycle for:', format='%Y-%m-%dT%H:%M')
    schedule_cycle = SubmitField("Schedule")
