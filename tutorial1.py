# making sense of the tutorial in https://www.elveflow.com/microfluidic-applications/setup-microfluidic-flow-control/setup-environment-elveflow-sdk/

# ADD THE ELVEFLOW LIBRARY

import sys
sys.path.append(r'C:\Users\hslab1\Documents\ESI\ESI_SDK\DLL64')#add the path of the library here
sys.path.append(r'C:\Users\hslab1\Documents\ESI\ESI_SDK\Python_64')#add the path of the LoadElveflow.py
from ctypes import *
from array import array
from Elveflow64 import *

#
# Initialization of OB1 ( ! ! ! REMEMBER TO USE .encode('ascii') ! ! ! )
#
Kenobi = c_int32()
print("Instrument name and regulator types are hardcoded in the Python script")

# See User Guide to determine regulator types and NIMAX to determine the instrument name
# WE HAVE JUST TWO CHANNELS, BOTH TYPE 2 (0-2000 MBAR)
error = OB1_Initialization('0204CC5D'.encode('ascii'),  # OB-1 serial number (check by running NIMAX)
                           2,2,0,0, # Types of channels 1,2,3,4 respectively
                           byref(Kenobi)  # reference assigned to the OB-1
                           )

# All functions will return error codes to help you to debug your code, for further information refer to User Guide
print('error:%d' % error)
print("OB1 ID: %d" % Kenobi.value)

#
# Calibrate the OB-1
#

Calib = (c_double * 1000)()  # Always define array this way, calibration should have 1000 elements

while True:
    answer = input('select calibration type (default, load, new ) : ')
    Calib_path = 'C:\\Users\\Public\\Desktop\\Calibration\\Calib.txt'
    if answer == 'default':
        error = Elveflow_Calibration_Default(byref(Calib), 1000)
        break

    if answer == 'load':
        error = Elveflow_Calibration_Load(Calib_path.encode('ascii'), byref(Calib), 1000)
        break

    if answer == 'new':
        # check the calibration setup
        calib_ready='no'
        while (calib_ready!='yes'):
            calib_ready = input('New OB-1 calibration. Type yes to confirm all sensors are disconnected and pressure outlets are capped : ')

        OB1_Calib(Kenobi.value, Calib, 1000)
        error = Elveflow_Calibration_Save(
            Calib_path.encode('ascii'),
            # 'calinewbration.txt',
            byref(Calib), 1000)
        print('Calib saved in %s' % Calib_path.encode('ascii'))

        # check the main setup
        reconnected = 'no'
        while (reconnected != 'yes'):
            reconnected = input(
                'OB-1 calibration complete. Type yes to confirm you have reconnected all desired sensors and pressure outlets : ')
        # --------------- TODO: CALIBRATION VALIDATION ------------------
        break

#
# Initialisation of sensors
#

# Add two digital flow sensors with water calibration

print('error add digit flow sensor 1:%d' % error)
error=OB1_Add_Sens(Kenobi, # which OB-1 is being used
                   2,   # channel connected to the sensor
                   4,   # sensor type
                   1,   # 0 if analog, 1 if digital
                   0,   # 0 if calibrated for water, 1 if calibrated for isopropanol
                   7,   # resolution bits (NOT the exact number thereof! refer to the walkthrough)
                   0    # voltage for custom analog sensors (IRRELEVANT FOR US)
                   )
print('error add digit flow sensor 2:%d' % error)

#
# MAIN MANUAL LOOP
#

while True:
    answer = input('what to do (set_p, get_p, get_sens, or exit) : ')
    # select pressure on a channel
    if answer == 'set_p':
        # select the channel to manipulate (ask again if value unfeasible)
        set_channel = 0
        while (set_channel !=1 and set_channel !=2):
            set_channel = int(input("select channel(1-2) : "))
        set_channel = c_int32(set_channel)  # convert to c_int32

        # select the pressure to set (ask again if value unfeasible)
        set_pressure = -1
        while (set_pressure < 0 or set_pressure > 2000):
            set_pressure = float(input("select pressure (0 to 2000 mbars) : "))
        set_pressure = c_double(set_pressure)  # convert to c_double

        # set the desired pressure in the desired channel
        error = OB1_Set_Press(Kenobi.value,         # which OB-1 is being used
                              set_channel,          # which channel is being controlled
                              set_pressure,         # which pressure is being set
                              byref(Calib), 1000    # calibration (do not touch)
                              )

    # read a sensor
    if answer == "get_sens":
        # initialise the sensor data ouptut
        data_sens = c_double()

        # select the sensor to check (ask again if value infeasible)
        set_channel = 0
        while (set_channel !=1 and set_channel !=2):
            set_channel = int(input("select sensor (1-2) : "))
        set_channel = c_int32(set_channel)  # convert to c_int32

        # read the desired sensor
        error = OB1_Get_Sens_Data(Kenobi.value,     # which OB-1 is being used
                                  set_channel,      # which sensor is being read
                                  1,                # 1 means all pressure and analog sensor readings actually measured, not taken for memory. Irrelevant for digital sensors
                                  byref(data_sens)  # where to write the data
                                  )  # Acquire_data=1 -> read all the analog values
        print('Sensor ', set_channel.value, ' flow: ', data_sens.value, ' uL/min')

    if answer == 'get_p':
        # initialise the pressure data output
        data_p = c_double()

        # select the pressure channel to check (ask again if value unfeasible)
        get_channel = 0
        while (get_channel != 1 and get_channel != 2):
            get_channel = int(input("select channel(1-2) : "))
        get_channel = c_int32(get_channel)  # convert to c_int32

        error = OB1_Get_Press(Kenobi.value,     # which OB-1 is being used
                              get_channel,      # which channel pressure is being read
                              1,                # 1 means all pressure and analog sensor readings actually measured, not taken for memory. Irrelevant for digital sensors
                              byref(Calib),     # calibration (do not touch)
                              byref(data_p),    # where to write the data
                              1000              # calibration (do not touch)
                              )
        print('error: ', error)
        print('Channel ', get_channel, ' pressure : ', data_p.value, ' mbar')

    print('error :', error)

    if answer == 'exit':
        # set all pressures to zero
        error = OB1_Set_Press(Kenobi.value,  # which OB-1 is being used
                              1,  # which channel is being controlled
                              0,  # which pressure is being set
                              byref(Calib), 1000  # calibration (do not touch)
                              )
        error = OB1_Set_Press(Kenobi.value,  # which OB-1 is being used
                              1,  # which channel is being controlled
                              0,  # which pressure is being set
                              byref(Calib), 1000  # calibration (do not touch)
                              )

        break

