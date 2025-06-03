# EMULATOR.PY - emulator of Elveflow SDK for prototyping code without the OB1 and/or the valve connected

# PACKAGE IMPORTS
import os
from math import pi
from ctypes import *
import tkinter.filedialog

import numpy as np


# EMULATED OB1 CLASS DEFINITION ----------------------------------------------------------------------------
# an object of this class stores the channel pressures
# and the resistance of the setup
class emulated_OB1:
    # initialise the object with 'None's and '-1's in the fields
    def __init__(self):
        # OB-1 name string
        self.Device_Name = 'emulated_OB1'.encode('ascii')

        # OB-1 reference
        self.OB1_ID = 0

        # channel pressures
        self.ch_pressures=[-1, -1]
        # channel resistances
        self.ch_resistances=[-1, -1]

        # channel sensors - are they present
        self.ch_sensors_present=[False, False]
        return

    # find the flow for a given set resistance, assuming zero delays
    def get_flow(self, ch_id):
        return self.ch_pressures[ch_id]/self.ch_resistances[ch_id]

    # set channel resistances
    def set_resistances(self, channel_resistances):
        self.ch_resistances = channel_resistances
        return

# AUXILIARIES ----------------------------------------------------------------------------------------------
# calculate tubing resistance [mbar*s/uL]
def tubing_res_calc(R_um,  # tubing radius, um
                    L_cm,  # tubing length, cm
                    mu = 6.913e-7   # by default, water at 37C in mbar*s
                    ):
    return (8*mu*L_cm/(pi * R_um**4))*1e13

# DEFINE YOUR EMULATOR HERE! -------------------------------------------------------------------------------
emulator_R_um = 100 # resistor radius [um]
emulator_L_cm = 10  # resistor length [cm]
emulator_res = tubing_res_calc(emulator_R_um, emulator_L_cm)

OB1_em = emulated_OB1()
OB1_em.set_resistances([emulator_res, emulator_res])

# DEFINITIONS OF SDK FUNCTION ANALOGUES FOR THE OB-1 -------------------------------------------------------------------
# initialise the OB-1
# in the emulator, just set the OB-1 name string and reference
def OB1_Initialization(
        # OB-1 self.OB1's serial number (check by running NIMAX)
        Device_Name='0204CC5D'.encode('ascii'),
        # Types of channels 1,2,3,4 respectively - WE HAVE JUST TWO CHANNELS, BOTH TYPE 2 (0-2000 MBAR)
        reg_ch_1=2,
        reg_ch_2=2,
        reg_ch_3=0,
        reg_ch_4=0,
        # reference assigned to the OB-1
        OB1_ID_out=byref(c_int32())
):
    OB1_em.Device_Name = Device_Name
    OB1_em.OB1_ID = OB1_ID_out

    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    ob1_error_msg =0

    # return error message
    return ob1_error_msg

# destroy the OB-1
# in the emulator, do nothing
def OB1_Destructor(
    # reference to which OB-1 is being used
    OB1_ID
):
    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    ob1_error_msg = 0

    # return error message
    return ob1_error_msg

# add the OB-1 sensor
# in the emulator, set appropriate OB1_em.ch_sensor_present
def OB1_Add_Sens(
        # reference to which OB-1 is being used
        OB1_ID,
        # the selected channel
        channel_1_to_4,
        # sensor type - WE ONLY HAVE TYPE 4 SENSORS (MICRFOLUIDIC FLOW SENSORS FOR MAX +-80UL/MIN)
        Z_sensor_type = 4,
        # sensor type (A or D) - 0 if ana, 1 if digital - OUR SENSORS ARE DIGITAL
        Z_sensor_digit_analog = 1,
        # sensor calibartion - 0 if calibrated for water, 1 if calibrated for isopropanol - OUR SENSORS ARE CALIBRATED FOR WATER
        Z_Sensor_FSD_Calib = 0,
        # sensor resolution bits (NOT the exact number thereof! refer to the walkthrough)
        Z_D_F_S_Resolution = 7,
        # voltage for custom analogue sensors - IRRELEVANT AS OUR SENSORS ARE DIGITAL
        customsens_voltage_5_to_25 = 0
):
    # set sensor pressure
    OB1_em.ch_sensors_present[channel_1_to_4-1] = True

    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    ob1_error_msg = 0

    # return error message
    return ob1_error_msg


# get OB-1 flow sensor data
# in the emulator, just pressure divided by resistance (perfect and no delay)
def OB1_Get_Sens_Data(
        # reference to which OB-1 is being used
        OB1_ID,
        # the selected channel
        channel_1_to_4,
        # 1 means all pressure and analog sensor readings actually measured, not taken for memory. Irrelevant for digital sensors
        acquire_data1true0false,
        # where to write the data
        sens_data
):
    # set readings
    sens_data_ptr = cast(sens_data, POINTER(c_double))
    sens_data_ptr.contents.value=OB1_em.get_flow(channel_1_to_4-1)

    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    ob1_error_msg = 0

    # return error message
    return ob1_error_msg

# get OB-1 pressure data
# in the emulator, just set pressure (perfect and no delay)
def OB1_Get_Press(
        # reference to which OB-1 is being used
        OB1_ID,
        # the selected channel
        channel_1_to_4,
        # 1 means all pressure and analog sensor readings actually measured, not taken for memory. Irrelevant for digital sensors
        acquire_data1true0false,
        # calibration array
        calib_array_in,
        # where to write the data
        pressure,
        # calibration array length (do not touch!)
        calib_array_length = 1000
):
    # get readings
    pressure_ptr = cast(pressure, POINTER(c_double))
    pressure_ptr.contents.value = OB1_em.ch_pressures[channel_1_to_4-1]

    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    ob1_error_msg = 0

    # return error message
    return ob1_error_msg


# set OB-1 pressure in a given channel
# in the emulator, just set pressure (perfect and no delay)
def OB1_Set_Press(
        # reference to which OB-1 is being used
        OB1_ID,
        # the selected channel
        channel_1_to_4,
        # desired pressure
        pressure,
        # calibration array
        calib_array_in,
        # calibration array length (do not touch!)
        calib_array_length = 1000
):
    # set pressure - handling the cases when a pressure is a Python int/float or a c_double
    if(isinstance(pressure, (int, float))):
        OB1_em.ch_pressures[channel_1_to_4 - 1] = pressure
    else:
        OB1_em.ch_pressures[channel_1_to_4 - 1] = pressure.value

    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    ob1_error_msg = 0

    # return error message
    return ob1_error_msg


# set OB-1 pressure in all channels, according to an input array
# in the emulator, just set pressure (perfect and no delay)
def OB1_Set_All_Press(
        # reference to which OB-1 is being used
        OB1_ID,
        # array of desired pressures
        pressure_array_in,
        # length of desired pressures array
        pressure_array_length,
        # calibration array
        calib_array_in,
        # calibration array length (do not touch!)
        calib_array_length = 1000
):
    # set pressures - handling the cases when a pressure is a Python int/float or a ctypes list
    if(isinstance(pressure_array_in, (list, tuple, np.ndarray))):
        for i in range(0, pressure_array_length):
            OB1_em.ch_pressures[i] = pressure_array_in[i]
    else:
        for i in range(0,pressure_array_length):
            OB1_em.ch_pressures[i]=pressure_array_in[i].value

    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    ob1_error_msg = 0

    # return error message
    return ob1_error_msg


# calibrate the OB-1
# in the emulator, just return a 1000-long array of zeros
def OB1_Calib(
        # reference to which OB-1 is being used
        OB1_ID,
        # calibration array
        calib_array_out,
        # calibration array length (do not touch!)
        calib_array_length = 1000
):
    # get the all-zeros Calibration array
    calib_array_ptr = cast(calib_array_out, POINTER(c_double * calib_array_length))
    calib_array = calib_array_ptr.contents
    for i in range(0, calib_array_length):
        calib_array[i] = 0

    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    ob1_error_msg = 0

    # return error message
    return ob1_error_msg

# get a default calibration
# in the emulator, just return a 1000-long array of zeros
def Elveflow_Calibration_Default(
        # calibration array
        calib_array_out,
        # calibration array length (do not touch!)
        calib_array_length = 1000
):
    # get the all-zeros Calibration array
    calib_array_ptr = cast(calib_array_out, POINTER(c_double * calib_array_length))
    calib_array = calib_array_ptr.contents
    for i in range(0, calib_array_length):
        calib_array[i] = 0

    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    ob1_error_msg = 0

    # return error message
    return ob1_error_msg

# load a calibration
def Elveflow_Calibration_Load(
        # calibration file path
        path,
        # calibration array
        calib_array_out,
        # calibration array length (do not touch!)
        calib_array_length = 1000
):
    # convert path to string
    path_str = path.decode('ascii')

    # check if path exists, get path from a dialogue window if not
    if os.path.exists(path_str):
        # open the file at the path
        with open(path_str, 'rb') as calib_file:
            data = calib_file.read()
    else:
        # open the file chosen by the user
        with tkinter.filedialog.askopenfile(mode='rb') as calib_file:
            data = calib_file.read()

    # get calibration array values from binary data
    calib_array_ptr = cast(calib_array_out, POINTER(c_double * calib_array_length))
    calib_array = calib_array_ptr.contents
    for i in range(0, calib_array_length):
        calib_array[i] = data[i]

    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    ob1_error_msg = 0

    # return error message
    return ob1_error_msg

# load a calibration
def Elveflow_Calibration_Save(
        # calibration file path
        path,
        # calibration array
        calib_array_out,
        # calibration array length (do not touch!)
        calib_array_length = 1000
):
    # get the all-zeros Calibration array
    calib_array_ptr = cast(calib_array_out, POINTER(c_double * calib_array_length))
    calib_array = calib_array_ptr.contents

    # convert path to string
    path_str = path.decode('ascii')

    # check if path exists, get path from a dialogue window if not
    if (not os.path.exists(path_str)):
        path_str=tkinter.filedialog.asksaveasfilename()

    # open the file at the path
    with open(path_str, 'wb') as f:
        # Get raw bytes from the array
        raw_data = string_at(calib_array, calib_array_length)
        # write the raw bytes into the file
        f.write(raw_data)


    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    ob1_error_msg = 0

    # return error message
    return ob1_error_msg


# EMULATED VALVE CLASS DEFINITION ----------------------------------------------------------------------------
# an object of this class stores the channel pressures
# and the resistance of the setup
class emulated_valve:
    # initialise the object with 'None's and '-1's in the fields
    def __init__(self):
        # valve name string
        self.Device_Name = 'emulated_valve'.encode('ascii')

        # valve reference
        self.MUX_DRI_ID = None

        # which inlet the valve is currently set to
        self.inlet = -1

        return

    # find the currently set valve inlet
    def get_inlet(self):
        return self.inlet

    # set the valve inlet
    def set_inlet(self, inlet):
        self.inlet = inlet
        return


# INITIALISING THE VALVE EMULATOR -------------------------------------------------------------------------------
valve_em = emulated_valve()

# DEFINITIONS OF SDK FUNCTION ANALOGUES FOR THE MUX DISTRIBUTOR VALVE --------------------------------------------------
# initiate the valve device
def MUX_DRI_Initialization(
        # valve communication port of the PC (char array pointer)
        Visa_COM,
        # reference assigned to the valve
        MUX_DRI_ID_out=byref(c_int32())
):
    # in the emulator, just
    valve_em.MUX_DRI_ID = MUX_DRI_ID_out

    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    valve_error_msg = 0
    return valve_error_msg

# destroy communications with the valve
# in the emulator, do nothing
def MUX_DRI_Destructor(
        # reference to which valve is being used
        MUX_DRI_ID_in
):
    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    valve_error_msg = 0

    return valve_error_msg


# send an action command to the valve: 0 to home the valve, 1 to get the valve's serial number
def MUX_DRI_Send_Command(
        # reference to which valve is being used
        MUX_DRI_ID_in,
        # action command to the valve
        action,
        # answer array pointer - for getting the valve's serial number
        answer,
        # answer array length - for getting the valve's serial number
        length
):
    # homing the valve if getting command 0 - set to inlet 1 in the emulator
    if(action == 0):
        # set to inlet 0 and get the corresponding error message
        valve_error_msg = MUX_DRI_Set_Valve(MUX_DRI_ID_in,  # valve ID value
                                            c_int32(1),  # valve inlet
                                            0  # valve rotation direction (zero for shortest)
                                            )
    # getting the valve serial number if getting command 1 - just zeros in the emulator
    elif(action == 1):
        answer_ptr = cast(answer, POINTER(c_double * length))
        answer_array = answer_ptr.contents
        for i in range(0, length):
            answer_array[i] = '0'
        # define error message
        # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
        valve_error_msg = 0
    else:
        # define error message
        # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
        valve_error_msg = 0

    return valve_error_msg


# get the valve inlet data
def MUX_DRI_Get_Valve(
        # reference to which valve is being used
        MUX_DRI_ID_in,
        # where to write the data
        selected_Valve
):
    # get readings
    selected_Valve_ptr = cast(selected_Valve, POINTER(c_int32))
    selected_Valve_ptr.contents.value = valve_em.get_inlet()

    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    valve_error_msg = 0

    # return error message
    return valve_error_msg


# set the valve inlet
def MUX_DRI_Set_Valve(
        # reference to which valve is being used
        MUX_DRI_ID_in,
        # which inlet to set
        selected_Valve,
        # valve rotation directions: 0 for the shortest, 1 for clockwise, 2 for anticlockwise - irrelevant in the emulator
        Z_MUX_DRI_Rotation
):
    # set valve inlet - handling the cases when the selection is a Python int/float or a int32_t
    if (isinstance(selected_Valve, (int, float))):
        valve_em.set_inlet(selected_Valve)
    else:
        valve_em.set_inlet(selected_Valve.value)

    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    valve_error_msg = 0

    return valve_error_msg


# CONSTANTS SIGNIFYING VALVE COMMANDS ----------------------------------------------------------------------------------
# valve action commands: 0 to home the valve, 1 to get the valve's serial number
Z_MUX_DRI_Action_Home = 0
Z_MUX_DRI_Action_SerialNumber = 1

# valve rotation directions: 0 for the shortest, 1 for clockwise, 2 for anticlockwise
Z_MUX_DRI_Rotation_Shortest = 0
Z_MUX_DRI_Rotation_Clockwise = 1
Z_MUX_DRI_Rotation_CounterClockwise = 2
