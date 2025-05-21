# EMULATOR.PY - emulator of Elveflow SDK for prototyping code without the OB1 and/or the valve connected

# PACKAGE IMPORTS
from math import pi
from ctypes import *

# elveflow imports - SELECTIVE!
import sys
sys.path.append(r'D:\CODE\MM_microfluidics\Elveflow_SDK\DLL64')#add the path of the library here
sys.path.append(r'D:\CODE\MM_microfluidics\Elveflow_SDK\Python_64')#add the path of the LoadElveflow.py
from Elveflow64 import Elveflow_Calibration_Default, Elveflow_Calibration_Load, Elveflow_Calibration_Save

# EMULATED OB1 CLASS DEFINITION ----------------------------------------------------------------------------
# an object of this class stores the channel pressures
# and the resistance of the setup
class emulated_OB1:
    # initialise the object with 'None's and '-1's in the fields
    def __init__(self):
        # OB-1 name string
        self.Device_Name = 'emulated_OB1'.encode('ascii')

        # OB-1 reference
        self.OB1_ID = None

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

# DEFINITIONS OF SDK FUNCTION ANALOGUES --------------------------------------------------------------------
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
    OB1_em.ch_sensors_present[channel_1_to_4] = True

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
    sens_data.contents.value=OB1_em.get_flow(channel_1_to_4)

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
    # set readings
    pressure.contents.value = OB1_em.ch_pressures[channel_1_to_4]

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
    # set pressure
    OB1_em.ch_pressures[channel_1_to_4]=pressure

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
    # set pressures
    for i in range(0,pressure_array_length):
        OB1_em.ch_pressures[i]=pressure_array_in[i]

    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    ob1_error_msg = 0

    # return error message
    return ob1_error_msg


# calibrate the OB-1
# in the emulator, just return a default Elveflow calibration array
def OB1_Calib(
        # reference to which OB-1 is being used
        OB1_ID,
        # calibration array
        calib_array_out,
        # calibration array length (do not touch!)
        calib_array_length = 1000
):
    # get the deafult Elveflow Calibration array
    calib_array_out=Elveflow_Calibration_Default(calib_array_out, calib_array_length)

    # define error message
    # TBD: make it consistent with the SDK manual. For now, always 0 (all OK)
    ob1_error_msg = 0

    # return error message
    return ob1_error_msg
