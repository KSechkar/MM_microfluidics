# PID_EXPERIMENT.PY
# Run a regular mother machine experiment with PI control (D control currently unsupported by Elveflow)

# IMPORTS --------------------------------------------------------------------------------------------------------------
# PYTHON PACKAGES
import time
import numpy as np, pandas as pd
import matplotlib, matplotlib.pyplot as plt
import threading
import tkinter, tkinter.filedialog
import os
import csv
import queue

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
        from_file = input('Do you want to load settings from a saved file? (yes, no) : ')
        if (from_file == 'yes'):
            # select the file
            loadfilewindow = tkinter.Tk()
            loadfilewindow.wm_attributes('-topmost', 1)
            loadfilewindow.withdraw()
            settings_file = tkinter.filedialog.askopenfilename()
            # load settings from the file
            still_todo=self.load_settings(settings_file)
        else:
            still_todo = {'OB-1 CHANNEL': True,
                          'FLOW CONTROLLER': True,
                          'OB-1-COMPUTER INTERACTIONS': True,
                          'SAFEGUARDS': True}

        # print('\nSET UP THE OB-1')    # ----------------------------------------------------------------------------------
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
            Calib_path = 'C:\\Users\\Public\\Desktop\\Calibration\\Calib.txt'
            if calib_type == 'default':
                ob1_error_msg = Elveflow_Calibration_Default(byref(self.Calib), 1000)
                if (ob1_error_msg != 0):
                    print('Default calibration error: %d' % ob1_error_msg)
                    exit(1)
                self.check_calibration()
                good_calibration=input('Happy with the calibration? (yes, no) : ')
                if (good_calibration=='yes'):
                    break

            if calib_type == 'load':
                ob1_error_msg = Elveflow_Calibration_Load(' '.encode('ascii'), byref(self.Calib), 1000)
                if (ob1_error_msg != 0):
                    print('Calibration loading error: %d' % ob1_error_msg)
                    exit(1)
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
                ob1_error_msg=OB1_Calib(self.OB1.value, self.Calib, 1000)
                if(ob1_error_msg != 0):
                    print('OB-1 calibration error: %d' % ob1_error_msg)
                    exit(1)
                ob1_error_msg = Elveflow_Calibration_Save(
                    Calib_path.encode('ascii'),
                    byref(self.Calib), 1000)
                if(ob1_error_msg != 0):
                    print('OB-1 calibration save error: %d' % ob1_error_msg)
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

        print('\nSPECIFY THE OB-1 SETUP') # ----------------------------------------------------------------------------
        if(still_todo['OB-1 CHANNEL']):
            self.ch = c_int32(int(input('Select the pressure and sensor channel to use (1, 2) : ')))
        else:
            print('(Channel number loaded from file - is %d)' % self.ch.value)
        print('Adding the flow sensor...')
        ob1_error_msg = OB1_Add_Sens(self.OB1,  # which OB-1 is being used
                                     self.ch.value,  # the selected channel
                                     4,  # sensor type - WE ONLY HAVE TYPE 4 SENSORS (MICRFOLUIDIC FLOW SENSORS FOR MAX +-80UL/MIN)
                                     1,  # 0 if analog, 1 if digital - OUR SENSORS ARE DIGITAL
                                     0,  # 0 if calibrated for water, 1 if calibrated for isopropanol - OUR SENSORS ARE CALIBRATED FOR WATER
                                     7,  # resolution bits (NOT the exact number thereof! refer to the walkthrough)
                                     0  # voltage for custom analog sensors - IRRELEVANT AS OUR SENSORS ARE DIGITAL
                                     )
        if (ob1_error_msg != 0):
            print('Sensor addition error: %d' % ob1_error_msg)
            exit(1)

        # print('\nFILL THE TUBING') # -----------------------------------------------------------------------------------
        self.fill_tubing()

        print('\nSET UP THE FLOW CONTROLLER') # ------------------------------------------------------------------------
        if(still_todo['FLOW CONTROLLER']):
            self.ref_flow = c_double(float(input('Specify the reference flow rate (ul/min) : ')))
            self.p_gain = float(input('Specify the flow controller\'s P gain : '))
            self.i_gain = float(input('Specify the flow controller\'s I gain : '))
            # self.d_gain = float(input('Specify the flow controller\'s D gain : '))  # D CONTROL CURRENTLY UNSUPPORTED BY ELVEFLOW
            self.min_flerrint = float(input('Input error integral lower bound for anti-windup (uL) : '))
            self.max_flerrint = float(input('Input error integral upper bound for anti-windup (uL) : '))
            set_p_bounds = input('Would you like to set non-default bounds on pressure? (yes, no) : ')
            if(set_p_bounds=='yes'):
                self.min_p_ctrl = float(input('Specify the minimum pressure control bound (mbar) : '))
                self.max_p_ctrl = float(input('Specify the maximum pressure control bound (mbar) : '))
            else:
                # if bounds are not specified, set them to default, i.e. physically possible values
                self.min_p_ctrl = 0.0
                self.max_p_ctrl = 2000.0
        else:
            print('(Loaded from file)')
        self.flerrint = 0.0 # initialise with zero error integral
        self.remote = False # REMOTE CONTROL CURRENTLY NOT WORKING

        print('\nSET OB1-COMPUTER INTERACTION PREFERENCES')  # ---------------------------------------------------------
        if(still_todo['OB1-COMPUTER INTERACTIONS']):
            self.dt_check = float(input('dt_check: how often you want to check on the OB-1 (seconds) : '))
            self.dt_log = float(input('dt_log: how often you want to log data (seconds) : '))
            short_term_memo_time = float(
                input('short_term_memo_time: how long you want to keep ALL most recent data in memory (seconds) : '))
            # convert from logging and remembering times to number of data points
            self.log_every_points = int(self.dt_log / self.dt_check)
            self.short_term_memo_size = int(short_term_memo_time / self.dt_check)+1
            # initialise short-term memory for the pressure, the flow and the measurement times
            self.stmemo_p = []
            self.stmemo_flow = []
            self.stmemo_time = []
            self.stmemo_ref = []
        else:
            print('(Loaded from file)')

        print('\nSET UP THE SAFEGUARDS') # -----------------------------------------------------------------------------
        if(still_todo['SAFEGUARDS']):
            self.make_safeguards()
        else:
            print('(Loaded from file)')

        # SAVE THE STARTING SETTINGS -----------------------------------------------------------------------------------
        save_filename=self.save_settings()
        print('\nStarting settings saved in %s' % save_filename)

        # GET READY TO DO CRUISE CONTROL -------------------------------------------------------------------------------
        self.doing_cruise_control = False
        self.logfilepath = ''
        # create OB-1 interaction thread
        self.OB1_thread = threading.Thread(target=self.cruise_control_OB1, daemon=True)
        # create user input thread
        self.user_thread = threading.Thread(target=self.cruise_control_user, daemon=True)
        # create a queue of user commands for the OB-1 thread
        self.user_cmd_queue = queue.Queue()
        # create a queue of messages to be printed when prompted by the OB-1 handler
        self.OB1_print_queue = queue.Queue()

        return

    # get settings from a txt file
    def load_settings(self, filename):
        # moving to the next non-empty and non-comment line
        def next_meaningful_line(current_line):
            next_line=current_line+1
            while (next_line < lines_total):
                if (lines[next_line] == '\n' or lines[next_line][0] == '#'):
                    next_line += 1
                else:
                    break
            # if end of file is reached, return next_line=lines_total
            # print(current_line, next_line)
            return next_line
        
        # open the file
        with open(filename, 'r') as file:
            # get the lines from the file
            lines = file.readlines()
            lines_total = len(lines)

            # initialise
            curr_line = 0
            still_todo={'OB-1 CHANNEL': True,
                        'FLOW CONTROLLER': True,
                        'OB1-COMPUTER INTERACTIONS': True,
                        'SAFEGUARDS': True}

            # go through the lines
            while(curr_line<lines_total):
                # read OB-1 channel
                if(lines[curr_line]=='OB-1 CHANNEL\n'):
                    still_todo['OB-1 CHANNEL'] = False
                    curr_line = next_meaningful_line(curr_line)
                    # get the channel
                    self.ch = c_int32(int(lines[curr_line].split()[2]))
                    curr_line = next_meaningful_line(curr_line)

                    # skip the 'END OB-1 CHANNEL' marker line
                    curr_line = next_meaningful_line(curr_line)
                    continue

                # read the reference and PI(D?) gains
                elif(lines[curr_line]=='FLOW CONTROLLER\n'):
                    still_todo['FLOW CONTROLLER'] = False
                    curr_line = next_meaningful_line(curr_line)

                    # see if we're running a remote control loop
                    self.remote = bool(int(lines[curr_line].split()[2]))
                    curr_line = next_meaningful_line(curr_line)
                    # get the reference flow
                    self.ref_flow = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # get the P gain
                    self.p_gain = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # get the I gain
                    self.i_gain = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # get the D gain
                    # self.d_gain = float(lines[curr_line].split()[2])    # D CONTROL CURRENTLY UNSUPPORTED BY ELVEFLOW
                    # curr_line = next_meaningful_line(curr_line)

                    # PARAMETERS FOR NON-REMOTE CONTROL ONLY
                    if not(self.remote):
                        # get the anti-windup bounds for error integral, if any specified
                        if(lines[curr_line].split()[0]=='min_flerrint'):
                            self.min_flerrint = float(lines[curr_line].split()[2])
                            curr_line = next_meaningful_line(curr_line)
                            self.max_flerrint = float(lines[curr_line].split()[2])
                            curr_line = next_meaningful_line(curr_line)
                        # get the user-defined pressure control bounds, if any specified
                        if(lines[curr_line].split()[0]=='min_p_ctrl'):
                            self.min_p_ctrl = float(lines[curr_line].split()[2])
                            curr_line = next_meaningful_line(curr_line)
                            self.max_p_ctrl = float(lines[curr_line].split()[2])
                            curr_line = next_meaningful_line(curr_line)
                        else:
                            # if bounds are not specified, set them to default
                            self.min_p_ctrl = 0.0
                            self.max_p_ctrl = 2000.0

                    # skip the 'END FLOW CONTROLLER' marker line
                    curr_line = next_meaningful_line(curr_line)
                    continue

                # read OB1-computer interaction settings
                elif(lines[curr_line]=='OB1-COMPUTER INTERACTIONS\n'):
                    still_todo['OB1-COMPUTER INTERACTIONS'] = False
                    curr_line = next_meaningful_line(curr_line)
                    # get the check time
                    self.dt_check = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # get the log time
                    self.dt_log = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # get the short-term memory time
                    short_term_memo_time = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # convert from logging and remembering times to number of data points
                    self.log_every_points = int(self.dt_log / self.dt_check)
                    self.short_term_memo_size = int(short_term_memo_time / self.dt_check)+1
                    # initialise short-term memory for the pressure, the flow and the measurement times
                    self.stmemo_p = []
                    self.stmemo_flow = []
                    self.stmemo_time = []
                    self.stmemo_ref = []

                    # skip the 'END OB1-COMPUTER INTERACTIONS' marker line
                    curr_line = next_meaningful_line(curr_line)
                    continue

                # read safeguards
                elif(lines[curr_line]=='SAFEGUARDS\n'):
                    if(still_todo['OB1-COMPUTER INTERACTIONS']):
                        print('Error: safeguards cannot be defined before OB1-computer interactions are specified!')
                        exit(1)
                    still_todo['SAFEGUARDS'] = False

                    # initialise the set of safeguards
                    curr_line = next_meaningful_line(curr_line)
                    p_bounds = []
                    p_lnub = []
                    flow_bounds = []
                    flow_lnub = []
                    safeguard_check_steps = []
                    self.safeguard_conds = []
                    # keep reading safeguards until a blank line is reached
                    while(lines[curr_line][0:14]!='END SAFEGUARDS'):
                        # read the pressure cutoff condition
                        cutoff_condition = lines[curr_line].split()
                        curr_cutoff_condition_entry = 0

                        # read the pressure cutoff condition, if there is one
                        if(cutoff_condition[curr_cutoff_condition_entry]!='p'):
                            # if no pressure condition is specified, the pressure condition is always true
                            p_bounds.append(0)
                            p_lnub.append(0)
                        else:
                            curr_cutoff_condition_entry += 1
                            # see if the pressure condition is <= or >=
                            if(cutoff_condition[curr_cutoff_condition_entry]=='<='):
                                p_lnub.append(-1)
                            elif(cutoff_condition[curr_cutoff_condition_entry]=='>='):
                                p_lnub.append(1)
                            else:
                                print('Error: invalid safeguard format!')
                                exit(1)
                            curr_cutoff_condition_entry += 1
                            # get the pressure threshold
                            p_bounds.append(float(cutoff_condition[curr_cutoff_condition_entry]))
                            curr_cutoff_condition_entry += 1
                            # skip the 'AND' if there is one
                            if(cutoff_condition[curr_cutoff_condition_entry]=='AND'):
                                curr_cutoff_condition_entry += 1
                        # read the flow cutoff condition, if there is one
                        if (cutoff_condition[curr_cutoff_condition_entry] != 'flow'):
                            # if no flow condition is specified, the pressure condition is always true
                            flow_bounds.append(0)
                            flow_lnub.append(0)
                            # if also no pressure condition and it's not an end-of-safeguards marker, something is off
                            if(p_lnub[-1]==0):
                                print('Error: invalid safeguard format!')
                                exit(1)
                        else:
                            curr_cutoff_condition_entry += 1
                            # see if the pressure condition is <= or >=
                            if (cutoff_condition[curr_cutoff_condition_entry] == '<='):
                                flow_lnub.append(-1)
                            elif (cutoff_condition[curr_cutoff_condition_entry] == '>='):
                                flow_lnub.append(1)
                            else:
                                print('Error: invalid safeguard format!')
                                exit(1)
                            curr_cutoff_condition_entry += 1
                            # get the pressure threshold
                            flow_bounds.append(float(cutoff_condition[curr_cutoff_condition_entry]))
                            curr_cutoff_condition_entry += 1

                        # skip the 'FOR'
                        curr_cutoff_condition_entry += 1

                        # get for how long the condition must be true to trigger the cutoff
                        safeguard_time = float(cutoff_condition[curr_cutoff_condition_entry])
                        safeguard_check_steps.append(int(safeguard_time / self.dt_check)+1)  # convert to number of data points in short-term memory
                        if (safeguard_check_steps[-1] > self.short_term_memo_size):
                            print('Error: the specified time exceeds short-term memory')
                            exit(1)
                        elif (safeguard_check_steps[-1] <= 0):
                            print('Error: the specified time window must be positive')
                            exit(1)

                        # record the interperatable condition string
                        self.safeguard_conds.append(lines[curr_line][:-1])

                        # move to the next line
                        curr_line = next_meaningful_line(curr_line)
                        
                        if(curr_line>=lines_total):
                            break

                    # record the safeguard specs as numpy arrays
                    # record the safeguard specs as numpy arrays
                    self.p_bounds = np.array(p_bounds)
                    self.p_lnub = np.array(p_lnub)
                    self.flow_bounds = np.array(flow_bounds)
                    self.flow_lnub = np.array(flow_lnub)
                    self.safeguard_check_steps = np.array(safeguard_check_steps)
                    self.num_safeguards = len(self.p_bounds)

                    # skip the 'END SAFEGUARDS' marker line
                    curr_line = next_meaningful_line(curr_line)
                    continue
                else:
                    # if the line is not recognised, move to the next one
                    curr_line = next_meaningful_line(curr_line)
                    continue

        # return the list of settings that still need to be entered manually
        return still_todo

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
            print('Connect all system components, excluding the resistance.' +
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
    
    # set up the safeguards
    def make_safeguards(self):
        add_safeguard = input('Do you want to add a pressure cutoff condition? (yes, no) : ')
        p_bounds = []
        p_lnub = []
        flow_bounds = []
        flow_lnub = []
        safeguard_check_steps = []
        self.safeguard_conds = []
        while (add_safeguard == 'yes'):
            print('\tIf a condition BOTH on pressure and flow specified, pressure will be cut off if BOTH are TRUE!')
            p_cond = input('\tIs there a pressure condition? (yes, no) : ')
            if (p_cond != 'yes'):
                p_bounds.append(0)
                p_lnub.append(0)
            else:
                safeguard_p_str = input(
                    '\t\tInput your pressure condition in the format [p <= x] or [p >= x] where x is the pressure threshold (mbar) : ')
                if (safeguard_p_str[0:5] == 'p <= '):
                    p_bounds.append(float(safeguard_p_str[5:]))
                    p_lnub.append(-1)
                elif (safeguard_p_str[0:5] == 'p >= '):
                    p_bounds.append(float(safeguard_p_str[5:]))
                    p_lnub.append(1)
                else:
                    print('Error: invalid format!')
                    continue
            flow_cond = input('\tIs there a flow condition? (yes, no) : ')
            if (flow_cond != 'yes'):
                flow_bounds.append(0)
                flow_lnub.append(0)
            else:
                safeguard_flow_str = input('\t\tInput your flow condition in the format [flow <= x] or [flow >= x] where x is the flow threshold (ul/min) : ')
                if (safeguard_flow_str[0:8] == 'flow <= '):
                    flow_bounds.append(float(safeguard_flow_str[8:]))
                    flow_lnub.append(-1)
                elif (safeguard_flow_str[0:8] == 'flow >= '):
                    flow_bounds.append(float(safeguard_flow_str[8:]))
                    flow_lnub.append(1)
                else:
                    print('Error: invalid format!')
                    continue

            # check the user has entered at least one condition
            if (p_cond == 'no' and flow_cond == 'no'):
                print('Error: at least one condition must be specified')
                continue

            safeguard_time = float(input('For how long must the condition be true to trigger the cutoff (seconds) : '))
            safeguard_check_steps.append(
                int(safeguard_time / self.dt_check)+1)  # convert to number of data points in short-term memory
            if (safeguard_check_steps[-1] > self.short_term_memo_size):
                print('Error: the specified time exceeds short-term memory')
                continue
            elif (safeguard_check_steps[-1] <= 0):
                print('Error: the specified must be positive')
                continue

            # make an interperatable condition string
            self.safeguard_conds.append('')
            if (p_cond == 'yes'):
                self.safeguard_conds[-1] = self.safeguard_conds[-1] + safeguard_p_str + ' mbar'
            if (flow_cond == 'yes'):
                if(p_cond == 'yes'):
                    self.safeguard_conds[-1] += ' AND '
                self.safeguard_conds[-1] = self.safeguard_conds[-1] + safeguard_flow_str + ' uL/min'
            self.safeguard_conds[-1] += ' FOR ' + str(safeguard_time) + ' s'

            # ask if another safeguard is to be added
            add_safeguard = input('\nDo you want to add another pressure cutoff condition? (yes, no) : ')

        # record the safeguard specs as numpy arrays
        self.p_bounds = np.array(p_bounds)
        self.p_lnub = np.array(p_lnub)
        self.flow_bounds = np.array(flow_bounds)
        self.flow_lnub = np.array(flow_lnub)
        self.safeguard_check_steps = np.array(safeguard_check_steps)
        self.num_safeguards = len(self.p_bounds)

        print('\nPressure cutoff conditions summary: ')
        for i in range(self.num_safeguards):
            print('\tCondition %d: %s' % (i, self.safeguard_conds[i]))
        return 

    # CRUISE CONTROL --------------------------------------------------------------------------------------------------

    # save the starting settings
    def save_settings(self):
        filename = 'latest_start_settings.txt'
        with open(filename, 'w') as file:
            file.write('OB-1 CHANNEL\n')
            file.write('ch = ' + str(self.ch) + '\n')
            file.write('END OB-1 CHANNEL\n')
            file.write('\n')

            file.write('FLOW CONTROLLER\n')
            file.write('remote = ' + str(int(self.remote)) + '\n')
            file.write('ref_flow = ' + str(self.ref_flow) + ' ul/min\n')
            file.write('p_gain = ' + str(self.p_gain) + '\n')
            file.write('i_gain = ' + str(self.i_gain) + '\n')
            # file.write('d_gain = ' + str(self.d_gain) + '\n') # D CONTROL CURRENTLY UNSUPPORTED BY ELVEFLOW
            if not(self.remote):
                file.write('min_flerrint = ' + str(self.min_flerrint) + '\n')
                file.write('max_flerrint = ' + str(self.max_flerrint) + '\n')
                file.write('min_p_ctrl = ' + str(self.min_p_ctrl) + ' mbar\n')
                file.write('max_p_ctrl = ' + str(self.max_p_ctrl) + ' mbar\n')
            file.write('END FLOW CONTROLLER\n')
            file.write('\n')

            file.write('OB1-COMPUTER INTERACTIONS\n')
            file.write('dt_check = ' + str(self.dt_check) + ' s\n')
            file.write('dt_log = ' + str(self.dt_log) + ' s\n')
            file.write('short_term_memo_time = ' + str((self.short_term_memo_size-1)*self.dt_check) + ' s\n')
            file.write('END OB1-COMPUTER INTERACTIONS\n')
            file.write('\n')

            file.write('SAFEGUARDS\n')
            for i in range(self.num_safeguards):
                file.write(self.safeguard_conds[i] + '\n')
            file.write('END SAFEGUARDS\n')
            file.write('\n')
        return os.path.abspath(filename)

    # CRUISE CONTROL FUNCTIONS -----------------------------------------------------------------------------------------
    # main thread for cruise control of the microfluidic flow
    def cruise_control(self, log_filename=r'OB1_PID_log.csv'):
        # indicate that cruise control is being done
        self.doing_cruise_control = True
        self.logfilepath = os.path.abspath(log_filename)
        # start writing the log file
        with(open(self.logfilepath, 'w', newline='')) as logfile:
            logwriter = csv.writer(logfile)
            logwriter.writerow(['Time (s)', 'Pressure (mbar)', 'Flow (ul/min)', 'Reference flow (ul/min)'])

        # start the threads
        self.OB1_thread.start()
        self.user_thread.start()

        # keep the main thread alive
        try:
            while self.doing_cruise_control:
                time.sleep(self.dt_check)
        except KeyboardInterrupt:
            self.stop_cruise_control()
            print('Cruise control keyboard-interrupted')

        return

    # handle interactions and records with the OB-1 during cruise control
    def cruise_control_OB1(self):
        cc_start_time = time.time() # start time of cruise control
        cc_check_cntr = 0 # counter for how many times the computer has checked on the OB-1

        # SET UP THE REMOTE PI(D?) LOOP - REMOTE LOOP CURRENTLY NOT WORKING
        if(self.remote):
            ob1_error_msg = OB1_Start_Remote_Measurement(self.OB1.value,    # which OB-1 is being used
                                                         byref(self.Calib), 1000)    # Calibration (do not touch)
            if(ob1_error_msg != 0):
                print('Remote measurement initiation error: %d' % ob1_error_msg)
                exit(1)
            # start the onsite PI controller
            ob1_error_msg = PID_Add_Remote(self.OB1.value,  # which OB-1 is being used for pressure supply
                                   self.ch,         # which channel of this OB-1 is being controlled
                                   self.OB1.value,  # which OB-1 is being used for flow sensing
                                   self.ch,         # which channel of this OB-1 is being used for flow sensing
                                   self.p_gain,     # P gain
                                   self.i_gain,     # I gain
                                   # self.d_gain,   # D CONTROL CURRENTLY UNSUPPORTED BY ELVEFLOW
                                   1)               # 1 if run, 0 if stop
            if(ob1_error_msg != 0):
                print('PID controller initiation error: %d' % ob1_error_msg)
                exit(1)
            # set the reference
            ob1_error_msg = OB1_Set_Remote_Target(self.OB1.value,   # which OB-1 is being used
                                          self.ch,          # which channel is being controlled
                                          self.ref_flow)    # reference flow rate
            if(ob1_error_msg != 0):
                print('Reference flow setting error: %d' % ob1_error_msg)
                exit(1)

        while self.doing_cruise_control:
            # HANDLE THE USER INPUT, IF ANY
            try:
                # get the user command and the argument
                user_cmd, user_cmd_arg0, user_cmd_arg1, user_cmd_arg2 = self.user_cmd_queue.get_nowait()
                # get the command type
                if (user_cmd == 0):  # 0 for stopping the cruise control
                    self.stop_cruise_control()
                    break
                elif (user_cmd == 1):  # 1 for changing reference flow
                    self.ref_flow = user_cmd_arg0
                elif (user_cmd == 2):  # 2 for changing the PI(D?) gains
                    # get the gains
                    self.p_gain = user_cmd_arg0
                    self.i_gain = user_cmd_arg1
                    # self.d_gain = user_cmd_arg2   # D CONTROL CURRENTLY UNSUPPORTED BY ELVEFLOW

                    # SET THE REMOTE LOOP GAINS, IF IT'S RUNNING
                    if(self.remote):
                        ob1_error_msg = PID_Set_Gains_Remote(self.OB1.value,  # which OB-1 is being used
                                                             self.ch,  # which channel is being controlled
                                                             self.p_gain,  # P gain
                                                             self.i_gain,  # I gain
                                                             # self.d_gain,     # D CONTROL CURRENTLY UNSUPPORTED BY ELVEFLOW
                                                             1)  # 1 if run, 0 if stop
            except:
                pass

            # GET READINGS FROM THE OB-1
            # get the time of the check - NOT from the start of cruise control
            t_check_absolute = time.time()
            # read the pressure and flow...
            p_read_c_double = c_double()  # initialise pressure reading
            flow_read_c_double = c_double()  # initialise flow reading
            # ...FROM THE REMOTE LOOP, IF IT'S RUNNING
            if(self.remote):
                print('You shouldn\'t be here...')
                # NOT WORKING, AND WHEN WE TRY TO MAKE IT WORK, WILL HAVE TO USE GET_REMOTE_DATA INSTEAD OF GET_PRESS AND GET_SENS
                # # pressure
                # ob1_error_msg = OB1_Get_Press(self.OB1.value,  # which OB-1 is being used
                #                       self.ch,  # which channel pressure is being read
                #                       1,
                #                       # 1 means all pressure and analog sensor readings actually measured, not taken for memory. Irrelevant for digital sensors
                #                       byref(self.Calib),  # calibration (do not touch)
                #                       byref(p_read),  # where to write the data
                #                       1000  # calibration (do not touch)
                #                       )
                # if(ob1_error_msg != 0):
                #     print('Remote pressure measurement error: %d' % ob1_error_msg)
                #     exit(1)
                # # flow
                # ob1_error_msg = OB1_Get_Sens(self.OB1.value,  # which OB-1 is being used
                #                              self.ch,  # which channel sensor is being read
                #                              byref(flow_read),  # where to write the data
                #                              1000  # calibration (do not touch)
                #                              )
                # if (ob1_error_msg != 0):
                #     print('Remote flow measurement error: %d' % ob1_error_msg)
                #     exit(1)
            # ...OR DIRECTLY, IF DOING PI(D?) CONTROL ON SITE
            else:
                # pressure
                ob1_error_msg = OB1_Get_Press(self.OB1.value,  # which OB-1 is being used
                                      self.ch,              # which channel pressure is being read
                                      1,                    # 1 means all pressure and analog sensor readings actually measured, not taken for memory. Irrelevant for digital sensors
                                      byref(self.Calib),    # calibration (do not touch)
                                      byref(p_read_c_double),        # where to write the data
                                      1000                  # calibration (do not touch)
                                      )
                if(ob1_error_msg != 0):
                    print('Pressure measurement error: %d' % ob1_error_msg)
                    exit(1)
                p_read = p_read_c_double.value
                # flow
                ob1_error_msg = OB1_Get_Sens_Data(self.OB1.value,  # which OB-1 is being used
                                  self.ch,  # which sensor is being read
                                  1,    # 1 means all pressure and analog sensor readings actually measured, not taken for memory. Irrelevant for digital sensors
                                  byref(flow_read_c_double)  # where to write the data
                                  )  # Acquire_data=1 -> read all the analog values
                if (ob1_error_msg != 0):
                    print('Flow measurement error: %d' % ob1_error_msg)
                    exit(1)
                flow_read = flow_read_c_double.value

            # CHECK THE SAFEGUARDS, CUT OFF THE PRESSURE IF NEEDED
            cutoff_condition_true, which_cutoff_condition = self.check_safeguards()
            if (cutoff_condition_true):
                self.stop_cruise_control()
                print('Cruise control cut off by safeguard condition %d : ' % which_cutoff_condition)
                print('\n\t' + self.safeguard_conds[which_cutoff_condition])
                break

            # DO PI(D?) CONTROL ON SITE IF NOT RUNNING A REMOTE LOOP
            if not(self.remote):
                # calculate pressure to supply to the channel
                p = self.PI_controller(flow_read)
                p_c_double = c_double(p)
                # set the calculated pressure on the OB-1
                ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                              self.ch,  # which channel is being controlled
                                              p_c_double,  # which pressure is being set
                                              byref(self.Calib), 1000  # calibration (do not touch)
                                              )
                if(ob1_error_msg != 0):
                    print('Pressure setting error: %d' % ob1_error_msg)
                    exit(1)

            # RECORD THE DATA IN SHORT-TERM MEMORY
            self.stmemo_time.append(t_check_absolute-cc_start_time) # time SINCE THE START OF CRUISE CONTROL
            self.stmemo_p.append(p_read)
            self.stmemo_flow.append(flow_read)
            self.stmemo_ref.append(self.ref_flow)
            # pop the oldest readings if short-term memory is full
            if(len(self.stmemo_p)>self.short_term_memo_size):
                self.stmemo_p.pop(0)
                self.stmemo_flow.pop(0)
                self.stmemo_time.pop(0)
                self.stmemo_ref.pop(0)

            # LOG THE DATA IF IT'S TIME TO DO SO
            if(cc_check_cntr % self.log_every_points == 0):
                with open(self.logfilepath, 'a', newline='') as logfile:
                    logwriter = csv.writer(logfile)
                    logwriter.writerow([self.stmemo_time[-1], self.stmemo_p[-1], self.stmemo_flow[-1], self.stmemo_ref[-1]])

            # UPDATE THE CHECK COUNTER AND WAIT FOR THE NEXT CHECK
            cc_check_cntr += 1
            time.sleep(self.dt_check-(time.time()-t_check_absolute))
        return

    # handle user input during cruise control
    def cruise_control_user(self):
        while self.doing_cruise_control:
            # First, print messages from the OB-1 handler, if any
            try:
                OB1_print = self.OB1_print_queue.get_nowait()
                print(1)
                print(OB1_print)
            except:
                pass

            # User input
            user_cmd = input("What do you want to do? (stop, set_ref, set_gains): ")

            if(user_cmd=='stop'):   # stop the cruise control
                print('Stopping cruise control...')
                self.user_cmd_queue.put((0,         # command code: 0 for stopping the cruise control
                                         0, 0, 0))   # args: irrelevant for cmd 0
                break
            elif(user_cmd=='set_ref'):  # set the reference flow
                ref_flow = float(input("Specify the reference flow (ul/min): "))
                self.user_cmd_queue.put((1,                 # command code: 1 for changing reference flow
                                         ref_flow, 0, 0))   # args: zeroth is the new ref flow, others irrelevant
            elif(user_cmd=='set_gains'):  # set the PI(D?) gains
                p_gain = float(input("Specify the new P gain: "))
                i_gain = float(input("Specify the new I gain: "))
                # d_gain = float(input("Specify the new D gain: "))  # D CONTROL CURRENTLY UNSUPPORTED BY ELVEFLOW
                self.user_cmd_queue.put((2,                 # command code: 2 for changing the PI(D?) gains
                                         # args
                                         p_gain,            # zeroth arg is the new P gain
                                         i_gain,            # first arg is the new I gain
                                         0))                # second arg is the new D gain - BUT D CONTROL CURRENTLY UNSUPPORTED BY ELVEFLOW
        return

    # stop cruise control
    def stop_cruise_control(self):
        self.doing_cruise_control = False

        # STOP THE REMOTE LOOP, IF RUNNING IT - REMOTE LOOP CURRENTLY NOT WORKING
        if (self.remote):
            ob1_error_msg = OB1_Stop_Remote_Measurement(self.OB1.value)
            ob1_error_msg = PID_Set_Running_Remote(self.OB1.value,  # which OB-1 is being used
                                                   self.ch,  # which channel is being controlled
                                                   0)  # 1 if run, 0 if stop

        # set all pressures to zero
        ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                      1,  # which channel is being controlled
                                      0,  # which pressure is being set
                                      byref(self.Calib), 1000  # calibration (do not touch)
                                      )
        ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                      1,  # which channel is being controlled
                                      0,  # which pressure is being set
                                      byref(self.Calib), 1000  # calibration (do not touch)
                                      )

        print('Cruise control stopped')
        return

    # check the safeguards, cut off the pressure if conditions met
    def check_safeguards(self):
        if(self.num_safeguards==0):
            # if no safeguards are specified, return False and 0 (to avoid errors)
            return False, 0
        else:
            any_cutoff_condition_true = False
            for i in range(self.num_safeguards):
                # condition can only be met if the period considered by the safeguard has elapsed since the beginning
                if(len(self.stmemo_p)>=self.safeguard_check_steps[i]):
                    p_cutoff_cond_true = (
                            ((self.stmemo_p[-self.safeguard_check_steps[i]:] <= self.p_bounds[i]).all() and self.p_lnub[i] == -1)
                            or
                            ((self.stmemo_p[-self.safeguard_check_steps[i]:] >= self.p_bounds[i]).all() and self.p_lnub[i] == 1)
                            or
                            self.p_lnub[i] == 0 # if no pressure condition is specified, the pressure condition is always true
                    )
                    flow_cutoff_cond_true = (
                            ((self.stmemo_flow[-self.safeguard_check_steps[i]:] <= self.flow_bounds[i]).all() and self.flow_lnub[i] == -1)
                            or
                            ((self.stmemo_flow[-self.safeguard_check_steps[i]:] >= self.flow_bounds[i]).all() and self.flow_lnub[i] == 1)
                            or
                            self.flow_lnub[i] == 0 # if no flow condition is specified, the flow condition is always true
                    )
                    if(p_cutoff_cond_true and flow_cutoff_cond_true):
                        print('!!!PRESSURE CUT-OFF CONDITION %d TRIGGERED!!!' % i)
                        any_cutoff_condition_true = True
                        break

            # return whether any cutoff condition is true and the index of the condition
            return any_cutoff_condition_true, i

    # PI control signal calculator
    def PI_controller(self, flow):
        # calculate the flow error
        flerr = self.ref_flow - flow

        # integrate the flow error
        flerrint = self.flerrint + flerr*self.dt_check
        # limit the integral term for anti-windup
        self.flerrint=max(self.min_flerrint, min(flerrint, self.max_flerrint))

        # calculate the pressure to supply
        p_calc = self.p_gain*flerr + self.i_gain*self.flerrint
        # clip the pressure to physically possible values (0-2000 mbar) and/or user-defined values
        p = max(max(0, self.min_p_ctrl), min(p_calc, self.max_p_ctrl, self.max_p_ctrl))

        # return the pressure to feed to the system
        return p

    # PLOTTING THE CRUISE CONTROL DATA ---------------------------------------------------------------------------------
    # general function for plotting data
    def plot_cc_data(self,
                     # variables plotted always
                     data_time,  # time since cruise control start
                     data_p,     # pressure (measured at source)
                     data_flow,  # flow rate (measured at the outlet)
                     data_ref,   # reference flow rate
                     # pressure and flow plot ranges
                     p_range=(-10, 2000),  # pressure range
                     flow_range=(-10, 80),  # flow rate range
                     # output file name
                     plotfilename='OB1_PID_log.png',
                     # show safeguards or not?
                     show_safeguards=False,
                     ):
        # if showing safeguards, initialise hatches depicting them
        if(show_safeguards):
            safeguard_hatches = ['/', '\\', '|', '-', '+', 'x', 'o', 'O', '.', '*']

        # initialise the figure with subplots
        fig, axs = plt.subplots(nrows=2, ncols=1)

        # plot the flow and reference flow in the same subfigure using matplotlib
        # plot formatting
        axs[0].grid()
        axs[0].set_ylim(bottom=flow_range[0], top=flow_range[1])
        # plot itself
        axs[0].plot(data_time, data_flow, label='Flow',
                    linestyle='-', color='navy')
        axs[0].plot(data_time, data_ref, label='Reference flow',
                    linestyle='--', color='steelblue')
        axs[0].set_xlabel('Time since cruise control start (s)')
        axs[0].set_ylabel('Flow rate (ul/min)')
        axs[0].legend(loc='upper left')
        # show safeguards if asked to do so
        if(show_safeguards):
            for i in range(0,self.num_safeguards):
                if(self.flow_lnub[i]==-1):
                    axs[0].axhspan(flow_range[0], self.flow_bounds[i],
                                   facecolor='grey', alpha=0.5, hatch=safeguard_hatches[i])
                elif(self.flow_lnub[i]==1):
                    axs[0].axhspan(self.flow_bounds[i], flow_range[1],
                                   facecolor='grey', alpha=0.5, hatch=safeguard_hatches[i])

        # plot the pressure in a separate subfigure
        # plot formatting
        axs[1].grid()
        axs[1].set_ylim(bottom=p_range[0], top=p_range[1])
        # plot
        axs[1].plot(data_time, data_p, label='Pressure',
                    linestyle='-', color='firebrick')
        axs[1].set_xlabel('Time since cruise control start (s)')
        axs[1].set_ylabel('Pressure (mbar)')
        axs[1].legend(loc='upper left')
        # show safeguards if asked to do so
        if(show_safeguards):
            for i in range(0,self.num_safeguards):
                if(self.p_lnub[i]==-1):
                    axs[1].axhspan(p_range[0], self.p_bounds[i],
                                   facecolor='grey', alpha=0.5, hatch=safeguard_hatches[i])
                elif(self.p_lnub[i]==1):
                    axs[1].axhspan(self.p_bounds[i], p_range[1],
                                   facecolor='grey', alpha=0.5, hatch=safeguard_hatches[i])

        # adjust the layout
        fig.tight_layout(pad=2.0)
        # save figure
        plt.savefig(plotfilename)
        return

    # plot the shrt-term memory
    def plot_stmemo(self,
                    plotfilename='OB1_PID_log.png'):
        self.plot_cc_data(self.stmemo_time, self.stmemo_p, self.stmemo_flow, self.stmemo_ref,
                          plotfilename=plotfilename)
        return

    # plot the logged data from a file
    def plot_log(self,
                 logfilename='OB1_PID_log.csv',
                 plotfilename='OB1_PID_log.png',
                 # show safeguards or not?
                 show_safeguards=False,
                 ):
        # read the log file
        log_df = pd.read_csv(logfilename)   # get the dataframe from csv
        log_time = log_df['Time (s)'].to_numpy()
        log_p = log_df['Pressure (mbar)'].to_numpy()
        log_flow = log_df['Flow (ul/min)'].to_numpy()
        log_ref = log_df['Reference flow (ul/min)'].to_numpy()

        # plot the data
        self.plot_cc_data(log_time, log_p, log_flow, log_ref,
                          plotfilename=plotfilename,
                          show_safeguards=show_safeguards)
        return


# MAIN FUNCTION --------------------------------------------------------------------------------------------------------
def main():
    # initialise the OB-1 manager
    Kenobi = OB1_manager()

    # begin cruise control
    Kenobi.cruise_control()

    # plot the short-term memory at the end
    Kenobi.plot_stmemo(plotfilename='OB1_PID_final_stmemo.png')

    # plot the logged data
    Kenobi.plot_log(show_safeguards=True)

    return


# MAIN CALL ------------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    main()