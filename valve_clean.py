# VALVE_CLEAN.PY
# Use this script after your experiment to CLEAN A MUX DISTRIBUTOR VALVE

EMULATING = False

# IMPORTS --------------------------------------------------------------------------------------------------------------
# PYTHON PACKAGES
import time, datetime
import numpy as np, pandas as pd
import matplotlib, matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import threading
import tkinter, tkinter.filedialog
import os
import csv
import queue
from ctypes import *
from array import array

# ELVEFLOW SDK - if not emulating
if not(EMULATING):
    import sys
    sys.path.append(r'C:\Users\hslab1\Documents\ESI\ESI_SDK\DLL64')#add the path of the library here
    sys.path.append(r'C:\Users\hslab1\Documents\ESI\ESI_SDK\Python_64')#add the path of the LoadElveflow.py
    from Elveflow64 import *

# ELVEFLOW EMULATOR
else:
    from emulator import *
    matplotlib.use('tkagg')

# MAIN FUNCTION --------------------------------------------------------------------------------------------------------
def main():
    # initialise the valve
    valve_instrid = c_int32()
    print('Adding the VALVE...')
    valve_error_msg = MUX_DRI_Initialization("ASRL3::INSTR".encode('ascii'),
                                             byref(valve_instrid))
    if (valve_error_msg != 0):
        print('Valve addition error: %d' % valve_error_msg)
        exit(1)

    # get the valve ID value
    valve_instridval = valve_instrid.value
    # home the valve (necessary step for our MUX Distribtuion valve)
    answer = (c_char * 10)()
    valve_error_msg = MUX_DRI_Send_Command(valve_instridval,  # valve ID value
                                           0,  # valve action: 0 for home the valve
                                           answer,
                                           # char array for the answer - irrelevant here (needed to get a serial number)
                                           0
                                           # length of the answer array - irrelevant here (needed to get a serial number)
                                           )
    if (valve_error_msg != 0):
        print('Valve homing error: %d' % valve_error_msg)
        exit(1)

    print('Connect a syringe with cleaning liquid to the valve outlet.\n'+
          'Disconnect all tubing from inlets, but ensure there is a tray/paper towels underneath\n')

    finish = False
    while (not finish):
        for inlet in range(1, 13):
            # set the inlet to the next one
            valve_error_msg = MUX_DRI_Set_Valve(valve_instridval,  # valve ID value
                                                c_int32(inlet),  # valve inlet
                                                0  # valve rotation direction (zero for shortest)
                                                )
            if (valve_error_msg != 0):
                print('Valve setting error: %d' % valve_error_msg)
                exit(1)
            print('\nValve inlet set to '+str(inlet))
            input('Push liquid through the inlet, press any key when done: ')

        finish = (input('You have cleaned all inlets. Repeat with another liquid? (yes,no): ') != 'yes')

    print('Cleaning complete. Destroying valve communications...')
    # destroy valve communications
    valve_error_msg = MUX_DRI_Destructor(valve_instridval)
    if (valve_error_msg != 0):
        print('Valve destruction error: %d' % valve_error_msg)
        exit(1)

    return


# MAIN CALL ------------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    main()
