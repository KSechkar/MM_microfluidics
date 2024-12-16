# PID_EXPERIMENT.PY
# Run a rehular mother machine experiment with PID control

# IMPORTS --------------------------------------------------------------------------------------------------------------
# PYTHON PACKAGES
import time
import numpy as np
import matplotlib, matplotlib.pyplot as plt
import threading

# ELVEFLOW SDK
import sys
sys.path.append(r'C:\Users\hslab1\Documents\ESI\ESI_SDK\DLL64')#add the path of the library here
sys.path.append(r'C:\Users\hslab1\Documents\ESI\ESI_SDK\Python_64')#add the path of the LoadElveflow.py
from ctypes import *
from array import array
from Elveflow64 import *

# OB-1 MANAGER CLASS ---------------------------------------------------------------------------------------------------
class OB1_manager:
    # INITIALISATION AND SETUP -----------------------------------------------------------------------------------------
    # initialise (guides the user through setting up the microfluidics)
    def __init__(self):
        print('\nSET RECORD-KEEPING PREFERENCES')     # ------------------------------------------------------------------
        
        dt_check=float(input('dt_check: how often you want to check on the OB-1 (seconds) : '))
        dt_log=float(input('dt_log: how often you want to log data (seconds) : '))
        short_term_memo_time=float(input('short_term_memo_time: how long you want to keep ALL most recent data in memory (seconds) : '))
        # convert from logging and remembering times to number of data points
        log_every_points = int(dt_log / dt_check)
        short_term_memo_size = int(short_term_memo_time / dt_check)
        
        
        print('\nSET UP THE OB-1')    # ----------------------------------------------------------------------------------
        print('Initialising OB-1...')
        self.OB1 = c_int32()
        ob1_error_msg = OB1_Initialization('0204CC5D'.encode('ascii'),  # OB-1 self.OB1's serial number (check by running NIMAX)
                                   2, 2, 0, 0,                  # Types of channels 1,2,3,4 respectively - WE HAVE JUST TWO CHANNELS, BOTH TYPE 2 (0-2000 MBAR)
                                   byref(self.OB1))               # reference assigned to the OB-1     
        if (ob1_error_msg != 0):
            print('OB-1 initialisation error: %d' % ob1_error_msg)
            exit(1)
        while True:
            self.Calib = (c_double * 1000)()  # Always define array this way, calibration should have 1000 elements
            calib_type = input('Select OB-1 calibration (default, load, new ) : ')
            Calib_path = 'C:\\Users\\Public\\Desktop\\Calibration\\self.Calib.txt'
            if calib_type == 'default':
                ob1_error_msg = Elveflow_Calibration_Default(byref(self.Calib), 1000)
                self.check_calibration()
                good_calibration=input('Happy with the calibration? (yes, no) : ')
                if (good_calibration=='yes'):
                    break

            if calib_type == 'load':
                ob1_error_msg = Elveflow_Calibration_Load(Calib_path.encode('ascii'), byref(self.Calib), 1000)
                self.check_calibration()
                good_calibration = input('Happy with the calibration? (yes, no) : ')
                if (good_calibration == 'yes'):
                    break

            if calib_type == 'new':
                # check if the user has assembled the calibration setup
                calib_ready = 'no'
                while (calib_ready != 'yes'):
                    calib_ready = input('New OB-1 calibration. Type yes to confirm all sensors are disconnected and pressure outlets are capped : ')
                print('Calibrating the OB-1...')
                OB1_Calib(self.OB1.value, self.Calib, 1000)
                ob1_error_msg = Elveflow_Calibration_Save(
                    Calib_path.encode('ascii'),
                    byref(self.Calib), 1000)
                if(ob1_error_msg != 0):
                    print('OB-1 calibration error: %d' % ob1_error_msg)
                    exit(1)
                print('Calibration saved in %s' % Calib_path.encode('ascii'))
                self.check_calibration()
                good_calibration = input('Happy with the calibration? (yes, no) : ')
                if (good_calibration == 'yes'):
                    # check the main setup
                    reconnected = 'no'
                    while (reconnected != 'yes'):
                        reconnected = input('OB-1 calibration complete. Type yes to confirm you have reconnected all desired sensors and pressure outlets : ')
                    break
        
        print('\nSPECIFY THE OB-1 SETUP')
        self.ch = int(input('Select the pressure and sensor channel to use (1, 2) : '))
        print('Adding the flow sensor...')
        ob1_error_msg = OB1_Add_Sens(self.OB1,  # which OB-1 is being used
                                     self.ch,  # the selected channel
                                     4,  # sensor type - WE ONLY HAVE TYPE 4 SENSORS (MICRFOLUIDIC FLOW SENSORS FOR MAX +-80UL/MIN)
                                     1,  # 0 if analog, 1 if digital - OUR SENSORS ARE DIGITAL
                                     0,  # 0 if calibrated for water, 1 if calibrated for isopropanol - OUR SENSORS ARE CALIBRATED FOR WATER
                                     7,  # resolution bits (NOT the exact number thereof! refer to the walkthrough)
                                     0  # voltage for custom analog sensors - IRRELEVANT AS OUR SENSORS ARE DIGITAL
                                     )
        if (ob1_error_msg != 0):
            print('Sensor addition error: %d' % ob1_error_msg)
            exit(1)

        print('\nFILL THE TUBING')
        self.fill_tubing()
        
        return
    
    # check calibration
    def check_calibration(self):
        print('Checking calibration...')

        ref_ps=[10, 100, 1000, 2000] # reference pressures to consider
        for ref_p in ref_ps:
            print('\tChecking calibration at ' + str(ref_p) +' mbar...')
            # set reference pressures
            for ch in [1, 2]:
                ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                      ch,  # which channel is being controlled
                                      ref_p,  # which pressure is being set
                                      byref(self.Calib), 1000)
                if (ob1_error_msg != 0):
                    print('Pressure setting error: %d' % ob1_error_msg)
                    exit(1)
            # wait for the pressure to stabilise
            time.sleep(1)
            # read pressures
            p_offsets=[]
            for ch in [1, 2]:
                p_ch = c_double()
                ob1_error_msg = OB1_Get_Press(self.OB1.value,  # which OB-1 is being used
                                  ch,  # which channel pressure is being read
                                  1, # 1 means all pressure and analog sensor readings actually measured, not taken for memory. Irrelevant for digital sensors
                                  byref(self.Calib),  # calibration (do not touch)
                                  byref(p_ch),  # where to write the data
                                  1000)  # calibration (do not touch)
                if (ob1_error_msg != 0):
                    print('Pressure measurement error: %d' % ob1_error_msg)
                    exit(1)
                p_offsets.append(p_ch.value-ref_p)
            print('\t\tOffsets (mbar): channel 1 : ' + str(np.round(p_offsets[0],2))
                  + '; channel 2 : ' + str(np.round(p_offsets[1],2)))
        # set all pressures to zero
        for ch in [1, 2]:
            ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                  ch,  # which channel is being controlled
                                  0,  # which pressure is being set
                                  byref(self.Calib), 1000)
            if (ob1_error_msg != 0):
                print('Pressure setting error: %d' % ob1_error_msg)
                exit(1)
        return

    # fill the tubing with liquid
    def fill_tubing(self):
        # TUBING UP TO THE RESISTANCE
        ready_for_filling = 'no'
        while (ready_for_filling != 'yes'):
            print('Connect all system components up the chip, excluding the resistance.' +
                  '\nPut the outlet into the purge tube.' +
                  '\nThe OB-1 will apply a constant pressure to fill the tubing with liquid.' +
                  '\nOnce the tubing is filled with liquid, press any key.')
            ready_for_filling = input('Are you ready? (yes, no) : ')
        ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                              self.ch,  # which channel is being controlled
                              1000,  # which pressure is being set
                              byref(self.Calib), 1000)
        if (ob1_error_msg != 0):
            print('Pressure setting error: %d' % ob1_error_msg)
            exit(1)
        input('Press any key when done : ')
        ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                      self.ch,  # which channel is being controlled
                                      0,  # which pressure is being set - zero when done
                                      byref(self.Calib), 1000)
        if (ob1_error_msg != 0):
            print('Pressure setting error: %d' % ob1_error_msg)
            exit(1)

        # RESISTANCE
        ready_for_filling = 'no'
        while (ready_for_filling != 'yes'):
            print('\nConnect the resistor, the outlet end facing the purge tube.' +
                  '\nThe OB-1 will apply a constant pressure to fill the resistor with liquid.' +
                  '\nOnce the liduid starts coming out, press any key.')
            ready_for_filling = input('Are you ready? (yes, no) : ')
        ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                      self.ch,  # which channel is being controlled
                                      1000,  # which pressure is being set
                                      byref(self.Calib), 1000)
        if (ob1_error_msg != 0):
            print('Pressure setting error: %d' % ob1_error_msg)
            exit(1)
        input('Press any key when done : ')
        ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                      self.ch,  # which channel is being controlled
                                      0,  # which pressure is being set - zero when done
                                      byref(self.Calib), 1000)
        if (ob1_error_msg != 0):
            print('Pressure setting error: %d' % ob1_error_msg)
            exit(1)

        # ANY REMAINING TUBING
        fill_more = input('\nDo you need to fill more tubing? (yes, no) : ')
        while(fill_more=='yes'):
            ready_for_filling = 'no'
            while (ready_for_filling != 'yes'):
                print('\nAssemble your setup.' +
                      '\nThe OB-1 will apply a constant pressure to fill the tubing with liquid.' +
                      '\nOnce the liduid starts coming out, press any key.')
                ready_for_filling = input('Are you ready? (yes, no) : ')
            ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                          self.ch,  # which channel is being controlled
                                          1000,  # which pressure is being set
                                          byref(self.Calib), 1000)
            if (ob1_error_msg != 0):
                print('Pressure setting error: %d' % ob1_error_msg)
                exit(1)
            input('Press any key when done : ')
            ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                          self.ch,  # which channel is being controlled
                                          0,  # which pressure is being set - zero when done
                                          byref(self.Calib), 1000)
            if (ob1_error_msg != 0):
                print('Pressure setting error: %d' % ob1_error_msg)
                exit(1)
            fill_more = input('Do you need to fill more tubing? (yes, no) : ')

        return


    # CRUISE CONTROL --------------------------------------------------------------------------------------------------
    # start cruise control of the microfluidic flow
    def cruise_control(self):
        return

    # handle interactions with the OB-1 during cruise control
    def cruise_control_OB1(self):
        return

    # handle user input during cruise control
    def cruise_control_user(self):
        return

# MAIN FUNCTION --------------------------------------------------------------------------------------------------------
def main():
    # initialise the OB-1 manager
    OB1 = OB1_manager()

    # begin cruise control
    OB1.cruise_control()

    return


# MAIN CALL ------------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    main()