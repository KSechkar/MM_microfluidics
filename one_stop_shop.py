# ONE_STOP_SHOP.PY
# For running all microfluidic experiments

EMULATING = False

# DEVICE NAMES AND PORTS - CHECK ON NIMAX IF GETTING INITIALISATION ERRORS ---------------------------------------------
OB1_NAME = '0204CC5D'
VALVE_PORT ='ASRL3::INSTR'
RECIRC_PORT = 'ASRL5::INSTR'

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

def get_valid_input_float(prompt: str) -> float:
    while True:
        try:
            x = input(prompt)
            return float(x)
        except ValueError:
            print(f"{x} is not valid, must be parseable to a float. Try again!")

def get_valid_input_int(prompt: str, allowed:list[int]|None = None) -> int:
    while True:
        try:
            x = input(prompt)
            if (allowed is not None) and (x not in allowed):
                print(f"{x} is not in {allowed}")
                continue
            return int(x)
        except ValueError:
            print(f"{x} is not valid, must be parseable to an int. Try again!")

# OB-1 MANAGER CLASS ---------------------------------------------------------------------------------------------------
class OB1_manager:
    # INITIALISATION AND SETUP -----------------------------------------------------------------------------------------
    # initialise (guides the user through setting up the microfluidics)
    def __init__(self):
        # initialise channels
        self.channels = [
            channel_manager(1),  # first channel
            channel_manager(2)   # second channel
        ]
        # initialise MUX distribution valve
        self.valve=valve_manager()
        # initialise the Recirculation valve
        self.recirc=recirc_manager()

        from_file = input('Do you want to load settings from a saved file? (yes, no) : ')
        if (from_file == 'yes'):
            # select the file
            loadfilewindow = tkinter.Tk()
            loadfilewindow.wm_attributes('-topmost', 1)
            loadfilewindow.withdraw()
            #settings_file = tkinter.filedia.askopenfilename()
            settings_file = tkinter.filedialog.askopenfilename()
            # load settings from the file
            interactions_still_todo = self.load_settings(settings_file)
        else:
            # specify the channel(s) in use
            ch1_in_use = input('Is CHANNEL 1 in use? (yes, no) : ')
            if (ch1_in_use == 'yes'):
                self.channels[0].in_use=True
            ch2_in_use = input('Is CHANNEL 2 in use? (yes, no) : ')
            if (ch2_in_use == 'yes'):
                self.channels[1].in_use=True
            valve_in_use = input('Are you using a DISTRIBUTION VALVE? (yes, no) : ')
            if(valve_in_use == 'yes'):
                self.valve.in_use = True
            recirc_in_use = input('Are you using a RECIRCULATION VALVE? (yes, no) : ')
            if (recirc_in_use == 'yes'):
                self.recirc.in_use = True

            # specify that the OB-1-computer interaction settings are yet to be specified
            interactions_still_todo = True
            # specify that all the settings for the channels in use are yet to be selected
            for ch in self.channels:
                ch.still_todo = {'FLOW CONTROLLER': True,
                                 'SAFEGUARDS': True}
            # specify if the settings for the valve need to be selected
            if (self.valve.in_use):
                self.valve.still_todo = {'INTERACTIONS': True,
                                 'OPERATIONS': True}
            # specify if the settings for the valve need to be selected
            if (self.recirc.in_use):
                self.recirc.still_todo = {'INTERACTIONS': True,
                                         'OPERATIONS': True}

        # print('\nSET UP THE OB-1')    # ----------------------------------------------------------------------------------
        print('Initialising OB-1...')
        self.OB1 = c_int32()
        ob1_error_msg = OB1_Initialization(OB1_NAME.encode('ascii'),  # OB-1 self.OB1's serial number (check by running NIMAX)
                                   2, 2, 0, 0,                  # Types of channels 1,2,3,4 respectively - WE HAVE JUST TWO CHANNELS, BOTH TYPE 2 (0-2000 MBAR)
                                   byref(self.OB1))               # reference assigned to the OB-1
        if (ob1_error_msg != 0):
            print('OB-1 initialisation error: %d' % ob1_error_msg)
            exit(1)

        while True:
            self.Calib = (c_double * 1000)()  # Always define array this way, calibration should have 1000 elements
            calib_type = input('Select OB-1 calibration (default, load, new ) : ')
            Calib_path = r'C:\Users\Public\Desktop\Calibration\Calib'
            if calib_type == 'default':
                ob1_error_msg = Elveflow_Calibration_Default(byref(self.Calib), 1000)
                if (ob1_error_msg != 0):
                    print('Default calibration error: %d' % ob1_error_msg)
                    exit(1)
                checking_calibration = input('Do you want to check the calibration? (yes, no) : ')
                if(checking_calibration=='yes'):
                    self.check_calibration()
                    good_calibration=input('Happy with the calibration? (yes, no) : ')
                    if (good_calibration=='yes'):
                        break
                else:
                    break

            if calib_type == 'load':
                ob1_error_msg = Elveflow_Calibration_Load(' '.encode('ascii'), byref(self.Calib), 1000)
                if (ob1_error_msg != 0):
                    print('Calibration loading error: %d' % ob1_error_msg)
                    exit(1)
                checking_calibration = input('Do you want to check the calibration? (yes, no) : ')
                if (checking_calibration == 'yes'):
                    self.check_calibration()
                    good_calibration = input('Happy with the calibration? (yes, no) : ')
                    if (good_calibration == 'yes'):
                        break
                else:
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
                print('Calibartion complete')
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

        print('\nADDING CHANNELS') # -----------------------------------------------------------------------------------
        for ch in self.channels:
            if(ch.in_use):  # add the flow sensor if the channel is in use
                print('Adding the flow sensor for CHANNEL '+str(ch.id)+'...')
                ob1_error_msg = OB1_Add_Sens(self.OB1,  # which OB-1 is being used
                                             ch.id,  # the selected channel
                                             4,  # sensor type - WE ONLY HAVE TYPE 4 SENSORS (MICRFOLUIDIC FLOW SENSORS FOR MAX +-80UL/MIN)
                                             1,  # 0 if ana, 1 if digital - OUR SENSORS ARE DIGITAL
                                             0,  # 0 if calibrated for water, 1 if calibrated for isopropanol - OUR SENSORS ARE CALIBRATED FOR WATER
                                             7,  # resolution bits (NOT the exact number thereof! refer to the walkthrough)
                                             0  # voltage for custom ana sensors - IRRELEVANT AS OUR SENSORS ARE DIGITAL
                                             )
                if (ob1_error_msg != 0):
                    print('Sensor addition error: %d' % ob1_error_msg)
                    exit(1)
                print('Flow sensor for CHANNEL '+str(ch.id)+' added')

        print('\nSET OB1-COMPUTER INTERACTION PREFERENCES')  # ---------------------------------------------------------
        if (interactions_still_todo):
            self.dt_check = get_valid_input_float('dt_check: how often you want to check on the OB-1 (seconds) : ')
            self.dt_log = get_valid_input_float('dt_log: how often you want to log OB-1 data (seconds) : ')
            short_term_memo_dur = float(
                input('short_term_memo_dur: how long you want to keep ALL most recent OB-1 data in memory (seconds) : '))
            # convert from logging and remembering times to number of data points
            self.log_every_points = int(self.dt_log / self.dt_check)
            self.short_term_memo_size = int(short_term_memo_dur / self.dt_check) + 1
            # initialise the variables for the starting time of cruise control
            self.cc_start_time = -1  # for clarity, initialise with an impossible, negative value
        else:
            print('(Loaded from file)')

        print('\nSET UP THE FLOW CONTROLLERS') # ------------------------------------------------------------------------
        for ch in self.channels:
            if(ch.in_use):
                print('Set up the controller for CHANNEL ' + str(ch.id))
                if(ch.still_todo['FLOW CONTROLLER']):
                    ch.ref_flow = get_valid_input_float('Specify the reference flow rate (ul/min) : ')
                    ch.p_gain = get_valid_input_float('Specify the flow controller\'s P gain : ')
                    ch.i_gain = get_valid_input_float('Specify the flow controller\'s I gain : ')
                    ch.d_gain = get_valid_input_float('Specify the flow controller\'s D gain : ')
                    ch.min_flerrint = get_valid_input_float('Input error integral lower bound for anti-windup (uL) : ')
                    ch.max_flerrint = get_valid_input_float('Input error integral upper bound for anti-windup (uL) : ')
                    set_p_bounds = input('Would you like to set non-default bounds on pressure? (yes, no) : ')
                    if(set_p_bounds=='yes'):
                        ch.min_press_ctrl = get_valid_input_float('Specify the minimum pressure control bound (mbar) : ')
                        ch.max_p_ctrl = get_valid_input_float('Specify the maximum pressure control bound (mbar) : ')
                    else:
                        # if bounds are not specified, set them to default, i.e. physically possible values
                        ch.min_press_ctrl = 0.0
                        ch.max_p_ctrl = 2000.0
                else:
                    print('(Loaded from file)')
                ch.flerrint = 0.0 # initialise with zero error integral

        print('\nSET UP THE SAFEGUARDS') # -----------------------------------------------------------------------------
        for ch in self.channels:
            if (ch.in_use):
                print('Set up the safeguards for CHANNEL ' + str(ch.id))
                if (ch.still_todo['FLOW CONTROLLER']):
                    self.make_channel_safeguards(ch)
                else:
                    print('(Loaded from file)')

        print('\nSET UP THE DISTRIBUTION VALVE') # ----------------------------------------------------------------------------------
        if(self.valve.in_use):
            # load the valve
            self.valve.instrid = c_int32()
            print('Adding the VALVE...')
            valve_error_msg = MUX_DRI_Initialization(VALVE_PORT.encode('ascii'),
                                                     byref(self.valve.instrid))
            if (valve_error_msg != 0):
                print('Valve addition error: %d' % valve_error_msg)
                exit(1)
            # get the valve ID value
            self.valve.instridval = self.valve.instrid.value
            # if EMULATING, overried with the ID 1 for the Python dummy script to work
            if(EMULATING):
                self.valve.instridval = 1
            # home the valve (necessary step for our MUX Distribtuion valve)
            answer=(c_char * 10)()

            valve_error_msg = MUX_DRI_Send_Command(self.valve.instridval,  # valve ID value
                                                   0, # valve action: o for 'home the valve'
                                                   answer,  # char array for the answer - irrelevant here (needed to get a serial number)
                                                   0    # length of the answer array - irrelevant here (needed to get a serial number)
                                                   )
            if (valve_error_msg != 0):
                print('Valve homing error: %d' % ob1_error_msg)
                exit(1)

            # set up valve preferences
            # VALVE-COMPUTER INTERACTIONS
            if(self.valve.still_todo['INTERACTIONS']):
                self.valve.dt_check = get_valid_input_float('valve_dt_check: how often you want the computer to check on the VALVE (seconds) : ')
                self.valve.dt_log = get_valid_input_float('valve_dt_log: how often you want to log VALVE data (seconds) : ')
                self.valve.short_term_memo_dur = float(
                    input('valve_short_term_memo_dur: how long you want to keep ALL most recent VALVE data in memory (seconds) : '))
                # convert from logging and remembering times to number of data points
                self.valve.log_every_points = int(self.valve.dt_log / self.valve.dt_check)

            # VALVE OPERATIONS
            if(self.valve.still_todo['OPERATIONS']):
                self.valve.mode = input('Specify valve mode (set, pwm, set_scripted, pwm_scripted) : ')
                # specify compound-of-interest concentrations in all inlets
                inlet_cntr = 1
                inlet_concs = []
                while (True):
                    user_defined_conc = get_valid_input_float('COI conc in inlet ' + str(inlet_cntr) +
                                                    '? (-1 to stop entering): ')
                    if (user_defined_conc == -1):
                        break
                    inlet_concs.append(user_defined_conc)
                    inlet_cntr += 1
                self.valve.inlet_concs = np.array(inlet_concs)
                # set inlet settings
                if(self.valve.mode=='set' or self.valve.mode=='set_scripted'):
                    self.valve.inlet = get_valid_input_int('starting_inlet: specify the starting inlet : ', list(range(1, len(self.valve.inlet_concs)+1)))
                    self.valve.input_conc = self.valve.inlet_concs[self.valve.inlet-1]
                # pwm settings
                elif(self.valve.mode=='pwm' or self.valve.mode=='pwm_scripted'):
                    self.valve.pwm_period = get_valid_input_float('pwm_period: the PWM period (seconds) : ')
                    self.valve.input_conc = get_valid_input_float('starting_conc: the starting conc. : ')
                    self.valve.pwm_update_controls()    # update the valve controls for the selected input conc

            # set the inlet back to the starting one (NOTE: both if setting chosen manually and if loaded)
            valve_error_msg = MUX_DRI_Set_Valve(self.valve.instridval,  # valve ID value
                                                c_int32(self.valve.inlet),  # valve inlet
                                                0  # valve rotation direction (zero for shortest)
                                                )
            if (valve_error_msg != 0):
                print('Valve error: %d' % valve_error_msg)
                exit(1)

            # load the script if using one
            if(self.valve.mode == 'set_scripted' or self.valve.mode == 'pwm_scripted'):
                self.valve.load_script()

        else:
            print('(Valve not in use)')

        print('\nSET UP THE RECIRCULATION VALVE') # ----------------------------------------------------------------------------------
        if(self.recirc.in_use):
            # load the recirculator
            self.recirc.instrid = c_int32()
            print('Adding the RECIRCULATOR...')
            recirc_error_msg = MUX_DRI_Initialization(RECIRC_PORT.encode('ascii'),
                                                     byref(self.recirc.instrid))
            if (recirc_error_msg != 0):
                print('Recirculator addition error: %d' % recirc_error_msg)
                exit(1)
            # get the recirculator ID value
            self.recirc.instridval = self.recirc.instrid.value
            # if EMULATING, overried with the ID 2 for the Python dummy script to work
            if (EMULATING):
                self.recirc.instridval = 2
            # home the recirculator (necessary step for our MUX Recirculation valve)
            answer=(c_char * 10)()
            recirc_error_msg = MUX_DRI_Send_Command(self.recirc.instridval,  # recirc ID value
                                                   0, # recirc action: 0 for 'home the valve'
                                                   answer,  # char array for the answer - irrelevant here (needed to get a serial number)
                                                   0    # length of the answer array - irrelevant here (needed to get a serial number)
                                                   )
            if (recirc_error_msg != 0):
                print('Recirculator homing error: %d' % ob1_error_msg)
                exit(1)

            # set up recirculator preferences
            # RECIRCULATOR-COMPUTER INTERACTIONS
            if(self.recirc.still_todo['INTERACTIONS']):
                self.recirc.dt_check = get_valid_input_float('recirc_dt_check: how often you want the computer to check on the RECIRCULATOR (seconds) : ')
                self.recirc.dt_log = get_valid_input_float('recirc_dt_log: how often you want to log RECIRCULATOR data (seconds) : ')
                self.recirc.short_term_memo_dur = float(
                    input('recirc_short_term_memo_dur: how long you want to keep ALL most recent RECIRCULATOR data in memory (seconds) : '))
                # convert from logging and remembering times to number of data points
                self.recirc.log_every_points = int(self.recirc.dt_log / self.recirc.dt_check)

            # RECIRCULATOR OPERATIONS
            if(self.recirc.still_todo['OPERATIONS']):
                self.recirc.mode = input('Specify the RECIRCULATOR mode (manual, scripted) : ')
                # set inlet settings
                while(True):
                    state_A_or_B = input('starting_inlet: specify the starting state (A, B): ')
                    if(state_A_or_B == 'A'):
                        self.recirc.state = 1 # state A corresponds to the int 1
                        break
                    elif(state_A_or_B == 'B'):
                        self.recirc.state = 2 # state B corresponds to the int 2
                        break

            # set the inlet back to the starting one (NOTE: both if setting chosen manually and if loaded)
            recirc_error_msg = MUX_DRI_Set_Valve(self.recirc.instridval,  # valve ID value
                                                c_int32(self.recirc.state),  # valve inlet
                                                0  # valve rotation direction (zero for shortest)
                                                )
            if (recirc_error_msg != 0):
                print('Recirculator error: %d' % recirc_error_msg)
                exit(1)

            # load the script if using one
            if(self.recirc.mode == 'scripted'):
                self.recirc.load_script()

        else:
            print('(Recirculator not in use)')

        print('\nFILL THE TUBING') # -----------------------------------------------------------------------------------
        for ch in self.channels:
            if (ch.in_use):
                tubing_filled = input(
                    'Is your CHANNEL ' + str(ch.id) + ' tubing filled with liquid now? (yes, no) : ')
                if (tubing_filled == 'no'):
                    print('Tubing-filling walkthrough initiated')
                    self.fill_channel_tubing(ch)

        # SAVE THE STARTING SETTINGS -----------------------------------------------------------------------------------
        save_filename=self.save_settings()
        print('\nStarting settings saved in %s' % save_filename)

        # GET READY TO DO CRUISE CONTROL -------------------------------------------------------------------------------
        self.doing_cruise_control = False
        self.OB1_logfilepath = ''

        # create a queue of user commands for the OB-1 thread
        self.user_cmd_queue = queue.Queue()
        # create a queue of messages to be printed when prompted by the OB-1 handler
        self.print_queue = queue.Queue()
        # create a queue of user commands for the valve
        self.user_valve_cmd_queue = queue.Queue()
        # create a queue of user commands for the recirculator
        self.user_recirc_cmd_queue = queue.Queue()

        # create a short term memory locker for safe live plotting
        self.lock = threading.Lock()
        # create a variable stating a live plotter should be opened
        self.open_live_plot = False
        # create a variable stating if a live plotter is running
        self.live_plot_running = False
        # create a variable stating if the threads have just been started
        self.threads_just_started = True

        # create OB-1 interaction thread
        self.OB1_thread = threading.Thread(target=self.cruise_control_OB1, daemon=True)
        # create user input thread
        self.user_thread = threading.Thread(target=self.cruise_control_user, daemon=True)
        # create valve cruise control thread if it is in use
        if(self.valve.in_use):
            self.valve_thread = threading.Thread(target=self.cruise_control_valve, daemon=True)
        # create recirculator cruise control thread if it is in use
        if (self.recirc.in_use):
            self.recirc_thread = threading.Thread(target=self.cruise_control_recirc, daemon=True)

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
        # at the start, we are yet to specify OB-1 computer interactions and the valve
        interactions_still_todo = True
        valve_still_todo = True

        # open the file
        with open(filename, 'r') as file:
            # get the lines from the file
            lines = file.readlines()
            lines_total = len(lines)

            # initialise
            curr_line = 0

            # go through the lines
            while(curr_line<lines_total):
                # handle channels
                if(lines[curr_line]=='CHANNEL 1\n'):
                    curr_line = next_meaningful_line(curr_line)
                    # check if the channel is in use
                    if(lines[curr_line]=='NOT IN USE\n'):
                        # if not in use, skip the 'END CHANNEL 1' line and proceed
                        curr_line = next_meaningful_line(curr_line)
                    else:
                        # if in use, set the channel under consideration to be channel 1
                        ch=self.channels[0]
                        ch.in_use=True
                        ch.still_todo = {'FLOW CONTROLLER': True,
                                      'OB1-COMPUTER INTERACTIONS': True,
                                      'SAFEGUARDS': True}
                        continue
                elif(lines[curr_line] == 'CHANNEL 2\n'):
                    curr_line = next_meaningful_line(curr_line)
                    # check if the channel is in use
                    if (lines[curr_line] == 'NOT IN USE\n'):
                        # if not in use, skip the 'END CHANNEL 1' line and proceed
                        curr_line = next_meaningful_line(curr_line)
                    else:
                        # if in use, set the channel under consideration to be channel 1
                        ch = self.channels[1]
                        ch.in_use = True
                        ch.still_todo = {'FLOW CONTROLLER': True,
                                         'OB1-COMPUTER INTERACTIONS': True,
                                         'SAFEGUARDS': True}
                        continue

                # read the reference and PI(D?) gains
                elif(lines[curr_line]=='FLOW CONTROLLER\n'):
                    ch.still_todo['FLOW CONTROLLER'] = False
                    curr_line = next_meaningful_line(curr_line)

                    # get the reference flow
                    ch.ref_flow = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # get the P gain
                    ch.p_gain = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # get the I gain
                    ch.i_gain = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # get the D gain
                    ch.d_gain = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)

                    # PARAMETERS FOR CONTROL
                    # get the anti-windup bounds for error integral, if any specified
                    if(lines[curr_line].split()[0]=='min_flerrint'):
                        ch.min_flerrint = float(lines[curr_line].split()[2])
                        curr_line = next_meaningful_line(curr_line)
                        ch.max_flerrint = float(lines[curr_line].split()[2])
                        curr_line = next_meaningful_line(curr_line)
                    # get the user-defined pressure control bounds, if any specified
                    if(lines[curr_line].split()[0]=='min_press_ctrl'):
                        ch.min_press_ctrl = float(lines[curr_line].split()[2])
                        curr_line = next_meaningful_line(curr_line)
                        ch.max_p_ctrl = float(lines[curr_line].split()[2])
                        curr_line = next_meaningful_line(curr_line)
                    else:
                        # if bounds are not specified, set them to default
                        ch.min_press_ctrl = 0.0
                        ch.max_p_ctrl = 2000.0

                    # skip the 'END FLOW CONTROLLER' marker line
                    curr_line = next_meaningful_line(curr_line)
                    continue

                # read OB1-computer interaction settings
                elif(lines[curr_line]=='OB1-COMPUTER INTERACTIONS\n'):
                    interactions_still_todo = False
                    curr_line = next_meaningful_line(curr_line)
                    # get the check time
                    self.dt_check = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # get the log time
                    self.dt_log = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # get the short-term memory time
                    short_term_memo_dur = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # convert from logging and remembering times to number of data points
                    self.log_every_points = int(self.dt_log / self.dt_check)
                    self.short_term_memo_size = int(short_term_memo_dur / self.dt_check)+1

                    # skip the 'END OB1-COMPUTER INTERACTIONS' marker line
                    curr_line = next_meaningful_line(curr_line)
                    continue

                # read safeguards
                elif(lines[curr_line]=='SAFEGUARDS\n'):
                    if(interactions_still_todo):
                        print('Error: safeguards cannot be defined before OB1-computer interactions are specified!')
                        exit(1)
                    ch.still_todo['SAFEGUARDS'] = False

                    # initialise the set of safeguards
                    curr_line = next_meaningful_line(curr_line)
                    p_bounds = []
                    p_lnub = []
                    flow_bounds = []
                    flow_lnub = []
                    safeguard_check_steps = []
                    ch.safeguard_conds = []
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
                        ch.safeguard_conds.append(lines[curr_line][:-1])

                        # move to the next line
                        curr_line = next_meaningful_line(curr_line)
                        
                        if(curr_line>=lines_total):
                            break

                    # record the safeguard specs as numpy arrays
                    # record the safeguard specs as numpy arrays
                    ch.p_bounds = np.array(p_bounds)
                    ch.p_lnub = np.array(p_lnub)
                    ch.flow_bounds = np.array(flow_bounds)
                    ch.flow_lnub = np.array(flow_lnub)
                    ch.safeguard_check_steps = np.array(safeguard_check_steps)
                    ch.num_safeguards = len(ch.p_bounds)

                    # skip the 'END SAFEGUARDS' marker line
                    curr_line = next_meaningful_line(curr_line)
                    continue
                elif(lines[curr_line]=='VALVE\n'):
                    curr_line = next_meaningful_line(curr_line)
                    # check if the channel is in use
                    if (lines[curr_line] == 'NOT IN USE\n'):
                        # if not in use, skip the 'END VALVE' line and proceed
                        curr_line = next_meaningful_line(curr_line)
                    else:
                        # if in use, start setting the valve up
                        self.valve.in_use = True
                        self.valve.still_todo = {'INTERACTIONS': True,
                                         'OPERATIONS': True}
                        continue

                elif(lines[curr_line]=='VALVE-COMPUTER INTERACTIONS\n'):
                    self.valve.still_todo['INTERACTIONS'] = False
                    curr_line = next_meaningful_line(curr_line)
                    # get the check time
                    self.valve.dt_check = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # get the log time
                    self.valve.dt_log = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # get the short-term memory time
                    self.valve.short_term_memo_dur = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # convert from logging and remembering times to number of data points
                    self.valve.log_every_points = int(self.valve.dt_log / self.valve.dt_check)

                    # skip the 'END VALVE-COMPUTER INTERACTIONS' marker line
                    curr_line = next_meaningful_line(curr_line)

                elif (lines[curr_line] == 'VALVE OPERATIONS\n'):
                    self.valve.still_todo['OPERATIONS'] = False
                    curr_line = next_meaningful_line(curr_line)
                    # get the valve mode
                    self.valve.mode = lines[curr_line].split()[2]
                    curr_line = next_meaningful_line(curr_line)
                    # get the compound of interest concentrations in the valve
                    inlet_conc_strings = lines[curr_line].split()[2:]
                    inlet_concs = []
                    for inlet_cntr in range(0, len(inlet_conc_strings)):
                        inlet_concs.append(float(inlet_conc_strings[inlet_cntr]))
                    self.valve.inlet_concs = np.array(inlet_concs)
                    curr_line = next_meaningful_line(curr_line)
                    # get other valve specs depending on the mode
                    if(self.valve.mode=='set' or self.valve.mode=='set_scripted'):
                        # get the starting inlet
                        self.valve.inlet = int(lines[curr_line].split()[2])
                        self.valve.input_conc = self.valve.inlet_concs[self.valve.inlet-1]# also get the corresponding starting input concentration
                        curr_line = next_meaningful_line(curr_line)
                    elif(self.valve.mode=='pwm' or self.valve.mode=='pwm_scripted'):
                        # get the PWM period
                        self.valve.pwm_period = float(lines[curr_line].split()[2])
                        curr_line = next_meaningful_line(curr_line)
                        # get the desired input concentration of the compound of interest
                        self.valve.input_conc = float(lines[curr_line].split()[2])
                        self.valve.pwm_update_controls()  # update the valve controls for the selected input conc
                        curr_line = next_meaningful_line(curr_line)

                    # skip the 'END VALVE OPERATIONS' marker line
                    curr_line = next_meaningful_line(curr_line)

                elif (lines[curr_line] == 'RECIRCULATOR\n'):
                    curr_line = next_meaningful_line(curr_line)
                    # check if the channel is in use
                    if (lines[curr_line] == 'NOT IN USE\n'):
                        # if not in use, skip the 'END RECIRCULATOR' line and proceed
                        curr_line = next_meaningful_line(curr_line)
                    else:
                        # if in use, start setting the RECIRCULATOR up
                        self.recirc.in_use = True
                        self.recirc.still_todo = {'INTERACTIONS': True,
                                                 'OPERATIONS': True}
                        continue

                elif (lines[curr_line] == 'RECIRCULATOR-COMPUTER INTERACTIONS\n'):
                    self.recirc.still_todo['INTERACTIONS'] = False
                    curr_line = next_meaningful_line(curr_line)
                    # get the check time
                    self.recirc.dt_check = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # get the log time
                    self.recirc.dt_log = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # get the short-term memory time
                    self.recirc.short_term_memo_dur = float(lines[curr_line].split()[2])
                    curr_line = next_meaningful_line(curr_line)
                    # convert from logging and remembering times to number of data points
                    self.recirc.log_every_points = int(self.recirc.dt_log / self.recirc.dt_check)

                    # skip the 'END RECIRCULATOR-COMPUTER INTERACTIONS' marker line
                    curr_line = next_meaningful_line(curr_line)

                elif (lines[curr_line] == 'RECIRCULATOR OPERATIONS\n'):
                    self.recirc.still_todo['OPERATIONS'] = False
                    curr_line = next_meaningful_line(curr_line)
                    # get the recirculator mode
                    self.recirc.mode = lines[curr_line].split()[2]
                    curr_line = next_meaningful_line(curr_line)
                    # get the starting inlet
                    recirc_state_A_or_B  = lines[curr_line].split()[2]
                    if (recirc_state_A_or_B  == 'A'):
                        self.recirc.state = 1
                    elif (recirc_state_A_or_B == 'B'):
                        self.recirc.state = 2
                    else:
                        print('Error! Invalid recirculator state')
                    curr_line = next_meaningful_line(curr_line)

                    # skip the 'END RECIRCULATOR OPERATIONS' marker line
                    curr_line = next_meaningful_line(curr_line)

                else:
                    # if the line is not recognised, move to the next one
                    curr_line = next_meaningful_line(curr_line)
                    continue

        # return the list of settings that still need to be entered manually
        return interactions_still_todo

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

    # fill the tubing for a given channel with liquid
    def fill_channel_tubing(self, ch):
        # ASK IF THIS IS THE CHANNEL WITH THE VALVE - IF IT IS IN USE
        if (not self.valve.in_use):
            fill_all_valve_inlets = False
        else:
            ch_with_valve = input('Is this the channel with the VALVE? (yes, no) : ')
            if(ch_with_valve == 'yes'):
                fill_all_valve_inlets = True
            else:
                fill_all_valve_inlets = False

        # TUBING UP TO THE RESISTANCE - IF NOT FILLING THE VALVE INLETS
        if(not fill_all_valve_inlets):
            ready_for_filling = 'no'
            while (ready_for_filling != 'yes'):
                print('Connect all system components, excluding the resistance.' +
                      '\nPut the outlet into the purge tube.' +
                      '\nThe OB-1 will apply a constant pressure to fill the tubing with liquid.' +
                      '\nOnce the tubing is filled with liquid, press any key.')
                ready_for_filling = input('Are you ready? (yes, no) : ')
            ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                  ch.id,  # which channel is being controlled
                                  1000,  # which pressure is being set
                                  byref(self.Calib), 1000)
            if (ob1_error_msg != 0):
                print('Pressure setting error: %d' % ob1_error_msg)
                exit(1)
            input('Press any key when done : ')
            ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                          ch.id,  # which channel is being controlled
                                          0,  # which pressure is being set - zero when done
                                          byref(self.Calib), 1000)
            if (ob1_error_msg != 0):
                print('Pressure setting error: %d' % ob1_error_msg)
                exit(1)
        # TUBING UP TO THE RESISTANCE - IF FILLING THE VALVE INLETS
        else:
            print('Connect all system components, excluding the resistance.' +
                  '\nPut the outlet into the purge tube.' +
                  '\nThe OB-1 will apply a constant pressure to fill the tubing with liquid.' +
                  '\nThe OB-1 will do this for valve inlet 1, then repeat for all valve inlets' +
                  '\nOnce the tubing is filled with liquid, press any key.')
            for inlet_cntr in range(1,len(self.valve.inlet_concs)+1):
                ready_for_filling = 'no'
                while (ready_for_filling != 'yes'):
                    ready_for_filling = input('Inlet '+str(inlet_cntr)+'. Are you ready? (yes, no) : ')
                # set the valve inlet to be filled
                valve_error_msg = MUX_DRI_Set_Valve(self.valve.instridval,  # valve ID value
                                                    c_int32(int(inlet_cntr)),  # valve inlet
                                                    0  # valve rotation direction (zero for shortest)
                                                    )
                if (valve_error_msg != 0):
                    print('Valve error: %d' % valve_error_msg)
                    exit(1)
                # fill the tubing by applying a constant pressure
                ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                              ch.id,  # which channel is being controlled
                                              1000,  # which pressure is being set
                                              byref(self.Calib), 1000)
                if (ob1_error_msg != 0):
                    print('Pressure setting error: %d' % ob1_error_msg)
                    exit(1)
                input('Press any key when done : ')
                ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                              ch.id,  # which channel is being controlled
                                              0,  # which pressure is being set - zero when done
                                              byref(self.Calib), 1000)
                if (ob1_error_msg != 0):
                    print('Pressure setting error: %d' % ob1_error_msg)
                    exit(1)
            # set the inlet back to the starting one
            valve_error_msg = MUX_DRI_Set_Valve(self.valve.instridval,  # valve ID value
                                                c_int32(self.valve.inlet),  # valve inlet
                                                0  # valve rotation direction (zero for shortest)
                                                )
            if (valve_error_msg != 0):
                print('Valve error: %d' % valve_error_msg)
                exit(1)

        # RESISTANCE
        ready_for_filling = 'no'
        while (ready_for_filling != 'yes'):
            print('\nConnect the resistor, the outlet end facing the purge tube.' +
                  '\nThe OB-1 will apply a constant pressure to fill the resistor with liquid.' +
                  '\nOnce the liduid starts coming out, press any key.')
            ready_for_filling = input('Are you ready? (yes, no) : ')
        ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                      ch.id,  # which channel is being controlled
                                      1000,  # which pressure is being set
                                      byref(self.Calib), 1000)
        if (ob1_error_msg != 0):
            print('Pressure setting error: %d' % ob1_error_msg)
            exit(1)
        input('Press any key when done : ')
        ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                      ch.id,  # which channel is being controlled
                                      0,  # which pressure is being set - zero when done
                                      byref(self.Calib), 1000)
        if (ob1_error_msg != 0):
            print('Pressure setting error: %d' % ob1_error_msg)
            exit(1)

        # RECIRCULATOR
        if(self.recirc.in_use):
            print('Not sure what you\'re doing with your recirculator, but fill the tubing in the next, customary step if needed.\n')

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
                                          ch.id,  # which channel is being controlled
                                          1000,  # which pressure is being set
                                          byref(self.Calib), 1000)
            if (ob1_error_msg != 0):
                print('Pressure setting error: %d' % ob1_error_msg)
                exit(1)
            input('Press any key when done : ')
            ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                          ch.id,  # which channel is being controlled
                                          0,  # which pressure is being set - zero when done
                                          byref(self.Calib), 1000)
            if (ob1_error_msg != 0):
                print('Pressure setting error: %d' % ob1_error_msg)
                exit(1)
            fill_more = input('Do you need to fill more tubing? (yes, no) : ')

        return
    
    # set up the safeguards for a given channel
    def make_channel_safeguards(self, ch):
        add_safeguard = input('Do you want to add a condition for cutting off pressure? (yes, no) : ')
        p_bounds = []
        p_lnub = []
        flow_bounds = []
        flow_lnub = []
        safeguard_check_steps = []
        ch.safeguard_conds = []
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

            safeguard_time = get_valid_input_float('For how long must the condition be true to trigger the cutoff (seconds) : ')
            safeguard_check_steps.append(
                int(safeguard_time / self.dt_check)+1)  # convert to number of data points in short-term memory
            if (safeguard_check_steps[-1] > self.short_term_memo_size):
                print('Error: the specified time exceeds short-term memory')
                continue
            elif (safeguard_check_steps[-1] <= 0):
                print('Error: the specified must be positive')
                continue

            # make an interperatable condition string
            ch.safeguard_conds.append('')
            if (p_cond == 'yes'):
                ch.safeguard_conds[-1] = ch.safeguard_conds[-1] + safeguard_p_str + ' mbar'
            if (flow_cond == 'yes'):
                if(p_cond == 'yes'):
                    ch.safeguard_conds[-1] += ' AND '
                ch.safeguard_conds[-1] = ch.safeguard_conds[-1] + safeguard_flow_str + ' uL/min'
            ch.safeguard_conds[-1] += ' FOR ' + str(safeguard_time) + ' s'

            # ask if another safeguard is to be added
            add_safeguard = input('\nDo you want to add another pressure cutoff condition? (yes, no) : ')

        # record the safeguard specs as numpy arrays
        ch.p_bounds = np.array(p_bounds)
        ch.p_lnub = np.array(p_lnub)
        ch.flow_bounds = np.array(flow_bounds)
        ch.flow_lnub = np.array(flow_lnub)
        ch.safeguard_check_steps = np.array(safeguard_check_steps)
        ch.num_safeguards = len(ch.p_bounds)

        print('\nPressure cutoff conditions summary: ')
        for i in range(ch.num_safeguards):
            print('\tCondition %d: %s' % (i, ch.safeguard_conds[i]))
        return 

    # CRUISE CONTROL --------------------------------------------------------------------------------------------------

    # save the starting settings
    def save_settings(self):
        date_time_string = (datetime.datetime.now()).strftime("_%d%m_%H%M")
        filename = 'logs/start_settings'+date_time_string+'.txt'
        with open(filename, 'w') as file:
            # record the OB1-computer interaction settings
            file.write('OB1-COMPUTER INTERACTIONS\n')
            file.write('dt_check = ' + str(self.dt_check) + ' s\n')
            file.write('dt_log = ' + str(self.dt_log) + ' s\n')
            file.write('short_term_memo_dur = ' + str((self.short_term_memo_size - 1) * self.dt_check) + ' s\n')
            file.write('END OB1-COMPUTER INTERACTIONS\n')
            file.write('\n')

            # record channel settings
            for ch in self.channels:
                file.write('CHANNEL '+str(ch.id)+'\n')
                if(not ch.in_use):
                    file.write('NOT IN USE\n')
                    file.write('END CHANNEL'+str(ch.id)+'\n')
                    file.write('\n')
                    continue

                file.write('FLOW CONTROLLER\n')
                # initial reference setpoint
                file.write('ref_flow = ' + str(float(ch.ref_flow)) + ' ul/min\n')
                # controller gain
                file.write('p_gain = ' + str(ch.p_gain) + '\n')
                file.write('i_gain = ' + str(ch.i_gain) + '\n')
                file.write('d_gain = ' + str(ch.d_gain) + '\n')
                # auxiliary controller parameters
                file.write('min_flerrint = ' + str(ch.min_flerrint) + '\n')
                file.write('max_flerrint = ' + str(ch.max_flerrint) + '\n')
                file.write('min_press_ctrl = ' + str(ch.min_press_ctrl) + ' mbar\n')
                file.write('max_p_ctrl = ' + str(ch.max_p_ctrl) + ' mbar\n')
                file.write('END FLOW CONTROLLER\n')
                file.write('\n')

                file.write('SAFEGUARDS\n')
                for i in range(ch.num_safeguards):
                    file.write(ch.safeguard_conds[i] + '\n')
                file.write('END SAFEGUARDS\n')
                file.write('END CHANNEL '+str(ch.id)+'\n')
                file.write('\n')

            # record valve settings
            file.write('VALVE\n')
            if (not self.valve.in_use):
                file.write('NOT IN USE\n')
            else:
                file.write('VALVE-COMPUTER INTERACTIONS\n')
                # save the time between computer checks on the valve
                file.write('valve_dt_check = ' + str(self.valve.dt_check) + ' s\n')
                # save the logging time for the valve
                file.write('valve_dt_log = ' + str(self.valve.dt_log) + ' s\n')
                # save the short-term memory duration in seconds
                file.write('valve_stmemo_dur = ' + str(self.valve.short_term_memo_dur) + ' s\n')
                # finish the computer interactions block
                file.write('END VALVE-COMPUTER INTERACTIONS\n\n')

                file.write('VALVE OPERATIONS\n')
                # save the valve mode
                file.write('mode = ' + str(self.valve.mode) + '\n')
                # save the compound of interest concentrations in the valve inlets
                inlet_concs_str = ''
                for inlet_cntr in range(0, len(self.valve.inlet_concs)):
                    if (inlet_cntr != 0):
                        inlet_concs_str += ' '
                    inlet_concs_str += str(self.valve.inlet_concs[inlet_cntr])
                file.write('inlet_concs = ' + inlet_concs_str + '\n')
                # save other valve specs depending on the mode
                if (self.valve.mode == 'set' or self.valve.mode == 'set_scripted'):
                    # get the starting inlet
                    file.write('starting_inlet = ' + str(self.valve.inlet) + '\n')
                elif (self.valve.mode == 'pwm' or self.valve.mode == 'pwm_scripted'):
                    # save the PWM period
                    file.write('pwm_period = ' + str(self.valve.pwm_period) + ' s\n')
                    # save the starting desired input concentration of the compound of interest
                    file.write('starting_conc = ' + str(self.valve.input_conc) + '\n')
                # finish the operations block
                file.write('END VALVE OPERATIONS\n')
                # finish the valve block
                file.write('END VALVE\n')

            # record recirculator settings
            file.write('RECIRCULATOR\n')
            if (not self.recirc.in_use):
                file.write('NOT IN USE\n')
            else:
                file.write('RECIRCULATOR-COMPUTER INTERACTIONS\n')
                # save the time between computer checks on the recirculator
                file.write('recirc_dt_check = ' + str(self.recirc.dt_check) + ' s\n')
                # save the logging time for the recirculator
                file.write('recirc_dt_log = ' + str(self.recirc.dt_log) + ' s\n')
                # save the short-term memory duration in seconds
                file.write('recirc_stmemo_dur = ' + str(self.recirc.short_term_memo_dur) + ' s\n')
                # finish the computer interactions block
                file.write('END RECIRCULATOR-COMPUTER INTERACTIONS\n\n')

                file.write('RECIRCULATOR OPERATIONS\n')
                # save the recirculator mode
                file.write('mode = ' + str(self.recirc.mode) + '\n')
                # save the starting state
                file.write('starting_state = ' + 'AB'[self.recirc.state-1] + '\n')
                # finish the operations block
                file.write('END RECIRCULATOR OPERATIONS\n')
                # finish the recirculator block
                file.write('END RECIRCULATOR\n')

        return os.path.abspath(filename)

    # CRUISE CONTROL FUNCTIONS -----------------------------------------------------------------------------------------
    # main thread for cruise control of the microfluidic flow
    def cruise_control(self,
                       OB1_log_filename=r'logs/OB1_PID_log.csv',
                       valve_log_filename=r'logs/valve_log.csv',
                       recirc_log_filename=r'logs/recirc_log.csv',):
        # indicate that cruise control is being done
        self.doing_cruise_control = True
        self.open_live_plot = True  # open a live plot at first

        # get log file paths (including for valve states IF VALVE IN USE)
        self.OB1_logfilepath = os.path.abspath(OB1_log_filename)
        if(self.valve.in_use):
            self.valve.logfilepath = os.path.abspath(valve_log_filename)
            self.valve.error_logfilepath = os.path.abspath(valve_log_filename[:-4]+'_errors.txt')
        if(self.recirc.in_use):
            self.recirc.logfilepath = os.path.abspath(recirc_log_filename)
            self.recirc.error_logfilepath = os.path.abspath(recirc_log_filename[:-4]+'_errors.txt')

        # ask how much medium there is in the source - IF VALVE NOT IN USE
        if(not self.valve.in_use):
            for ch in self.channels:
                if(ch.in_use):
                    ch.medstart = get_valid_input_float('How much medium is there in the CHANNEL '+str(ch.id)+' source (ml)? : ')
        else:
            for ch in self.channels:
                ch.medstart = 0.0
            
        # start in reference flow tracking mode
        for ch in self.channels:
            if(ch.in_use):
                ch.mode = 0

        # start writing the log files (including for valve states IF VALVE IN USE)
        with(open(self.OB1_logfilepath, 'w', newline='')) as logfile:
            logwriter = csv.writer(logfile)
            row = ['Time (s)']
            row_entries_for_each_channel = ['Pressure (mbar)', 'Flow (ul/min)',
                                            'Medium left (ml)',
                                            'Mode',
                                            'Reference flow (ul/min)', 'Constant pressure (mbar)',
                                            'P gain', 'I gain', 'D gain']
            for ch in self.channels:
                for row_entry in row_entries_for_each_channel:
                    row.append('CH '+str(ch.id)+' '+row_entry)
            logwriter.writerow(row)
        if(self.valve.in_use):
            with(open(self.valve.logfilepath, 'w', newline='')) as logfile:
                logwriter = csv.writer(logfile)
                row = ['Time (s)']
                valve_entries = ['Valve inlet', 'Valve input conc.']
                if (self.valve.mode == 'pwm' or self.valve.mode == 'pwm_scripted'):
                    valve_entries.append('Valve duty cycle')
                    valve_entries.append('PWM low inlet')
                    valve_entries.append('PWM high inlet')
                if(self.valve.mode=='set_scripted' or self.valve.mode=='pwm_scripted'):
                    valve_entries.append('Time since script launch (s)')
                for row_entry in valve_entries:
                    row.append(row_entry)
                logwriter.writerow(row)
            with(open(self.valve.error_logfilepath, 'w', newline='')) as logfile:
                logfile.write('VALVE ERROR LOG:\n')
        if (self.recirc.in_use):
            with(open(self.recirc.logfilepath, 'w', newline='')) as logfile:
                logwriter = csv.writer(logfile)
                row = ['Time (s)']
                recirc_entries = ['Recirc. state']
                if (self.recirc.mode == 'scripted'):
                    recirc_entries.append('Time since script launch (s)')
                for row_entry in recirc_entries:
                    row.append(row_entry)
                logwriter.writerow(row)
            with(open(self.valve.error_logfilepath, 'w', newline='')) as logfile:
                logfile.write('RECIRCULATOR ERROR LOG:\n')

        # start the threads
        self.threads_just_started = True
        self.cc_start_time = time.time()  # start time of cruise control
        self.OB1_thread.start()
        self.user_thread.start()
        if(self.valve.in_use):
            self.valve_thread.start()
        if(self.recirc.in_use):
            self.recirc_thread.start()
        self.threads_just_started = False

        # keep the main thread alive
        try:
            while self.doing_cruise_control:
                # open a live plot in the main thread if prompted
                if(self.open_live_plot):
                    self.open_live_plot = False
                    self.live_plot_running = True
                    self.live_stmemo_plot()
                    self.live_plot_running = False
                time.sleep(self.dt_check)  # sleep for the check time if not kept alive by a live plot
        except KeyboardInterrupt:
            self.stop_cruise_control()
            print('Keyboard-interrupted')

        return

    # handle interactions and records with the OB-1 during cruise control
    def cruise_control_OB1(self):
        cc_check_cntr = 0 # counter for how many times the computer has checked on the OB-1

        while self.doing_cruise_control:
            # NO MEDIA CHANGES BY DEFAULT
            for ch in self.channels:
                if (ch.in_use):
                    ch.medleft_new = -1

            # HANDLE THE USER INPUT, IF ANY
            try:
                # get the user command and the argument
                user_cmd, user_ch, user_cmd_arg0, user_cmd_arg1, user_cmd_arg2 = self.user_cmd_queue.get_nowait()

                # get the channel selected - mind the shift as channels are labelled as 1 and 2 but Pyhton indices start at 0
                ch=self.channels[int(user_ch)-1]

                # get the command type
                if (user_cmd == 0):  # 0 for stopping the cruise control
                    self.stop_cruise_control()
                    break

                elif (user_cmd == 1):  # 1 for setting a new reference flow
                    if(not ch.in_use):
                        self.print_queue.put('CHANNEL '+str(ch.id)+' not in use!')
                    else:
                        if(ch.mode==1): # if we have been in the constant pressure mode, indicate the mode's changed now
                            ch.mode = 0
                            self.print_queue.put('Mode changed to flow reference tracking')
                        ch.ref_flow = user_cmd_arg0

                elif (user_cmd == 2):  # 2 for changing the controller mode
                    if (not ch.in_use):
                        self.print_queue.put('CHANNEL ' + str(ch.id) + ' not in use!')
                    else:
                        if(ch.mode==0): # if we have been in the flow reference tracking mode, indicate the mode's changed now
                            ch.mode = 1
                            self.print_queue.put('Mode changed to constant pressure')
                        ch.const_press = user_cmd_arg0

                elif (user_cmd == 3):  # 3 for changing the PI(D?) gains
                    if (not ch.in_use):
                        self.print_queue.put('CHANNEL ' + str(ch.id) + ' not in use!')
                    else:
                        # get the gains
                        ch.p_gain = user_cmd_arg0
                        ch.i_gain = user_cmd_arg1
                        ch.d_gain = user_cmd_arg2

                elif (user_cmd == 4):   # 4 for opening a live plot
                    if (self.threads_just_started or self.live_plot_running):  # only open a new live plot if one isn't already running
                        self.print_queue.put('Live plot already running!')
                    else:
                        self.open_live_plot = True

                elif (user_cmd == 5):  # 5 for changing the medium amount in the source - not supported if a valve is active
                    if (not ch.in_use):
                        self.print_queue.put('CHANNEL ' + str(ch.id) + ' not in use!')
                    elif (self.valve.in_use):
                        self.print_queue.put('Unsupported when VALVE is in use!')
                    else:
                        ch.medleft_new = user_cmd_arg0

                elif (user_cmd == 6): # 6 for purging the integral controller's memory
                    if (not ch.in_use):
                        self.print_queue.put('CHANNEL ' + str(ch.id) + ' not in use!')
                    else:
                        ch.flerrint = 0.0
                        self.print_queue.put('Integral controller memory set to zero')
            except:
                pass

            # GET READINGS FROM THE OB-1
            # get the time of measurement
            t_check_absolute = time.time()  # get the time of the check - NOT from the start of cruise control
            t_check_relative = t_check_absolute - self.cc_start_time  # convert ti time from the start of cruise control
            # handling each channel in turn
            for ch in self.channels:
                # read the pressure and flow...
                p_read_c_double = c_double()  # initialise pressure reading
                flow_read_c_double = c_double()  # initialise flow reading
                # pressure
                ob1_error_msg = OB1_Get_Press(self.OB1.value,  # which OB-1 is being used
                                      ch.id,              # which channel pressure is being read
                                      1,                    # 1 means all pressure and analog sensor readings actually measured, not taken for memory. Irrelevant for digital sensors
                                      byref(self.Calib),    # calibration (do not touch)
                                      byref(p_read_c_double),        # where to write the data
                                      1000                  # calibration (do not touch)
                                      )
                if(ob1_error_msg != 0):
                    print('Pressure measurement error: %d' % ob1_error_msg)
                    exit(1)
                ch.p_read = p_read_c_double.value   # record the read pressure for the channel
                # flow
                ob1_error_msg = OB1_Get_Sens_Data(self.OB1.value,  # which OB-1 is being used
                                  ch.id,  # which sensor is being read
                                  1,    # 1 means all pressure and analog sensor readings actually measured, not taken for memory. Irrelevant for digital sensors
                                  byref(flow_read_c_double)  # where to write the data
                                  )  # Acquire_data=1 -> read all the analog values
                if (ob1_error_msg != 0):
                    print('Flow measurement error: %d' % ob1_error_msg)
                    exit(1)
                ch.flow_read = flow_read_c_double.value

            # CHECK THE SAFEGUARDS, CUT OFF THE PRESSURE IF NEEDED
            for ch in self.channels:
                if(ch.in_use):
                    cutoff_condition_true, which_cutoff_condition = self.check_channel_safeguards(ch)
                    if (cutoff_condition_true):
                        self.stop_cruise_control()
                        print('Cruise control cut off by safeguard condition %d : ' % which_cutoff_condition)
                        print('\n\t' + ch.safeguard_conds[which_cutoff_condition])
                        break

            # DO PID CONTROL
            for ch in self.channels:
                if(ch.in_use):
                    # calculate pressure to supply to the channel
                    if(ch.mode==0):   # flow reference tracking
                        p = self.channel_PID_controller(ch, ch.flow_read, t_check_relative)
                    elif(ch.mode==1): # constant pressure
                        p = ch.const_press
                    p_c_double = c_double(p)
                    # set the calculated pressure on the OB-1
                    ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                                  ch.id,  # which channel is being controlled
                                                  p_c_double,  # which pressure is being set
                                                  byref(self.Calib), 1000  # calibration (do not touch)
                                                  )
                    if(ob1_error_msg != 0):
                        print('Pressure setting error: %d' % ob1_error_msg)
                        exit(1)

            # RECORD THE CHANNEL DATA IN SHORT-TERM MEMORY
            with self.lock:
                for ch in self.channels:
                    if (ch.in_use):
                        ch.stmemo_time.append(t_check_relative) # time SINCE THE START OF CRUISE CONTROL
                        ch.stmemo_p.append(ch.p_read)
                        ch.stmemo_flow.append(ch.flow_read)

                        # record the controller mode and parameters depending on the mode
                        ch.stmemo_mode.append(ch.mode)
                        if(ch.mode==0):   # flow reference tracking
                            # flow controller data
                            ch.stmemo_ref_flow.append(ch.ref_flow)
                            # NaNs for the constant pressure setpoint
                            ch.stmemo_const_press.append(np.nan)
                        elif(ch.mode==1): # constant pressure
                            # constant pressure controller data
                            ch.stmemo_const_press.append(ch.const_press)
                            # NaNs for the reference flow
                            ch.stmemo_ref_flow.append(np.nan)
                        # controller gains
                        ch.stmemo_p_gain.append(ch.p_gain)
                        ch.stmemo_i_gain.append(ch.i_gain)
                        ch.stmemo_d_gain.append(ch.d_gain)

                        # for estimated medium left in the source, calculate the estimate first
                        if(self.valve.in_use): # incompatible with the valve => just plug in zero
                            ch.medleft=0.0
                        else:
                            if(len(ch.stmemo_medleft)==0):
                                ch.medleft = ch.medstart  # at the beginning, the starting volume
                            elif(ch.medleft_new>=0):   # if medium source has been changed, recorsd this value
                                ch.medleft = ch.medleft_new
                            else:
                                # estimate using the trapezium rule
                                ch.medleft = ch.stmemo_medleft[-1] - (0.5 * (ch.flow_read + ch.stmemo_flow[-1]) * self.dt_check / 60000)  # note the conversion factor from ul/min to ml/s
                        ch.stmemo_medleft.append(ch.medleft)

                        # pop the oldest readings if short-term memory is full
                        if(len(ch.stmemo_p)>self.short_term_memo_size):
                            ch.stmemo_p.pop(0)
                            ch.stmemo_flow.pop(0)
                            ch.stmemo_time.pop(0)
                            ch.stmemo_ref_flow.pop(0)
                            ch.stmemo_const_press.pop(0)
                            ch.stmemo_p_gain.pop(0)
                            ch.stmemo_i_gain.pop(0)
                            ch.stmemo_d_gain.pop(0)
                            ch.stmemo_medleft.pop(0)

            # LOG THE DATA IF IT'S TIME TO DO SO
            if(cc_check_cntr % self.log_every_points == 0):
                with open(self.OB1_logfilepath, 'a', newline='') as logfile:
                    logwriter = csv.writer(logfile)
                    with self.lock:
                        row = [t_check_relative]    # time of the readings - common for both channels
                        for ch in self.channels:
                            if (ch.in_use):
                                row = row + [
                                    #  pressure, flow
                                    ch.stmemo_p[-1], ch.stmemo_flow[-1],
                                    # medium left in the source
                                    ch.stmemo_medleft[-1],
                                    # controller mode
                                    ch.stmemo_mode[-1],
                                    # reference flow
                                    ch.stmemo_ref_flow[-1],
                                    # constant pressure setpoint
                                    ch.stmemo_const_press[-1],
                                    # P, I, D gains
                                    ch.stmemo_p_gain[-1], ch.stmemo_i_gain[-1], ch.stmemo_d_gain[-1]]
                            else:
                                row = row + [None]*9
                        # record the controller state depdning on the mode
                        logwriter.writerow(row, )

            # UPDATE THE CHECK COUNTER AND WAIT FOR THE NEXT CHECK
            cc_check_cntr += 1  # update the check counter for the next step
            sleep_time = cc_check_cntr*self.dt_check-(time.time()-self.cc_start_time)   # find sleep time until the next step
            time.sleep(max(sleep_time,0.0))  # sleep until the next step
        return

    # handle user input during cruise control
    def cruise_control_user(self):
        # get the set of commands on offer for a given valve mode
        cmds_on_offer = 'stop; set_ref_flow, set_const_press, set_gains, purge_integ'
        if (not self.valve.in_use):
            cmds_on_offer += '; change_medium'
        elif (self.valve.mode == 'set'):
            cmds_on_offer += '; set_valve_inlet'
        elif (self.valve.mode == 'pwm'):
            cmds_on_offer += '; set_input_conc'
        elif((self.valve.mode == 'set_scripted' or self.valve.mode == 'pwm_scripted')
              and (not self.valve.script_running)):
            cmds_on_offer += '; launch_valve_script'
        if (self.recirc.in_use):
            if (self.recirc.mode == 'manual'):
                cmds_on_offer += '; set_recirc_state'
            elif(self.recirc.mode == 'scripted'):
                cmds_on_offer += '; launch_recirc_script'

        cmds_on_offer += '; live_plot'

        while self.doing_cruise_control:
            # sleep for a while to let the OB-1 deal with the previous command
            if not(self.threads_just_started):
                time.sleep(self.dt_check)

            # First, print messages from the OB-1 handler, if any
            try:
                OB1_print = self.print_queue.get_nowait()
                print(OB1_print)
            except:
                pass

            # User input
            user_cmd = input('What would you like to do? \n('+cmds_on_offer+'): ')
            
            # OB-1 COMMANDS --------------------------------------------------------------------------------------
            if(user_cmd=='stop'):   # stop the cruise control
                print('Stopping cruise control...')
                self.user_cmd_queue.put((0,         # command code: 0 for stopping the cruise control
                                         0,         # channel: irrelevant for cmd 0
                                         0, 0, 0))   # args: irrelevant for cmd 0
                break
            elif(user_cmd=='set_ref_flow'):  # set the reference flow
                if(self.channels[0].in_use and (not self.channels[1].in_use)):
                    ch_id=1
                elif((not self.channels[0].in_use) and self.channels[1].in_use):
                    ch_id=2
                else:
                    ch_id = get_valid_input_int("Specify the channel (1,2) : ")
                ref_flow = get_valid_input_float("Specify the reference flow (ul/min) : ")
                self.user_cmd_queue.put((1,                 # command code: 1 for setting a new reference flow
                                         ch_id,             # channel
                                         ref_flow, 0, 0))   # args: zeroth is the new ref flow, others irrelevant
            elif (user_cmd == 'set_const_press'):  # set a constant pressure
                if (self.channels[0].in_use and (not self.channels[1].in_use)):
                    ch_id = 1
                elif ((not self.channels[0].in_use) and self.channels[1].in_use):
                    ch_id = 2
                else:
                    ch_id = get_valid_input_int("Specify the channel (1,2) : ")
                const_press = get_valid_input_float("Specify the constant pressure (mbar) : ")
                self.user_cmd_queue.put((2,  # command code: 2 for setting a constant pressure
                                         ch_id,     # channel
                                         const_press, 0, 0))
            elif(user_cmd=='set_gains'):  # set the PI(D?) gains
                if (self.channels[0].in_use and (not self.channels[1].in_use)):
                    ch_id = 1
                elif ((not self.channels[0].in_use) and self.channels[1].in_use):
                    ch_id = 2
                else:
                    ch_id = get_valid_input_int("Specify the channel (1,2) : ")
                p_gain = get_valid_input_float("Specify the new P gain : ")
                i_gain = get_valid_input_float("Specify the new I gain : ")
                d_gain = get_valid_input_float("Specify the new D gain : ")
                self.user_cmd_queue.put((3,                 # command code: 3 for changing the PI(D?) gains
                                         ch_id,             # channel
                                         # args
                                         p_gain,            # zeroth arg is the new P gain
                                         i_gain,            # first arg is the new I gain
                                         d_gain))                # second arg is the new D gain
            elif(user_cmd=='live_plot'):  # open a live plot
                self.user_cmd_queue.put((4,  # command code: 4 for stopping the cruise control
                                         0, # channel: irrelevant for cmd 4
                                         0, 0, 0))  # args: irrelevant for cmd 4
            elif(user_cmd=='change_medium'):
                if (self.channels[0].in_use and (not self.channels[1].in_use)):
                    ch_id = 1
                elif ((not self.channels[0].in_use) and self.channels[1].in_use):
                    ch_id = 2
                else:
                    ch_id = get_valid_input_int("Specify the channel (1,2) : ")
                medleft_new = get_valid_input_float("Specify the new starting medium volume (ml): ")
                print(medleft_new)
                self.user_cmd_queue.put((5,  # command code: 5 for changing the medium source
                                         ch_id, # channel
                                         # args
                                         medleft_new, 0, 0))
            elif (user_cmd == 'purge_integ'):
                if (self.channels[0].in_use and (not self.channels[1].in_use)):
                    ch_id = 1
                elif ((not self.channels[0].in_use) and self.channels[1].in_use):
                    ch_id = 2
                else:
                    ch_id = get_valid_input_int("Specify the channel (1,2) : ")
                self.user_cmd_queue.put((6,  # command code: 5 for purging the integral controller memory
                                         ch_id,  # channel
                                         # args
                                         0, 0, 0))
            # VALVE COMMANDS -------------------------------------------------------------------------------------
            elif(user_cmd=='set_valve_inlet'):
                new_inlet = get_valid_input_int("Specify the inlet : ")
                self.user_valve_cmd_queue.put((0,   # command code: 0 for changing the valve inlet
                                               # args
                                               new_inlet, 0, 0))
            elif (user_cmd == 'set_input_conc'):
                new_input_conc = get_valid_input_float("Specify the PWM input conc. : ")
                self.user_valve_cmd_queue.put((1,  # command code: 1 for changing the PWM input conc.
                                               # args
                                               new_input_conc, 0, 0))
            elif(user_cmd == 'launch_valve_script'):
                self.user_valve_cmd_queue.put((2,  # command code: 2 for launching a script
                                               # args
                                               0, 0, 0))

            # RECIRCULATOR COMMANDS -------------------------------------------------------------------------------------
            elif (user_cmd == 'set_recirc_state'):
                while(True):
                    new_state_A_or_B = input("Specify the state (A,B): ")
                    if(new_state_A_or_B == 'A'):
                        new_state = 1
                        break
                    elif(new_state_A_or_B == 'B'):
                        new_state = 2
                        break
                self.user_recirc_cmd_queue.put((0,  # command code: 0 for changing the recirculator inlet
                                               # args
                                               new_state, 0, 0))
            elif (user_cmd == 'launch_recirc_script'):
                self.user_recirc_cmd_queue.put((2,  # command code: 2 for launching a script; yes I know '1' is undefined, but I'm going fro consistency with the recirculator
                                               # args
                                               0, 0, 0))
        return

    def cruise_control_valve(self):
        curr_inlet_set_time = time.time()  # time at which the valve was set to the current inlet - FOR SET_SCRIPTED
        curr_pwm_input_set_time = time.time()  # time at which the valve was set to enforce the set PWM input - FOR PWM & PWM_SCRIPTED

        pwm_period_cntr = 0 # number of PWM periods which have passed since the beginning of cruise control
        valve_check_cntr = 0 # number of checks on the valve by the computer since the beginning of cruise control
        next_action = 0 # next action: 0 if getting commands/updating stmemo, 1 if switching to high input, 2 if switching to low input

        # FOR SCRIPTED VALVE COMMANDS
        script_launch_time = -1.0 # time at which the scrip was launched - initialised as impossible -1 before the launch event
        next_scripted_cmd_time = -1.0   # time of execution for the next scripted command
        next_scripted_cmd = -1  # the next scripted command

        # set inlet mode - just check for user-prompted inlet changes every dt_check seconds (next_action always zero)
        if(self.valve.mode=='set'):
            while (self.doing_cruise_control):
                # HANDLE THE USER INPUT, IF ANY
                try:
                    # get the user command and the argument
                    user_cmd, user_cmd_arg0, user_cmd_arg1, user_cmd_arg2 = self.user_valve_cmd_queue.get_nowait()
                    
                    if (user_cmd == 0):  # 0 for changing the valve inlet
                        # print an error message for impossible inlets outside the 1-12 range
                        if(user_cmd_arg0<1 or user_cmd_arg0>12):
                            self.print_queue.put('ERROR: impossible valve inlet')
                        # print an error message if the desired valve inlet not in use
                        if(user_cmd_arg0>len(self.valve.inlet_concs)):
                            self.print_queue.put('ERROR: valve inlet not in use')
                        # otherwise, update valve controls
                        else:
                            with self.lock:
                                self.valve.inlet = int(user_cmd_arg0)
                                self.valve.input_conc = self.valve.inlet_concs[self.valve.inlet-1]
                            # set the valve to desired input
                            valve_error_msg = MUX_DRI_Set_Valve(self.valve.instridval,  # valve ID value
                                                                c_int32(self.valve.inlet),  # valve inlet
                                                                0  # valve rotation direction (zero for shortest)
                                                                )
                            # record valve error in the log
                            if (valve_error_msg != 0):
                                with open(self.valve.error_logfilepath, 'a') as file:
                                    file.write('Valve error '+str(valve_error_msg)+
                                               ' at t = '+ str(time.time()-self.cc_start_time) + ' s\n')
                            self.print_queue.put('Inlet changed')
                    else:
                        self.print_queue.put('ERROR: the valve is in set inlet mode')
                except:
                    pass

                # RECORD THE VALVE DATA IN SHORT-TERM MEMORY
                # get the time of record
                t_check_absolute = time.time()  # get the time of the check - NOT from the start of cruise control
                t_check_relative = t_check_absolute - self.cc_start_time  # convert to time from the start of cruise control
                with self.lock:
                    self.valve.stmemo_time.append(t_check_relative)
                    self.valve.stmemo_inlet.append(self.valve.inlet)
                    self.valve.stmemo_input_conc.append(self.valve.input_conc)
                    # pop the oldest readings if short-term memory is full
                    if (self.valve.stmemo_time[-1]-self.valve.stmemo_time[0]>self.valve.short_term_memo_dur):
                        self.valve.stmemo_time.pop(0)
                        self.valve.stmemo_inlet.pop(0)
                        self.valve.stmemo_input_conc.pop(0)

                # LOG THE DATA IF IT'S TIME TO DO SO
                if (valve_check_cntr % self.valve.log_every_points == 0):
                    with open(self.valve.logfilepath, 'a', newline='') as logfile:
                        logwriter = csv.writer(logfile)
                        with self.lock:
                            row = [t_check_relative]  # time of the readings
                            row = row + [self.valve.stmemo_inlet[-1], self.valve.stmemo_input_conc[-1]]
                            logwriter.writerow(row, )

                # UPDATE THE PERIOD COUNTER AND WAIT FOR THE NEXT CHECK
                valve_check_cntr += 1  # update the check counter for the next step
                sleep_time = valve_check_cntr * self.valve.dt_check - (time.time() - self.cc_start_time)  # find sleep time until the next step
                time.sleep(max(sleep_time, 0.0))  # sleep until the next step
        
        # PWM mode
        elif(self.valve.mode=='pwm'):
            # first action is setting the inlet valve to high if it ever should be high (and to low otherwise)
            if (self.valve.pwm_duty_cycle >= 0):
                next_action = 1
            else:
                next_action = 2
            # set the PWM period countrer
            pwm_period_cntr = 0

            # cruise control loop
            while (self.doing_cruise_control):
                # act depending on what ought to be done next

                # CHECK ON THE VALVE AND USER COMMANDS
                if(next_action == 0):
                    # HANDLE THE USER INPUT, IF ANY
                    try:
                        # get the user command and the argument
                        user_cmd, user_cmd_arg0, user_cmd_arg1, user_cmd_arg2 = self.user_valve_cmd_queue.get_nowait()

                        if (user_cmd == 1):  # 1 for changing the desired PWM conc.
                            # update controls - will come into effect at the next duty cycle
                            with self.lock:
                                self.valve.input_conc = user_cmd_arg0
                                self.valve.pwm_update_controls()
                            # report back to the user
                            self.print_queue.put('Input conc. changed')
                            # reset the PWM period counter and time at which the valve was set to enforce the given PWM input
                            pwm_period_cntr = 0
                            curr_pwm_input_set_time = time.time()
                            # reset the valve check counter, since we're now enforcing a new PWM input conc.
                            valve_check_cntr = 0
                            # out of due order, set the inlet valve to high if it ever should be high (and to low otherwise)
                            if (self.valve.pwm_duty_cycle > 0):
                                next_action = 1
                                continue
                            else:
                                next_action = 2
                                continue
                        else:
                            self.print_queue.put('ERROR: the valve is in PWM mode')
                    except:
                        pass
                    # RECORD THE VALVE DATA IN SHORT-TERM MEMORY
                    # get the time of record
                    t_check_absolute = time.time()  # get the time of the check - NOT from the start of cruise control
                    t_check_rel_to_cc_start = t_check_absolute - self.cc_start_time  # convert to time from THE START OF CRUISE CONTROL
                    t_check_rel_to_pwm_set = t_check_absolute - curr_pwm_input_set_time  # convert to time from THE MOMENT WE STARTED TRACKING THE GIVEN PWM INPUT CONC.
                    with self.lock:
                        self.valve.stmemo_time.append(t_check_rel_to_cc_start)
                        self.valve.stmemo_inlet.append(self.valve.inlet)
                        self.valve.stmemo_input_conc.append(self.valve.input_conc)
                        self.valve.stmemo_pwm_duty_cycle.append(self.valve.pwm_duty_cycle)
                        self.valve.stmemo_pwm_low_inlet.append(self.valve.pwm_low_inlet)
                        self.valve.stmemo_pwm_high_inlet.append(self.valve.pwm_high_inlet)
                        # pop the oldest readings if short-term memory is full
                        if (self.valve.stmemo_time[-1]-self.valve.stmemo_time[0]>self.valve.short_term_memo_dur):
                            self.valve.stmemo_time.pop(0)
                            self.valve.stmemo_inlet.pop(0)
                            self.valve.stmemo_input_conc.pop(0)
                            self.valve.stmemo_pwm_duty_cycle.pop(0)
                            self.valve.stmemo_pwm_low_inlet.pop(0)
                            self.valve.stmemo_pwm_high_inlet.pop(0)
                    # LOG THE DATA IF IT'S TIME TO DO SO
                    if (valve_check_cntr % self.valve.log_every_points == 0):
                        with open(self.valve.logfilepath, 'a', newline='') as logfile:
                            logwriter = csv.writer(logfile)
                            with self.lock:
                                row = [t_check_rel_to_cc_start]  # time of the readings
                                row = row + [self.valve.stmemo_inlet[-1], self.valve.stmemo_input_conc[-1]]
                                row = row + [
                                    self.valve.stmemo_pwm_duty_cycle[-1],
                                    self.valve.stmemo_pwm_low_inlet[-1],
                                    self.valve.stmemo_pwm_high_inlet[-1]
                                ]
                                logwriter.writerow(row, )

                    # update the number of checks which have been performed
                    valve_check_cntr += 1


                # SET VALVE INLET TO HIGH
                elif(next_action == 1):
                    # switching to the high inlet again means a PWM period has been completed
                    pwm_period_cntr += 1
                    
                    # now, actually switch the valve to the high state
                    valve_error_msg = MUX_DRI_Set_Valve(self.valve.instridval,  # valve ID value
                                                        c_int32(self.valve.pwm_high_inlet),  # valve inlet
                                                        # 2  # valve rotation direction (2 for counterclockwise)
                                                        0  # valve rotation direction (0 for shortest)
                                                        )

                    # record valve error in the log, if any
                    if (valve_error_msg != 0):
                        with open(self.valve.error_logfilepath, 'a') as file:
                            file.write('Valve error ' + str(valve_error_msg) +
                                       ' at t = ' + str(time.time() - self.cc_start_time) + ' s\n')

                    self.valve.inlet = self.valve.pwm_high_inlet    # no lock as accessed only by thisn thread


                # SET VALVE INLET TO LOW
                elif(next_action == 2):
                    valve_error_msg = MUX_DRI_Set_Valve(self.valve.instridval,  # valve ID value
                                                        c_int32(self.valve.pwm_low_inlet),  # valve inlet
                                                        # 1  # valve rotation direction (1 for clockwise)
                                                        0  # valve rotation direction (0 for shortest)
                                                        )
                    # record valve error in the log, if any
                    if (valve_error_msg != 0):
                        with open(self.valve.error_logfilepath, 'a') as file:
                            file.write('Valve error ' + str(valve_error_msg) +
                                       ' at t = ' + str(time.time() - self.cc_start_time) + ' s\n')

                    self.valve.inlet = self.valve.pwm_low_inlet    # no lock as accessed only by thisn thread


                # DETERMINE WHICH ACTION TO TAKE NEXT
                # if PWM means just permanently staying in high or low state, just wait until the next check
                if (self.valve.pwm_duty_cycle <= 0 or self.valve.pwm_duty_cycle >= 1):
                    next_action = 0
                    time_since_curr_pwm_input_set = time.time() - curr_pwm_input_set_time  # get the time the valve has been enforcing a given input conc. by PWM
                    time_to_check = max(valve_check_cntr * self.valve.dt_check - time_since_curr_pwm_input_set, 0.0)
                    time.sleep(time_to_check)
                # otherwise, determine time until each action has to be made
                else:
                    time_since_curr_pwm_input_set = time.time() - curr_pwm_input_set_time   # get the time the valve has been enforcing a given input conc. by PWM
                    time_to_switch_to_high = max(self.valve.pwm_period * pwm_period_cntr - time_since_curr_pwm_input_set, 0.0)  # get the time until the next switch to a high input
                    if(self.valve.inlet == self.valve.pwm_high_inlet):  # if we have a high inlet now, the
                        time_to_switch_to_low = max(self.valve.pwm_period * pwm_period_cntr - self.valve.pwm_time_in_low - time_since_curr_pwm_input_set,0.0)
                    else:
                        time_to_switch_to_low = max(self.valve.pwm_period * (pwm_period_cntr+1) - self.valve.pwm_time_in_low - time_since_curr_pwm_input_set,0.0)
                    time_to_check = max(valve_check_cntr * self.valve.dt_check - time_since_curr_pwm_input_set, 0.0)
                    # print([time_to_check, time_to_switch_to_high, time_to_switch_to_low])
                    # schedule the soonest action (valve inlet switching prioritised over computer checks)
                    if((time_to_switch_to_high < time_to_switch_to_low) and (time_to_switch_to_high <= time_to_check)):
                        next_action = 1
                        time.sleep(time_to_switch_to_high)
                    elif(time_to_switch_to_low <= time_to_check):
                        next_action = 2
                        time.sleep(time_to_switch_to_low)
                    else:
                        next_action = 0
                        time.sleep(time_to_check)

        # SET mode with scripted commands
        elif(self.valve.mode == 'set_scripted'):
            # first action is the initial check on the valve by the computer
            next_action = 0
            # set the executed script command counter - initialised as the impossible -1
            scripted_cmd_cntr = -1
            # get the number of scripted commands
            with self.lock:
                num_scripted_cmds = len(self.valve.scripted_cmds)

            # cruise control loop
            while (self.doing_cruise_control):
                # act depending on what ought to be done next

                # CHECK ON THE VALVE
                if (next_action == 0):
                    # HANDLE THE USER INPUT, IF ANY
                    try:
                        # get the user command and the argument
                        user_cmd, user_cmd_arg0, user_cmd_arg1, user_cmd_arg2 = self.user_valve_cmd_queue.get_nowait()

                        if (user_cmd == 2):  # 2 for launching the valve script
                            # record the time at which the script was launched
                            script_launch_time = time.time()
                            # indicate that the script is now running
                            with self.lock:
                                self.valve.script_running = True
                            # start counting the scripted commands
                            script_cmd_cntr = 0
                            # get the next command from the script and the time of its execution
                            next_scripted_cmd_time = self.valve.scripted_cmd_times[script_cmd_cntr]
                            next_scripted_cmd = self.valve.scripted_cmds[script_cmd_cntr]
                            # if the command is to be executed striaghtaway, update pwm controls out of due order
                            if (next_scripted_cmd_time == 0):
                                next_action = 3
                                continue

                        else:
                            self.print_queue.put('ERROR: the valve is in SCRIPTED SET INLET mode')
                    except:
                        pass

                    # RECORD THE VALVE DATA IN SHORT-TERM MEMORY
                    # get the time of record
                    t_check_absolute = time.time()  # get the time of the check - NOT from the start of cruise control
                    t_check_relative = t_check_absolute - self.cc_start_time  # convert to time from the start of cruise control
                    with self.lock:
                        self.valve.stmemo_time.append(t_check_relative)
                        self.valve.stmemo_inlet.append(self.valve.inlet)
                        self.valve.stmemo_input_conc.append(self.valve.input_conc)
                        # pop the oldest readings if short-term memory is full
                        if (self.valve.stmemo_time[-1] - self.valve.stmemo_time[0] > self.valve.short_term_memo_dur):
                            self.valve.stmemo_time.pop(0)
                            self.valve.stmemo_inlet.pop(0)
                            self.valve.stmemo_input_conc.pop(0)

                    # LOG THE DATA IF IT'S TIME TO DO SO
                    if (valve_check_cntr % self.valve.log_every_points == 0):
                        with open(self.valve.logfilepath, 'a', newline='') as logfile:
                            logwriter = csv.writer(logfile)
                            with self.lock:
                                row = [t_check_relative]  # time of the readings
                                row = row + [self.valve.stmemo_inlet[-1], self.valve.stmemo_input_conc[-1]]
                                if(script_launch_time < 0):
                                    row = row + [None]
                                else:
                                    row = row + [time.time() - script_launch_time]
                                logwriter.writerow(row, )

                    # UPDATE THE CHECK PERIOD COUNTER
                    valve_check_cntr += 1  # update the check counter for the next step

                # SWITCH THE VALVE INLET IF NEEDED
                elif(next_action == 3):
                    # print an error message for impossible inlets outside the 1-12 range
                    if (next_scripted_cmd < 1 or next_scripted_cmd > 12):
                        self.print_queue.put('ERROR: impossible valve inlet')
                    # print an error message if the desired valve inlet not in use
                    if (next_scripted_cmd > len(self.valve.inlet_concs)):
                        self.print_queue.put('ERROR: valve inlet not in use')
                    # otherwise, update valve controls
                    else:
                        with self.lock:
                            self.valve.inlet = int(next_scripted_cmd)
                            self.valve.input_conc = self.valve.inlet_concs[self.valve.inlet - 1]

                        # set the valve to desired input
                        valve_error_msg = MUX_DRI_Set_Valve(self.valve.instridval,  # valve ID value
                                                            c_int32(self.valve.inlet),  # valve inlet
                                                            0  # valve rotation direction (zero for shortest)
                                                            )
                        # record valve error in the log, if any
                        if (valve_error_msg != 0):
                            with open(self.valve.error_logfilepath, 'a') as file:
                                file.write('Valve error ' + str(valve_error_msg) +
                                           ' at t = ' + str(time.time() - self.cc_start_time) + ' s\n')

                        # get the next command in the script
                        scripted_cmd_cntr += 1
                        if (scripted_cmd_cntr == num_scripted_cmds):
                            next_scripted_cmd_time = -1.0  # no more commands in the script
                            next_scripted_cmd = -1
                        else:
                            with self.lock:
                                next_scripted_cmd_time = self.valve.scripted_cmd_times[scripted_cmd_cntr]
                                next_scripted_cmd = self.valve.scripted_cmds[scripted_cmd_cntr]
                        # reset time at which the valve was set to the current inlet
                        curr_inlet_set_time = time.time()
                        # reset the valve check counter, since we're now enforcing a new PWM input conc.
                        valve_check_cntr = 0

                # DETERMINE WHICH ACTION TO TAKE NEXT
                # check on the valve or execut a scritped command
                time_since_curr_inlet_set = time.time() - curr_inlet_set_time  # get the time the valve has been enforcing a given input conc. by PWM
                # time to the next valve check by the computer
                time_to_check = max(valve_check_cntr * self.valve.dt_check - time_since_curr_inlet_set,
                                    0.0)
                # time to the next scripted command
                if (next_scripted_cmd_time < 0):
                    time_to_next_scripted_cmd = np.inf
                else:
                    time_to_next_scripted_cmd = max(
                        next_scripted_cmd_time - (time.time() - script_launch_time), 0.0)
                # pick the shortest time to wait, prioritising script command execution all things equal
                if (time_to_check < time_to_next_scripted_cmd):
                    next_action = 0
                    time.sleep(time_to_check)
                else:
                    next_action = 3
                    time.sleep(time_to_next_scripted_cmd)

        # PWM mode with scripted commands
        elif (self.valve.mode == 'pwm_scripted'):
            # first action is setting the inlet valve to high if it ever should be high (and to low otherwise)
            if (self.valve.pwm_duty_cycle >= 0):
                next_action = 1
            else:
                next_action = 2
            # set the PWM period counter
            pwm_period_cntr = 0
            # set the executed script command counter - initialised as the impossible -1
            scripted_cmd_cntr = -1
            # get the number of scripted commands
            with self.lock:
                num_scripted_cmds = len(self.valve.scripted_cmds)

            # cruise control loop
            while (self.doing_cruise_control):
                # act depending on what ought to be done next

                # CHECK ON THE VALVE AND USER COMMANDS
                if (next_action == 0):
                    # HANDLE THE USER INPUT, IF ANY
                    try:
                        # get the user command and the argument
                        user_cmd, user_cmd_arg0, user_cmd_arg1, user_cmd_arg2 = self.user_valve_cmd_queue.get_nowait()

                        if (user_cmd == 2):  # 2 for launching the valve script
                            # record the time at which the script was launched
                            script_launch_time = time.time()
                            # indicate that the script is now running
                            with self.lock:
                                self.valve.script_running = True
                            # start counting the scripted commands
                            script_cmd_cntr = 0
                            # get the next command from the script and the time of its execution
                            next_scripted_cmd_time = self.valve.scripted_cmd_times[script_cmd_cntr]
                            next_scripted_cmd = self.valve.scripted_cmds[script_cmd_cntr]
                            # if the command is to be executed striaghtaway, update pwm controls out of due order
                            if(next_scripted_cmd_time==0):
                                next_action = 3
                                continue
                        else:
                            self.print_queue.put('ERROR: the valve is in SCRIPTED PWM mode')
                    except:
                        pass
                    # RECORD THE VALVE DATA IN SHORT-TERM MEMORY
                    # get the time of record
                    t_check_absolute = time.time()  # get the time of the check - NOT from the start of cruise control
                    t_check_rel_to_cc_start = t_check_absolute - self.cc_start_time  # convert to time from THE START OF CRUISE CONTROL
                    t_check_rel_to_pwm_set = t_check_absolute - curr_pwm_input_set_time  # convert to time from THE MOMENT WE STARTED TRACKING THE GIVEN PWM INPUT CONC.
                    with self.lock:
                        self.valve.stmemo_time.append(t_check_rel_to_cc_start)
                        self.valve.stmemo_inlet.append(self.valve.inlet)
                        self.valve.stmemo_input_conc.append(self.valve.input_conc)
                        self.valve.stmemo_pwm_duty_cycle.append(self.valve.pwm_duty_cycle)
                        self.valve.stmemo_pwm_low_inlet.append(self.valve.pwm_low_inlet)
                        self.valve.stmemo_pwm_high_inlet.append(self.valve.pwm_high_inlet)
                        # pop the oldest readings if short-term memory is full
                        if (self.valve.stmemo_time[-1] - self.valve.stmemo_time[0] > self.valve.short_term_memo_dur):
                            self.valve.stmemo_time.pop(0)
                            self.valve.stmemo_inlet.pop(0)
                            self.valve.stmemo_input_conc.pop(0)
                            self.valve.stmemo_pwm_duty_cycle.pop(0)
                            self.valve.stmemo_pwm_low_inlet.pop(0)
                            self.valve.stmemo_pwm_high_inlet.pop(0)
                    # LOG THE DATA IF IT'S TIME TO DO SO
                    if (valve_check_cntr % self.valve.log_every_points == 0):
                        with open(self.valve.logfilepath, 'a', newline='') as logfile:
                            logwriter = csv.writer(logfile)
                            with self.lock:
                                row = [t_check_rel_to_cc_start]  # time of the readings
                                # valve inlet and input conc.
                                row = row + [self.valve.stmemo_inlet[-1], self.valve.stmemo_input_conc[-1]]
                                # pwm characteristics
                                row = row + [
                                    self.valve.stmemo_pwm_duty_cycle[-1],
                                    self.valve.stmemo_pwm_low_inlet[-1],
                                    self.valve.stmemo_pwm_high_inlet[-1]
                                ]
                                # time since the script was launched
                                if(script_launch_time<0):
                                    row = row + [None]
                                else:
                                    row = row + [time.time() - script_launch_time]
                                logwriter.writerow(row, )

                    # update the number of checks which have been performed
                    valve_check_cntr += 1


                # SET VALVE INLET TO HIGH
                elif (next_action == 1):
                    # switching to the high inlet again means a PWM period has been completed
                    pwm_period_cntr += 1

                    # now, actually switch the valve to the high state
                    valve_error_msg = MUX_DRI_Set_Valve(self.valve.instridval,  # valve ID value
                                                        c_int32(self.valve.pwm_high_inlet),  # valve inlet
                                                        # 2  # valve rotation direction (2 for counterclockwise)
                                                        0  # valve rotation direction (0 for shortest)
                                                        )
                    # record valve error in the log, if any
                    if (valve_error_msg != 0):
                        with open(self.valve.error_logfilepath, 'a') as file:
                            file.write('Valve error ' + str(valve_error_msg) +
                                       ' at t = ' + str(time.time() - self.cc_start_time) + ' s\n')

                    self.valve.inlet = self.valve.pwm_high_inlet  # no lock as accessed only by thisn thread


                # SET VALVE INLET TO LOW
                elif (next_action == 2):
                    valve_error_msg = MUX_DRI_Set_Valve(self.valve.instridval,  # valve ID value
                                                        c_int32(self.valve.pwm_low_inlet),  # valve inlet
                                                        # 1  # valve rotation direction (1 for clockwise)
                                                        0  # valve rotation direction (0 for shortest)
                                                        )
                    # record valve error in the log, if any
                    if (valve_error_msg != 0):
                        with open(self.valve.error_logfilepath, 'a') as file:
                            file.write('Valve error ' + str(valve_error_msg) +
                                       ' at t = ' + str(time.time() - self.cc_start_time) + ' s\n')

                    self.valve.inlet = self.valve.pwm_low_inlet  # no lock as accessed only by thisn thread


                # UPDATE VALVE CONTROLS ACCORDING TO THE SCRIPTED COMMAND
                elif(next_action == 3):
                    with self.lock:
                        self.valve.input_conc = next_scripted_cmd
                        self.valve.pwm_update_controls()
                    # get the next command in the script
                    scripted_cmd_cntr += 1
                    if(scripted_cmd_cntr == num_scripted_cmds):
                        next_scripted_cmd_time = -1.0  # no more commands in the script
                        next_scripted_cmd = -1
                    else:
                        with self.lock:
                            next_scripted_cmd_time = self.valve.scripted_cmd_times[scripted_cmd_cntr]
                            next_scripted_cmd = self.valve.scripted_cmds[scripted_cmd_cntr]
                    # reset the PWM period counter and time at which the valve was set to enforce the given PWM input
                    pwm_period_cntr = 0
                    curr_pwm_input_set_time = time.time()
                    # reset the valve check counter, since we're now enforcing a new PWM input conc.
                    valve_check_cntr = 0
                    # out of due order, set the inlet valve to high if it ever should be high (and to low otherwise)
                    if (self.valve.pwm_duty_cycle > 0):
                        next_action = 1
                        continue
                    else:
                        next_action = 2
                        continue

                # DETERMINE WHICH ACTION TO TAKE NEXT
                # if PWM means just permanently staying in high or low state, just wait until the next check or the next scripted command
                if (self.valve.pwm_duty_cycle <= 0 or self.valve.pwm_duty_cycle >= 1):
                    time_since_curr_pwm_input_set = time.time() - curr_pwm_input_set_time  # get the time the valve has been enforcing a given input conc. by PWM
                    # time to the next valve check by the computer
                    time_to_check = max(valve_check_cntr * self.valve.dt_check - time_since_curr_pwm_input_set,
                                        0.0)
                    # time to the next scripted command
                    if(next_scripted_cmd_time < 0):
                        time_to_next_scripted_cmd = np.inf
                    else:
                        time_to_next_scripted_cmd = max(next_scripted_cmd_time - (time.time() - script_launch_time), 0.0)
                    # pick the shortest time to wait, prioritising script command execution all things equal
                    if(time_to_check<time_to_next_scripted_cmd):
                        next_action = 0
                        time.sleep(time_to_check)
                    else:
                        next_action = 3
                        time.sleep(time_to_next_scripted_cmd)
                # otherwise, determine time until each action has to be made
                else:
                    time_since_curr_pwm_input_set = time.time() - curr_pwm_input_set_time  # get the time the valve has been enforcing a given input conc. by PWM
                    time_to_switch_to_high = max(
                        self.valve.pwm_period * pwm_period_cntr - time_since_curr_pwm_input_set,
                        0.0)  # get the time until the next switch to a high input
                    if (self.valve.inlet == self.valve.pwm_high_inlet):  # if we have a high inlet now, closest switch is to the low inlet
                        time_to_switch_to_low = max(
                            self.valve.pwm_period * pwm_period_cntr - self.valve.pwm_time_in_low - time_since_curr_pwm_input_set,
                            0.0)
                    else:
                        time_to_switch_to_low = max(self.valve.pwm_period * (
                                    pwm_period_cntr + 1) - self.valve.pwm_time_in_low - time_since_curr_pwm_input_set,
                                                    0.0)
                    time_to_check = max(valve_check_cntr * self.valve.dt_check - time_since_curr_pwm_input_set, 0.0)
                    if (next_scripted_cmd_time < 0):
                        time_to_next_scripted_cmd = np.inf
                    else:
                        time_to_next_scripted_cmd = max(next_scripted_cmd_time - (time.time() - script_launch_time), 0.0)
                    # schedule the soonest action (valve inlet switching prioritised over computer checks)
                    # prioritise the script command execution over all others, valve switchings over computer checks
                    if(time_to_next_scripted_cmd <= time_to_switch_to_high and time_to_next_scripted_cmd <= time_to_switch_to_low and time_to_next_scripted_cmd <= time_to_check):
                        next_action = 3
                        time.sleep(time_to_next_scripted_cmd)
                    elif ((time_to_switch_to_high < time_to_switch_to_low) and (time_to_switch_to_high <= time_to_check)):
                        next_action = 1
                        time.sleep(time_to_switch_to_high)
                    elif (time_to_switch_to_low <= time_to_check):
                        next_action = 2
                        time.sleep(time_to_switch_to_low)
                    else:
                        next_action = 0
                        time.sleep(time_to_check)
            
        return

    def cruise_control_recirc(self):
        curr_state_set_time = time.time()  # time at which the recirculator was set to the current state

        recirc_check_cntr = 0  # number of checks on the valve by the computer since the beginning of cruise control
        next_action = 0  # next action: 0 if getting commands/updating stmemo, 1 if switching to high input, 2 if switching to low input

        # FOR SCRIPTED VALVE COMMANDS
        script_launch_time = -1.0  # time at which the scrip was launched - initialised as impossible -1 before the launch event
        next_scripted_cmd_time = -1.0  # time of execution for the next scripted command
        next_scripted_cmd = -1  # the next scripted command

        # mode with manual commands
        if (self.recirc.mode == 'manual'):
            while (self.doing_cruise_control):
                # HANDLE THE USER INPUT, IF ANY
                try:
                    # get the user command and the argument
                    user_cmd, user_cmd_arg0, user_cmd_arg1, user_cmd_arg2 = self.user_recirc_cmd_queue.get_nowait()

                    if (user_cmd == 0):  # 0 for changing the recirculator state
                        # print an error message for impossible states outside the 1-2 (alias A-B) range
                        if (user_cmd_arg0 < 1 or user_cmd_arg0 > 2):
                            self.print_queue.put('ERROR: impossible recirculator state')
                        # otherwise, update recirculator controls
                        else:
                            with self.lock:
                                self.recirc.state = int(user_cmd_arg0)
                            # set the recirculator to desired state
                            recirc_error_msg = MUX_DRI_Set_Valve(self.recirc.instridval,  # valve ID value
                                                                c_int32(self.recirc.state),  # valve inlet
                                                                0  # valve rotation direction (zero for shortest)
                                                                )
                            # record valve error in the log
                            if (recirc_error_msg != 0):
                                with open(self.recirc.error_logfilepath, 'a') as file:
                                    file.write('Recirculator error ' + str(recirc_error_msg) +
                                               ' at t = ' + str(time.time() - self.cc_start_time) + ' s\n')
                            self.print_queue.put('State changed')
                    else:
                        self.print_queue.put('ERROR: the recirculator is in manual mode')
                except:
                    pass

                # RECORD THE RECIRCULATOR DATA IN SHORT-TERM MEMORY
                # get the time of record
                t_check_absolute = time.time()  # get the time of the check - NOT from the start of cruise control
                t_check_relative = t_check_absolute - self.cc_start_time  # convert to time from the start of cruise control
                with self.lock:
                    self.recirc.stmemo_time.append(t_check_relative)
                    self.recirc.stmemo_state.append(self.recirc.state)
                    # pop the oldest readings if short-term memory is full
                    if (self.recirc.stmemo_time[-1] - self.recirc.stmemo_time[0] > self.recirc.short_term_memo_dur):
                        self.recirc.stmemo_time.pop(0)
                        self.recirc.stmemo_state.pop(0)

                # LOG THE DATA IF IT'S TIME TO DO SO
                if (recirc_check_cntr % self.recirc.log_every_points == 0):
                    with open(self.recirc.logfilepath, 'a', newline='') as logfile:
                        logwriter = csv.writer(logfile)
                        with self.lock:
                            row = [t_check_relative]  # time of the readings
                            row = row + ['AB'[self.recirc.stmemo_state[-1]-1]]
                            logwriter.writerow(row, )

                # UPDATE THE PERIOD COUNTER AND WAIT FOR THE NEXT CHECK
                recirc_check_cntr += 1  # update the check counter for the next step
                sleep_time = recirc_check_cntr * self.recirc.dt_check - (
                            time.time() - self.cc_start_time)  # find sleep time until the next step
                time.sleep(max(sleep_time, 0.0))  # sleep until the next step


        # mode with scripted commands
        elif (self.recirc.mode == 'scripted'):
            # first action is the initial check on the recirculator by the computer
            next_action = 0
            # set the executed script command counter - initialised as the impossible -1
            scripted_cmd_cntr = -1
            # get the number of scripted commands
            with self.lock:
                num_scripted_cmds = len(self.recirc.scripted_cmds)

            # cruise control loop
            while (self.doing_cruise_control):
                # act depending on what ought to be done next

                # CHECK ON THE RECIRCULATOR
                if (next_action == 0):
                    # HANDLE THE USER INPUT, IF ANY
                    try:
                        # get the user command and the argument
                        user_cmd, user_cmd_arg0, user_cmd_arg1, user_cmd_arg2 = self.user_recirc_cmd_queue.get_nowait()

                        if (user_cmd == 2):  # 2 for launching the  script
                            # record the time at which the script was launched
                            script_launch_time = time.time()
                            # indicate that the script is now running
                            with self.lock:
                                self.recirc.script_running = True
                            # start counting the scripted commands
                            script_cmd_cntr = 0
                            # get the next command from the script and the time of its execution
                            next_scripted_cmd_time = self.recirc.scripted_cmd_times[script_cmd_cntr]
                            next_scripted_cmd = self.recirc.scripted_cmds[script_cmd_cntr]
                            # if the command is to be executed striaghtaway, do it out of due order
                            if (next_scripted_cmd_time == 0):
                                next_action = 3
                                continue

                        else:
                            self.print_queue.put('ERROR: the recirculator is in SCRIPTED mode')
                    except:
                        pass

                    # RECORD THE RECIRCULATOR DATA IN SHORT-TERM MEMORY
                    # get the time of record
                    t_check_absolute = time.time()  # get the time of the check - NOT from the start of cruise control
                    t_check_relative = t_check_absolute - self.cc_start_time  # convert to time from the start of cruise control
                    with self.lock:
                        self.recirc.stmemo_time.append(t_check_relative)
                        self.recirc.stmemo_state.append(self.recirc.state)
                        # pop the oldest readings if short-term memory is full
                        if (self.recirc.stmemo_time[-1] - self.recirc.stmemo_time[0] > self.recirc.short_term_memo_dur):
                            self.recirc.stmemo_time.pop(0)
                            self.recirc.stmemo_state.pop(0)

                    # LOG THE DATA IF IT'S TIME TO DO SO
                    if (recirc_check_cntr % self.recirc.log_every_points == 0):
                        with open(self.recirc.logfilepath, 'a', newline='') as logfile:
                            logwriter = csv.writer(logfile)
                            with self.lock:
                                row = [t_check_relative]  # time of the readings
                                row = row + ['AB'[self.recirc.stmemo_state[-1]-1]]
                                if (script_launch_time < 0):
                                    row = row + [None]
                                else:
                                    row = row + [time.time() - script_launch_time]
                                logwriter.writerow(row, )

                    # UPDATE THE CHECK PERIOD COUNTER
                    recirc_check_cntr += 1  # update the check counter for the next step

                # SWITCH THE RECIRCULATOR STATE IF NEEDED
                elif (next_action == 3):
                    # print an error message for impossible inlets outside the 1-12 range
                    if (next_scripted_cmd < 1 or next_scripted_cmd > 2):
                        self.print_queue.put('ERROR: impossible recirculator state')
                    # otherwise, update recirculator controls
                    else:
                        with self.lock:
                            self.recirc.state = int(next_scripted_cmd)

                        # set the recirc to desired input
                        recirc_error_msg = MUX_DRI_Set_Valve(self.recirc.instridval,  # recirculator ID value
                                                            c_int32(self.recirc.state),  # recirculator state
                                                            0  # recirculator rotation direction (zero for shortest)
                                                            )
                        # record recirculator error in the log, if any
                        if (recirc_error_msg != 0):
                            with open(self.recirc.error_logfilepath, 'a') as file:
                                file.write('Recirculator error ' + str(recirc_error_msg) +
                                           ' at t = ' + str(time.time() - self.cc_start_time) + ' s\n')

                        # get the next command in the script
                        scripted_cmd_cntr += 1
                        if (scripted_cmd_cntr == num_scripted_cmds):
                            next_scripted_cmd_time = -1.0  # no more commands in the script
                            next_scripted_cmd = -1
                        else:
                            with self.lock:
                                next_scripted_cmd_time = self.recirc.scripted_cmd_times[scripted_cmd_cntr]
                                next_scripted_cmd = self.recirc.scripted_cmds[scripted_cmd_cntr]
                                print(next_scripted_cmd_time, next_scripted_cmd)
                        # reset time at which the recirculator was set to the current inlet
                        curr_state_set_time = time.time()
                        # reset the recirculator check counter, since we're now enforcing a new PWM input conc.
                        recirc_check_cntr = 0

                # DETERMINE WHICH ACTION TO TAKE NEXT
                # check on the recirculator or execute a scritped command
                time_since_curr_state_set = time.time() - curr_state_set_time  # get the time the valve has been enforcing a given input conc. by PWM
                # time to the next recirculator check by the computer
                time_to_check = max(recirc_check_cntr * self.recirc.dt_check - time_since_curr_state_set,
                                    0.0)
                # time to the next scripted command
                if (next_scripted_cmd_time < 0):
                    time_to_next_scripted_cmd = np.inf
                else:
                    time_to_next_scripted_cmd = max(
                        next_scripted_cmd_time - (time.time() - script_launch_time), 0.0)
                # pick the shortest time to wait, prioritising script command execution all things equal
                if (time_to_check < time_to_next_scripted_cmd):
                    next_action = 0
                    time.sleep(time_to_check)
                else:
                    next_action = 3
                    time.sleep(time_to_next_scripted_cmd)

        return

    # stop cruise control
    def stop_cruise_control(self):
        self.doing_cruise_control = False

        # set all pressures to zero
        ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                      1,  # which channel is being controlled
                                      0,  # which pressure is being set
                                      byref(self.Calib), 1000  # calibration (do not touch)
                                      )
        ob1_error_msg = OB1_Set_Press(self.OB1.value,  # which OB-1 is being used
                                      2,  # which channel is being controlled
                                      0,  # which pressure is being set
                                      byref(self.Calib), 1000  # calibration (do not touch)
                                      )

        # destroy communications with the OB-1
        ob1_error_msg = OB1_Destructor(self.OB1.value    # which OB-1 is being used
                                       )

        # if valve in use, destroy communications
        if(self.valve.in_use):
            valve_error_msg = MUX_DRI_Destructor(self.valve.instridval)

        # if recirculator in use, destroy communications
        if (self.recirc.in_use):
            recirc_error_msg = MUX_DRI_Destructor(self.recirc.instridval)

        print('Cruise control stopped')
        return

    # check the safeguards, cut off the pressure if conditions met for a given channel
    def check_channel_safeguards(self, ch):
        if(ch.num_safeguards==0):
            # if no safeguards are specified, return False and 0 (to avoid errors)
            return False, 0
        else:
            any_cutoff_condition_true = False
            with self.lock:
                for i in range(ch.num_safeguards):
                    # condition can only be met if the period considered by the safeguard has elapsed since the beginning
                    if(len(ch.stmemo_p)>=ch.safeguard_check_steps[i]):
                        p_cutoff_cond_true = (
                                ((ch.stmemo_p[-ch.safeguard_check_steps[i]:] <= ch.p_bounds[i]).all() and ch.p_lnub[i] == -1)
                                or
                                ((ch.stmemo_p[-ch.safeguard_check_steps[i]:] >= ch.p_bounds[i]).all() and ch.p_lnub[i] == 1)
                                or
                                ch.p_lnub[i] == 0 # if no pressure condition is specified, the pressure condition is always true
                        )
                        flow_cutoff_cond_true = (
                                ((ch.stmemo_flow[-ch.safeguard_check_steps[i]:] <= ch.flow_bounds[i]).all() and ch.flow_lnub[i] == -1)
                                or
                                ((ch.stmemo_flow[-ch.safeguard_check_steps[i]:] >= ch.flow_bounds[i]).all() and ch.flow_lnub[i] == 1)
                                or
                                ch.flow_lnub[i] == 0 # if no flow condition is specified, the flow condition is always true
                        )
                        if(p_cutoff_cond_true and flow_cutoff_cond_true):
                            print('!!!PRESSURE CUT-OFF CONDITION %d TRIGGERED!!!' % i)
                            any_cutoff_condition_true = True
                            break

            # return whether any cutoff condition is true and the index of the condition
            return any_cutoff_condition_true, i

    # PID control signal calculator for a given channel
    def channel_PID_controller(self, ch, flow, t_check):
        # calculate the flow error
        flerr = ch.ref_flow - flow

        # integrate the flow error
        flerrint = ch.flerrint + flerr*self.dt_check
        # limit the integral term for anti-windup
        ch.flerrint=max(ch.min_flerrint, min(flerrint, ch.max_flerrint))

        # get the derivative component - for the flow itself to avoid kicks as the reference changes
        with self.lock:
            if(len(ch.stmemo_flow)>=1):
                flder = (flow - ch.stmemo_flow[-1])/(t_check - ch.stmemo_time[-1])
            else:
                flder = 0

        # calculate the pressure to supply
        p_calc = ch.p_gain*flerr + ch.i_gain*ch.flerrint + ch.d_gain*flder
        # clip the pressure to physically possible values (0-2000 mbar) and/or user-defined values
        p = max(max(0, ch.min_press_ctrl), min(p_calc, ch.max_p_ctrl, ch.max_p_ctrl))

        # return the pressure to feed to the system
        return p

    # LIVE PLOTTING OF THE CRUISE CONTROL DATA -------------------------------------------------------------------------
    # plot the short-term memory during cruise control
    def live_stmemo_plot(self):
        plt.ion()  # Turn on interactive mode
        fig_live, axs_live = plt.subplots(nrows=2, ncols=3,
                                          width_ratios=[2, 1, 1], height_ratios=[1, 1],
                                          figsize=(10 , 5))

        # adjust the layout
        fig_live.tight_layout(pad=2.0)

        # plot the flow and reference flow in the same subfigure using matplotlib
        # plot formatting
        axs_live[0,0].grid()
        axs_live[0,0].set_ylim(bottom=-5, top=120)
        axs_live[0,0].set_xlabel('Time since cruise control start (s)')
        axs_live[0,0].set_ylabel('Flow rate (ul/min)')
        # start live plot lines for flow and reference flow
        ch1_flow_line_live, = axs_live[0,0].plot([], [], label='CH 1 Flow',
                                      linestyle='-', color=self.channels[0].plot_colour)
        ch1_ref_flow_line_live, = axs_live[0,0].plot([], [], label='CH 1 Ref. flow',
                                     linestyle='--', color=self.channels[0].ref_colour)
        ch2_flow_line_live, = axs_live[0, 0].plot([], [], label='CH 2 Flow',
                                                  linestyle='-', color=self.channels[1].plot_colour)
        ch2_ref_flow_line_live, = axs_live[0, 0].plot([], [], label='CH 2 Ref. flow',
                                                      linestyle='--', color=self.channels[1].ref_colour)
        # show legend
        axs_live[0,0].legend(loc='upper left')

        # plot the pressure in a separate subfigure
        # plot formatting
        axs_live[1,0].grid()
        axs_live[1,0].set_ylim(bottom=0, top=2000)
        # plot
        axs_live[1,0].set_xlabel('Time since cruise control start (s)')
        axs_live[1,0].set_ylabel('Pressure (mbar)')
        # start live plot line for pressure
        ch1_p_line_live, = axs_live[1,0].plot([], [], label='CH 1 Press.',
                                   linestyle='-', color=self.channels[0].plot_colour)
        # start live plot line for constant pressure setpoint
        ch1_const_press_line_live, = axs_live[1,0].plot([], [], label='CH 1 Const. press.',
                                             linestyle='--', color=self.channels[0].ref_colour)
        # start live plot line for pressure
        ch2_p_line_live, = axs_live[1, 0].plot([], [], label='CH 2 Press.',
                                               linestyle='-', color=self.channels[1].plot_colour)
        # start live plot line for constant pressure setpoint
        ch2_const_press_line_live, = axs_live[1, 0].plot([], [], label='CH 2 Const. press.',
                                                         linestyle='--', color=self.channels[1].ref_colour)
        # show legend
        axs_live[1,0].legend(loc='upper left')

        # plot the PID gains for channel 1
        if(self.channels[0].in_use):
            # plot formatting
            axs_live[0,1].grid()
            # start live plot lines for the gains
            ch1_p_gain_line_live, = axs_live[0,1].plot([], [], label='CH 1 P gain',
                                            linestyle='-', color='darkviolet', alpha=0.5)
            ch1_i_gain_line_live, = axs_live[0,1].plot([], [], label='CH 1 I gain',
                                            linestyle='-', color='darkorange', alpha=0.5)
            ch1_d_gain_line_live, = axs_live[0,1].plot([], [], label='CH 1 D gain',
                                            linestyle='-', color='lightseagreen', alpha=0.5)
            # show legend
            axs_live[0,1].legend(loc='upper left')
        else:
            axs_live[0,1].axis('off')
            # just pass Nones as plot lines to be passing something
            ch1_p_gain_line_live = None
            ch1_i_gain_line_live = None
            ch1_d_gain_line_live = None

        # plot the PID gains for channel 2
        if(self.channels[1].in_use):
            # plot formatting
            axs_live[0, 2].grid()
            # start live plot lines for the gains
            ch2_p_gain_line_live, = axs_live[0, 2].plot([], [], label='CH 2 P gain',
                                                        linestyle='-', color='darkviolet', alpha=0.5)
            ch2_i_gain_line_live, = axs_live[0, 2].plot([], [], label='CH 2 I gain',
                                                        linestyle='-', color='darkorange', alpha=0.5)
            ch2_d_gain_line_live, = axs_live[0, 2].plot([], [], label='CH 2 D gain',
                                                        linestyle='-', color='lightseagreen', alpha=0.5)
            # show legend
            axs_live[0, 2].legend(loc='upper left')
        else:
            axs_live[0, 2].axis('off')


        # IF VALVE AND/OR RECIRCULATOR NOT IN USE, plot estimated medium left in source for each channel
        if(not self.valve.in_use and not self.recirc.in_use):
            # plot the estimated medium left in the source for channel 1
            if(self.channels[0].in_use):
                # plot formatting
                axs_live[1, 1].grid()
                axs_live[1, 1].set_ylim(bottom=0, top=55)
                # plot
                axs_live[1, 1].set_xlabel('Time since cruise control start (s)')
                axs_live[1, 1].set_ylabel('Medium left in source (ml)')
                # start live plot line for pressure
                ch1_medleft_line_live, = axs_live[1, 1].plot([], [], label='CH 1 Medium left',
                                                             linestyle='-', color='gold')
                # show legend
                axs_live[1, 1].legend(loc='upper left')
            else:
                axs_live[1, 1].axis('off')
                # just pass Nones as plot lines to be passing something
                c1_medleft_line_live = None

            # plot the estimated medium left in the source for channel 2
            if (self.channels[1].in_use):
                # plot formatting
                axs_live[1, 2].grid()
                axs_live[1, 2].set_ylim(bottom=0, top=55)
                # plot
                axs_live[1, 2].set_xlabel('Time since cruise control start (s)')
                axs_live[1, 2].set_ylabel('Medium left in source (ml)')
                # start live plot line for pressure
                ch2_medleft_line_live, = axs_live[1, 2].plot([], [], label='CH 2 Medium left',
                                                         linestyle='-', color='gold')
                # show legend
                axs_live[1, 2].legend(loc='upper left')
            else:
                axs_live[1, 2].axis('off')
                # just pass Nones as plot lines to be passing something
                ch2_medleft_line_live = None

        # IF VALVE IN USE, plot valve states
        else:
            # plot the valve inlet
            axs_live[1, 1].grid()
            axs_live[1, 1].set_ylim(bottom=0, top=13)
            # plot labels
            axs_live[1, 1].set_xlabel('Time since cruise control start (s)')
            axs_live[1, 1].set_ylabel('Valve inlet')
            # ticks corresponding to inlets
            axs_live[1, 1].set_yticks(np.arange(1,12.5,1,np.dtype(int)))
            # mark the possible inlet range
            axs_live[1, 1].axhspan(ymin=0, ymax=1, color='grey', alpha=0.5)
            axs_live[1, 1].axhspan(ymin=12, ymax=13, color='grey', alpha=0.5)
            # plot the inlets
            valve_inlet_line_live, = axs_live[1, 1].plot([], [], label='Valve inlet',
                           linestyle='-', color='black')

            # IF RECIRCULATOR NOT IN USE, also plot concentrations created by the valve
            if(not self.recirc.in_use):
                # plot the valve input conc.
                axs_live[1, 2].grid()
                input_conc_ylims=(self.valve.inlet_concs[0]*0.75, self.valve.inlet_concs[-1]*1.25)
                axs_live[1, 2].set_ylim(input_conc_ylims[0],input_conc_ylims[1])
                # plot labels
                axs_live[1, 2].set_xlabel('Time since cruise control start (s)')
                axs_live[1, 2].set_ylabel('Set input conc.')
                # mark the possible inlet range
                axs_live[1, 2].axhspan(ymin=input_conc_ylims[0], ymax=self.valve.inlet_concs[0], color='grey', alpha=0.5)
                axs_live[1, 2].axhspan(ymin=self.valve.inlet_concs[-1], ymax=input_conc_ylims[-1], color='grey', alpha=0.5)
                # plot the set input concentration
                valve_input_conc_line_live, = axs_live[1, 2].plot([], [], label='Set input conc.',
                               linestyle='-', color='black')

        # IF RECIRCULATOR IN USE, plot the state
        if(self.recirc.in_use):
            # plot the recirculator state
            axs_live[1, 2].grid()
            axs_live[1, 2].set_ylim(bottom=0, top=3)
            # plot labels
            axs_live[1, 2].set_xlabel('Time since cruise control start (s)')
            axs_live[1, 2].set_ylabel('Recirc. state')
            # ticks corresponding to inlets
            axs_live[1, 2].set_yticks(np.arange(1, 2.5, 1, np.dtype(int)))
            axs_live[1, 2].set_yticklabels('AB') # redefined as state letters
            # mark the possible inlet range
            axs_live[1, 2].axhspan(ymin=0, ymax=1, color='grey', alpha=0.5)
            axs_live[1, 2].axhspan(ymin=2, ymax=3, color='grey', alpha=0.5)
            # plot the inlets
            recirc_state_line_live, = axs_live[1, 2].plot([], [], label='Recirc. state',
                                                         linestyle='-', color='black')

        # IF SOME PLOTS NOT PRESENT, just pass Nones as plot lines to be passing something
        if (not self.channels[0].in_use): # channel 1 PID gains
            ch1_p_gain_line_live = None
            ch1_i_gain_line_live = None
            ch1_d_gain_line_live = None
        if(not self.channels[1].in_use): # channel 2 PID gains
            ch2_p_gain_line_live = None
            ch2_i_gain_line_live = None
            ch2_d_gain_line_live = None
        if (self.valve.in_use or self.recirc.in_use or (not self.channels[0].in_use)):  # channel 1 medium left
            ch1_medleft_line_live = None
        if (self.valve.in_use or self.recirc.in_use or (not self.channels[1].in_use)):  # channel medium left
            ch2_medleft_line_live = None
        if(not self.valve.in_use): # valve plot lines
            valve_inlet_line_live = None
            valve_input_conc_line_live = None
        if(self.recirc.in_use):
            valve_input_conc_line_live = None
        else:
            recirc_state_line_live = None

        # define the plot updater function
        def live_plot_updater(frames):
            with (self.lock):
                # update the flow plot
                if(self.channels[0].in_use):
                    ch1_flow_line_live.set_data(self.channels[0].stmemo_time, self.channels[0].stmemo_flow)
                    ch1_ref_flow_line_live.set_data(self.channels[0].stmemo_time, self.channels[0].stmemo_ref_flow)
                if (self.channels[1].in_use):
                    ch2_flow_line_live.set_data(self.channels[1].stmemo_time, self.channels[1].stmemo_flow)
                    ch2_ref_flow_line_live.set_data(self.channels[1].stmemo_time, self.channels[1].stmemo_ref_flow)
                axs_live[0,0].relim()
                axs_live[0,0].autoscale_view()

                # update the pressure plot
                if(self.channels[0].in_use):
                    ch1_p_line_live.set_data(self.channels[0].stmemo_time, self.channels[0].stmemo_p)
                    ch1_const_press_line_live.set_data(self.channels[0].stmemo_time, self.channels[0].stmemo_const_press)
                if (self.channels[1].in_use):
                    ch2_p_line_live.set_data(self.channels[1].stmemo_time, self.channels[1].stmemo_p)
                    ch2_const_press_line_live.set_data(self.channels[1].stmemo_time, self.channels[1].stmemo_const_press)
                axs_live[1,0].relim()
                axs_live[1,0].autoscale_view()

                # update the PID gains plot for channel 1
                if(self.channels[0].in_use):
                    ch1_p_gain_line_live.set_data(self.channels[0].stmemo_time, self.channels[0].stmemo_p_gain)
                    ch1_i_gain_line_live.set_data(self.channels[0].stmemo_time, self.channels[0].stmemo_i_gain)
                    ch1_d_gain_line_live.set_data(self.channels[0].stmemo_time, self.channels[0].stmemo_d_gain)
                    axs_live[0,1].relim()
                    axs_live[0,1].autoscale_view()

                # update the PID gains plot for channel 2
                if (self.channels[1].in_use):
                    ch2_p_gain_line_live.set_data(self.channels[1].stmemo_time, self.channels[1].stmemo_p_gain)
                    ch2_i_gain_line_live.set_data(self.channels[1].stmemo_time, self.channels[1].stmemo_i_gain)
                    ch2_d_gain_line_live.set_data(self.channels[1].stmemo_time, self.channels[1].stmemo_d_gain)
                    axs_live[0, 2].relim()
                    axs_live[0, 2].autoscale_view()

                # IF VALVE AND/OR RECIRCULATOR NOT IN USE, update medium left plots
                if(not self.valve.in_use and not self.recirc.in_use):
                    # update the medium left plot for channel 1
                    if(self.channels[0].in_use):
                        ch1_medleft_line_live.set_data(self.channels[0].stmemo_time, self.channels[0].stmemo_medleft)
                        axs_live[1, 1].relim()
                        axs_live[1, 1].autoscale_view()

                    # update the medium left plot for channel 2
                    if (self.channels[1].in_use):
                        ch2_medleft_line_live.set_data(self.channels[1].stmemo_time, self.channels[1].stmemo_medleft)
                        axs_live[1, 2].relim()
                        axs_live[1, 2].autoscale_view()

                # IF VALVE IN USE, update valve plots
                else:
                    # update the inlet plot for the valve
                    valve_inlet_line_live.set_data(self.valve.stmemo_time, self.valve.stmemo_inlet)
                    axs_live[1, 1].relim()
                    axs_live[1, 1]. autoscale_view()

                    # update the input conc plot for the valve
                    if (not self.recirc.in_use):
                        valve_input_conc_line_live.set_data(self.valve.stmemo_time, self.valve.stmemo_input_conc)
                        axs_live[1, 2].relim()
                        axs_live[1, 2].autoscale_view()

                # IF RECIRCULATOR IN USE, update recirculator plots
                if(self.recirc.in_use):
                    recirc_state_line_live.set_data(self.recirc.stmemo_time, self.recirc.stmemo_state)
                    axs_live[1, 2].relim()
                    axs_live[1, 2].autoscale_view()

            return ch1_flow_line_live, ch1_p_line_live, \
                ch1_medleft_line_live, \
                ch1_ref_flow_line_live, ch1_const_press_line_live, \
                ch1_p_gain_line_live, ch1_i_gain_line_live, ch1_d_gain_line_live, \
                ch2_flow_line_live, ch2_p_line_live, \
                ch2_medleft_line_live, \
                ch2_ref_flow_line_live, ch2_const_press_line_live, \
                ch2_p_gain_line_live, ch2_i_gain_line_live, ch2_d_gain_line_live, \
                valve_inlet_line_live, valve_input_conc_line_live, \
                recirc_state_line_live


                # create the animator
        ani = FuncAnimation(fig_live, live_plot_updater, interval=1000, blit=False,
                            save_count=0,
                            cache_frame_data=False)

        # show the live plot
        try:
            plt.show(block=True)
        except KeyboardInterrupt:
            self.stop_cruise_control()
            print('Keyboard-interrupted')
        return

    # POST-FACTUM PLOTTING THE CRUISE CONTROL DATA ---------------------------------------------------------------------
    # general function for plotting data
    def plot_cc_data(self,
                     # variables plotted always
                     data_time,  # time since cruise control start
                     data_p,     # pressure (measured at source)
                     data_flow,  # flow rate (measured at the outlet)
                     data_medleft,  # medium left in the source
                     data_mode,  # controller mode (0 for flow reference tracking, 1 for constant pressure)
                     data_ref_flow,   # reference flow rate
                     data_const_press,  # constant pressure setpoint
                     data_gains, # P, I, D gains
                     data_valve_inlet,  # inlet selected at the valve
                     data_valve_input_conc, # valve input concentration
                     data_recirc_state, # recirculator states
                     # pressure and flow plot ranges
                     p_range=(-10, 2000),  # pressure range
                     flow_range=(-10, 80),  # flow rate range
                     # output file name
                     plotfilename='logs/OB1_PID_log.png'
                     ):
        plt.ioff()  # Turn off interactive mode

        # initialise the figure with subplots
        fig, axs = plt.subplots(nrows=2, ncols=3,
                                width_ratios=[2, 1, 1], height_ratios=[1, 1],
                                figsize=(10, 5))

        # plot the flow and reference flow in the same subfigure using matplotlib
        # plot formatting
        axs[0,0].grid()
        axs[0,0].set_ylim(bottom=flow_range[0], top=flow_range[1])
        # plot flow
        if(self.channels[0].in_use):
            axs[0,0].plot(data_time[0], data_flow[0], label='CH 1 Flow',
                        linestyle='-', color=self.channels[0].plot_colour)
            axs[0,0].plot(data_time[0], data_ref_flow[0], label='CH 1 Ref. flow',
                        linestyle='--', color=self.channels[0].ref_colour)
        if (self.channels[1].in_use):
            axs[0, 0].plot(data_time[1], data_flow[1], label='CH 2 Flow',
                           linestyle='-', color=self.channels[1].plot_colour)
            axs[0, 0].plot(data_time[1], data_ref_flow[1], label='CH 2 Ref. flow',
                           linestyle='--', color=self.channels[1].ref_colour)
        axs[0,0].set_xlabel('Time since cruise control start (s)')
        axs[0,0].set_ylabel('Flow rate (ul/min)')
        axs[0,0].legend(loc='upper left')

        # plot the pressure in a separate subfigure
        # plot formatting
        axs[1,0].grid()
        axs[1,0].set_ylim(bottom=p_range[0], top=p_range[1])
        # plot pressure
        if(self.channels[0].in_use):
            axs[1,0].plot(data_time[0], data_p[0], label='CH 1 Press.',
                        linestyle='-', color=self.channels[0].plot_colour)
            axs[1,0].plot(data_time[0], data_const_press[0], label='CH 1 Set press.',
                        linestyle='--', color=self.channels[0].ref_colour)
        if (self.channels[1].in_use):
            axs[1, 0].plot(data_time[1], data_p[1], label='CH 2 Press.',
                           linestyle='-', color=self.channels[1].plot_colour)
            axs[1, 0].plot(data_time[1], data_const_press[1], label='CH 2 Set press.',
                           linestyle='--', color=self.channels[1].ref_colour)
        axs[1,0].set_xlabel('Time since cruise control start (s)')
        axs[1,0].set_ylabel('Pressure (mbar)')
        axs[1,0].legend(loc='upper left')

        # plot the PID gains for channel 1
        axs[0, 1].grid()
        if(self.channels[0].in_use):
            # plot the gains
            axs[0, 1].plot(data_time[0], data_gains['P'][0], label='CH 1 P gain',
                           linestyle='-', color='darkviolet', alpha=0.5)
            axs[0, 1].plot(data_time[0], data_gains['I'][0], label='CH 1 I gain',
                           linestyle='-', color='darkorange', alpha=0.5)
            axs[0, 1].plot(data_time[0], data_gains['D'][0], label='CH 1 D gain',
                           linestyle='-', color='lightseagreen', alpha=0.5)
            # show legend
            axs[0, 1].legend(loc='upper left')
        else:
            axs[0, 1].axis('off')

        # plot the PID gains for channel 2
        axs[0, 2].grid()
        if (self.channels[1].in_use):
            # plot the gains
            axs[0, 2].plot(data_time[1], data_gains['P'][1], label='CH 2 P gain',
                           linestyle='-', color='darkviolet', alpha=0.5)
            axs[0, 2].plot(data_time[1], data_gains['I'][1], label='CH 2 I gain',
                           linestyle='-', color='darkorange', alpha=0.5)
            axs[0, 2].plot(data_time[1], data_gains['D'][1], label='CH 2 D gain',
                           linestyle='-', color='lightseagreen', alpha=0.5)
            # show legend
            axs[0, 2].legend(loc='upper left')
        else:
            axs[0, 2].axis('off')

        # IF VALVE AND/OR RECIRCULATOR NOT IN USE, plot estimated medium left in source for each channel
        if(not self.valve.in_use and not self.recirc.in_use):
            # plot the estimated medium left for channel 1
            axs[1, 1].grid()
            if(self.channels[0].in_use):
                axs[1, 1].set_ylim(bottom=0, top=55)
                # plot
                axs[1, 1].set_xlabel('Time since cruise control start (s)')
                axs[1, 1].set_ylabel('Medium left in source (ml)')
                # plot the medium left
                axs[1, 1].plot(data_time[0], data_medleft[0], label='CH 1 Medium left',
                               linestyle='-', color='gold')
                # show legend
                axs[1, 1].legend(loc='upper left')

            # plot the estimated medium left for channel 2
            axs[1, 2].grid()
            if (self.channels[1].in_use):
                axs[1, 2].set_ylim(bottom=0, top=55)
                # plot labels
                axs[1, 2].set_xlabel('Time since cruise control start (s)')
                axs[1, 2].set_ylabel('Medium left in source (ml)')
                # plot the medium left
                axs[1, 2].plot(data_time[1], data_medleft[1], label='CH 2 Medium left',
                               linestyle='-', color='gold')
                # show legend
                axs[1, 2].legend(loc='upper left')

        # OTHERWISE, PLIOT VALVE READINGS
        else:
            # plot the valve inlet
            axs[1, 1].grid()
            if (self.valve.in_use):
                # plot the valve inlet
                axs[1, 1].set_ylim(bottom=0, top=13)
                # plot labels
                axs[1, 1].set_xlabel('Time since cruise control start (s)')
                axs[1, 1].set_ylabel('Valve inlet')
                # ticks corresponding to inlets
                axs[1, 1].set_yticks(np.arange(1, 12.5, 1, np.dtype(int)))
                # mark the possible inlet range
                axs[1, 1].axhspan(ymin=0, ymax=1, color='grey', alpha=0.5)
                axs[1, 1].axhspan(ymin=12, ymax=13, color='grey', alpha=0.5)
                # plot the inlets
                axs[1, 1].plot(data_time[2], data_valve_inlet, label='Valve inlet',
                               linestyle='-', color='black')

            # plot the valve input conc. if recirculator not in use
            if(not self.recirc.in_use):
                axs[1, 2].grid()
                if (self.valve.in_use):
                    input_conc_ylims = (self.valve.inlet_concs[0] * 0.75, self.valve.inlet_concs[-1] * 1.25)
                    axs[1, 2].set_ylim(input_conc_ylims[0], input_conc_ylims[1])
                    # plot labels
                    axs[1, 2].set_xlabel('Time since cruise control start (s)')
                    axs[1, 2].set_ylabel('Set input conc.')
                    # mark the possible inlet range
                    axs[1, 2].axhspan(ymin=input_conc_ylims[0], ymax=self.valve.inlet_concs[0], color='grey',
                                           alpha=0.5)
                    axs[1, 2].axhspan(ymin=self.valve.inlet_concs[-1], ymax=input_conc_ylims[-1], color='grey',
                                           alpha=0.5)
                    # plot the inlets
                    axs[1, 2].plot(data_time[2], data_valve_input_conc, label='Set input conc.',
                                   linestyle='-', color='black')

        if(self.recirc.in_use):
            axs[1, 2].grid()
            if (self.valve.in_use):
                # plot the recirculator state
                axs[1, 2].set_ylim(bottom=0, top=3)
                # plot labels
                axs[1, 2].set_xlabel('Time since cruise control start (s)')
                axs[1, 2].set_ylabel('Recirc. state')
                # ticks corresponding to inlets
                axs[1, 2].set_yticks(np.arange(1, 2.5, 1, np.dtype(int)))
                axs[1, 2].set_yticklabels('AB')  # redefined as state letters
                # mark the possible inlet range
                axs[1, 2].axhspan(ymin=0, ymax=1, color='grey', alpha=0.5)
                axs[1, 2].axhspan(ymin=2, ymax=3, color='grey', alpha=0.5)
                # plot the inlets
                axs[1, 2].plot(data_time[3], data_recirc_state, label='Recirc. state',
                               linestyle='-', color='black')

        # adjust the layout
        fig.tight_layout(pad=1.0)
        # save figure
        plt.savefig(plotfilename)
        return

    # plot the shrt-term memory
    def plot_stmemo(self,
                    plotfilename='logs/OB1_PID_log.png'):
        self.plot_cc_data(data_time=[self.channels[0].stmemo_time, self.channels[1].stmemo_time, self.valve.stmemo_time, self.recirc.stmemo_time],
                          data_p=[self.channels[0].stmemo_p, self.channels[1].stmemo_p],
                          data_flow=[self.channels[0].stmemo_flow, self.channels[1].stmemo_flow],
                          data_medleft=[self.channels[0].stmemo_medleft, self.channels[1].stmemo_medleft],
                          data_mode=[self.channels[0].stmemo_mode, self.channels[1].stmemo_mode],
                          data_ref_flow=[self.channels[0].stmemo_ref_flow, self.channels[1].stmemo_ref_flow],
                          data_const_press=[self.channels[0].stmemo_const_press, self.channels[1].stmemo_const_press],
                          data_gains={'P': [self.channels[0].stmemo_p_gain, self.channels[1].stmemo_p_gain],
                                      'I': [self.channels[0].stmemo_i_gain, self.channels[1].stmemo_i_gain],
                                      'D': [self.channels[0].stmemo_d_gain, self.channels[1].stmemo_d_gain],},
                          data_valve_inlet=self.valve.stmemo_inlet,
                          data_valve_input_conc=self.valve.stmemo_input_conc,
                          data_recirc_state=self.recirc.stmemo_state,
                          plotfilename=plotfilename)
        return

    # plot the logged data from a file
    def plot_log(self,
                 OB1_logfilename='logs/OB1_PID_log.csv',
                 valve_logfilename='logs/valve_log.csv',
                 recirc_logfilename='logs/recirc_log.csv',
                 plotfilename='logs/log.png',
                 # show safeguards or not?
                 show_safeguards=False,
                 ):
        # read the OB-1 log file
        OB1_log_df = pd.read_csv(OB1_logfilename, na_values='N/A')   # get the dataframe from csv
        # read the valve log file (if not in use, just return a None)
        if(self.valve.in_use):
            valve_log_df = pd.read_csv(valve_logfilename, na_values='N/A')
        else:
            valve_log_df = None
        # read the recirculator log file (if not in use, just return a None)
        if (self.recirc.in_use):
            recirc_log_df = pd.read_csv(recirc_logfilename, na_values='N/A')
        else:
            recirc_log_df = None

        # get the data for time, pressure, flow
        log_time = [OB1_log_df['Time (s)'].to_numpy(), OB1_log_df['Time (s)'].to_numpy()]
        if(self.valve.in_use):
            log_time.append(valve_log_df['Time (s)'].to_numpy())
        else:
            log_time.append([None])
        if (self.recirc.in_use):
            log_time.append(recirc_log_df['Time (s)'].to_numpy())
        else:
            log_time.append([None])
        log_p = [OB1_log_df['CH 1 Pressure (mbar)'].to_numpy(), OB1_log_df['CH 2 Pressure (mbar)'].to_numpy()]
        log_flow = [OB1_log_df['CH 1 Flow (ul/min)'].to_numpy(), OB1_log_df['CH 2 Flow (ul/min)'].to_numpy()]
        # get the data for medium left in the source
        log_medleft = [OB1_log_df['CH 1 Medium left (ml)'].to_numpy(), OB1_log_df['CH 2 Medium left (ml)'].to_numpy()]
        # get the data for controller mode, reference flow and constant pressure setpoint
        log_mode = [OB1_log_df['CH 1 Mode'].to_numpy(), OB1_log_df['CH 2 Mode'].to_numpy()]
        log_ref_flow = [OB1_log_df['CH 1 Reference flow (ul/min)'].to_numpy(), OB1_log_df['CH 2 Reference flow (ul/min)'].to_numpy()]
        log_const_press = [OB1_log_df['CH 1 Constant pressure (mbar)'].to_numpy(), OB1_log_df['CH 2 Reference flow (ul/min)'].to_numpy()]
        # get the data for the gains
        log_gains={'P': [OB1_log_df['CH 1 P gain'].to_numpy(), OB1_log_df['CH 2 P gain'].to_numpy()],
                   'I': [OB1_log_df['CH 1 I gain'].to_numpy(), OB1_log_df['CH 2 I gain'].to_numpy()],
                   'D': [OB1_log_df['CH 1 D gain'].to_numpy(), OB1_log_df['CH 2 D gain'].to_numpy()]}
        # get the data for the valve (if not in use, just return a None)
        if (self.valve.in_use):
            log_valve_inlets = valve_log_df['Valve inlet']
            log_valve_input_concs = valve_log_df['Valve input conc.']
        else:
            log_valve_inlets = [None]
            log_valve_input_concs = [None]
        # get the data for the recirculator (if not in use, just return a None)
        if (self.recirc.in_use):
            log_recirc_states_A_or_B = recirc_log_df['Recirc. state']
            log_recirc_states=np.zeros(len(log_recirc_states_A_or_B))
            for i in range(0,len(log_recirc_states_A_or_B)):
                if(log_recirc_states_A_or_B[i]=='A'):
                    log_recirc_states[i] = 1
                else:
                    log_recirc_states[i] = 2
        else:
            log_recirc_states = [None]

        # plot the data
        self.plot_cc_data(data_time=log_time, data_p=log_p, data_flow=log_flow,
                          data_medleft=log_medleft,
                          data_mode=log_mode,
                          data_ref_flow=log_ref_flow, data_const_press=log_const_press,
                          data_gains=log_gains,
                          data_valve_inlet=log_valve_inlets,
                          data_valve_input_conc=log_valve_input_concs,
                          data_recirc_state=log_recirc_states,
                          plotfilename=plotfilename)
        return


# OB-1 CHANNEL MANAGER CLASS -------------------------------------------------------------------------------------------
class channel_manager:
    def __init__(self, id=1):
        self.in_use = False # by default, channel unused
        self.id = id    # channel ID: 1 or 2

        # colours for plotting
        plot_colours=['navy', 'darkred']
        ref_colours=['steelblue', 'firebrick']
        self.plot_colour=plot_colours[id-1]
        self.ref_colour=ref_colours[id-1]

        # variables initialised with -1 by default, lists initialised as empty

        # controller parameters and variables
        self.ref_flow = -1.0
        self.ref_flow = -1.0
        self.p_gain = -1.0
        self.i_gain = -1.0
        self.d_gain = -1.0
        self.min_flerrint = -1.0
        self.max_flerrint = -1.0
        self.min_press_ctrl = -1.0
        self.max_p_ctrl = -1.0
        self.flerrint = -1.0

        # channel safeguards
        self.p_bounds = np.array([])
        self.p_lnub = np.array([])
        self.flow_bounds = np.array([])
        self.flow_lnub = np.array([])
        self.safeguard_check_steps = np.array([])
        self.num_safeguards = 0
        self.safeguard_conds = []

        # medium in the source at the start of the run and currently left
        self.medstart = -1.0
        self.medleft = -1.0

        # short-term memory for control and logging
        # initialise short-term memory for the pressure, the flow and the measurement times
        self.stmemo_p = []
        self.stmemo_flow = []
        self.stmemo_time = []
        # initialise the short-term memory for estimated medium left in the source
        self.stmemo_medleft = []
        # initialise the short-term memory for controller mode
        self.stmemo_mode = []
        self.stmemo_ref_flow = []
        self.stmemo_const_press = []
        # initialise the short-term memory for controller gains
        self.stmemo_p_gain = []
        self.stmemo_i_gain = []
        self.stmemo_d_gain = []
        return


# MUX DISTRIBUTION VALVE MANAGER CLASS
class valve_manager:
    def __init__(self, id=1):
        self.in_use = False # by default, channel unused
        
        # instrument ID (assigned by the Elveflow SDK)
        self.instrid = c_int32()
        self.instridval = 0
        
        # valve-computer interaction parameters (initialised with zeros, then updated according to the settings)
        self.dt_check = 0.0
        self.dt_log = 0.0
        self.log_every_points = 0
        self.short_term_memo_dur = 0

        # valve data log file path (initialised with an empty string, then updated according to the user input)
        self.logfilepath =''
        self.error_logfilepath=''
        
        # valve mode set inlets ('set') or PWM ('pwm')
        # or scripted versions thereof ('_scripted') suffix added
        self.mode = 'set'
        
        # concentrations of a compound of interest in the inlets
        self.inlet_concs = np.array([0.0])
        
        # which inlet the valve is currently switched to
        self.inlet = 1

        # which concentration is currently being delivered
        self.input_conc = 0.0

        # PWM variables - initialised with dummy values
        self.pwm_period = 10  # period for PWM input, s
        self.pwm_low_inlet = 1  # low-concentration inlet used for PWM
        self.pwm_high_inlet = 2  # high-concentration inlet used for PWM
        self.pwm_time_in_high = self.pwm_period/2
        self.pwm_time_in_low = self.pwm_period/2
        self.pwm_duty_cycle = 0.5

        # colours for plotting
        self.plot_colour=['gray']

        # short-term memory for control and logging
        self.stmemo_time = []
        self.stmemo_inlet = [] # inlet we're switched to
        self.stmemo_input_conc = [] # input concentration to be delivered by PWM
        self.stmemo_pwm_duty_cycle = []    # PWM duty cycle (from 0 to 1)
        self.stmemo_pwm_low_inlet = []  # low-concentration inlet used for PWM
        self.stmemo_pwm_high_inlet = []    # high-concentration inlet used for PWM

        # program for the valve set by the script
        self.scripted_cmd_times = np.array([])
        self.scripted_cmds = np.array([]) # scripted inlets for set_scripted or input concs. for pwm_scripted
        self.script_running = False # indicator of whether the script is running

        return

    # update the PWM controls for the current desired input conc (self.input_conc)
    def pwm_update_controls(self):
        # find the inlet conc between which the desired input conc lies
        inlets_below = np.nonzero(self.inlet_concs<=self.input_conc)[0]
        if(len(inlets_below)==0):   # if no inlet concs are below the desired value, just pick the lowest available (i.e. the first one)
            self.pwm_low_inlet = 1
        else: # pick the highest inlet conc below desired value if there is one
            self.pwm_low_inlet = inlets_below[-1]+1 # note the +1 as inlet numbering starts from 1
        inlets_above = np.nonzero(self.inlet_concs>=self.input_conc)[0]
        if (len(inlets_above) == 0):  # if no inlet concs are below the desired value, just pick the lowest available (i.e. the last one)
            self.pwm_high_inlet = len(self.inlet_concs)
        else:  # pick the lowest inlet conc below desired value if there is one
            self.pwm_high_inlet = inlets_above[0] + 1  # note the +1 as inlet numbering starts from 1

        # find the duty cycle for the given input and low and high inlet
        if(self.pwm_low_inlet == self.pwm_high_inlet):  # if they are the same (e.g. desired value perfectly matches one conc), set zero duty cycle
            self.pwm_duty_cycle = 0.0
        else:
            pwm_duty_cycle_calc = (self.input_conc-self.inlet_concs[self.pwm_low_inlet-1])/(self.inlet_concs[self.pwm_high_inlet-1]-self.inlet_concs[self.pwm_low_inlet-1])
            self.pwm_duty_cycle = max(min(pwm_duty_cycle_calc,1.0),0.0)

        # find the times spent with high and low inlets
        self.pwm_time_in_high = self.pwm_period*self.pwm_duty_cycle
        self.pwm_time_in_low = self.pwm_period - self.pwm_time_in_high
        return

    # load the script for the valve
    def load_script(self):
        while True:
            # prompt the user to choose the script
            print('Select the valve script to load: ')
            script_filename = tkinter.filedialog.askopenfilename()

            # read the .csv script
            script_df = pd.read_csv(script_filename, na_values='N/A')  # get the dataframe from csv

            # check if the script is compatible with the valve mode, re-prompt the user if not
            if not (
                    (script_df.columns[1] == 'Valve inlet' and self.mode == 'set_scripted') or
                    (script_df.columns[1] == 'Valve input conc.' and self.mode == 'pwm_scripted')
            ):
                print('Wrong script for the valve mode: ' + self.mode)
                continue
            break

        # get the scripted switching times
        self.scripted_cmd_times = script_df['Time (s)'].to_numpy()
        # get the scripted commands
        if (self.mode == 'set_scripted'):
            self.scripted_cmds = script_df['Valve inlet'].to_numpy()
        else:
            self.scripted_cmds = script_df['Valve input conc.'].to_numpy()

        return


# MUX RECIRCULATOR MANAGER CLASS
class recirc_manager:
    def __init__(self, id=1):
        self.in_use = False  # by default, channel unused

        # instrument ID (assigned by the Elveflow SDK)
        self.instrid = c_int32()
        self.instridval = 0

        # recirculator-computer interaction parameters (initialised with zeros, then updated according to the settings)
        self.dt_check = 0.0
        self.dt_log = 0.0
        self.log_every_points = 0
        self.short_term_memo_dur = 0

        # recurculator mode: 'manual' or 'scripted' switching
        self.mode = 'manual'

        # recirculator data log file path (initialised with an empty string, then updated according to the user input)
        self.logfilepath = ''
        self.error_logfilepath = ''

        # which state the recirculator is currently switched to (A=1 or B=2)
        self.state = 1

        # colours for plotting
        self.plot_colour = ['gray']

        # short-term memory for control and logging
        self.stmemo_time = []
        self.stmemo_state = []  # state we're switched to

        # program for the recirculator set by the script
        self.scripted_cmd_times = np.array([])
        self.scripted_cmds = np.array([])  # scripted inlets for set_scripted or input concs. for pwm_scripted
        self.script_running = False  # indicator of whether the script is running

        return


    # load the script for the recirculator
    def load_script(self):
        while True:
            # prompt the user to choose the script
            print('Select the recirculator script to load: ')
            script_filename = tkinter.filedialog.askopenfilename()

            # read the .csv script
            script_df = pd.read_csv(script_filename, na_values='N/A')  # get the dataframe from csv

            # check if the script is compatible with the recirculator mode, re-prompt the user if not
            if not (
                    (script_df.columns[1] == 'Recirc. state' and self.mode == 'scripted')
            ):
                print('Wrong script for the recirculator mode: ' + self.mode)
                continue
            break

        # get the scripted switching times
        self.scripted_cmd_times = script_df['Time (s)'].to_numpy()
        # get the scripted commands
        if (self.mode == 'scripted'):
            scripted_cmds_A_or_B = script_df['Recirc. state']
            self.scripted_cmds = np.zeros(len(scripted_cmds_A_or_B),dtype=c_int32)
            for i in range(len(scripted_cmds_A_or_B)):
                if(scripted_cmds_A_or_B[i] == 'A'):
                    self.scripted_cmds[i] = 1
                elif(scripted_cmds_A_or_B[i] == 'B'):
                    self.scripted_cmds[i] = 2
                else:
                    print('Error! Invalid recirculator state')
                    return

        return


# MAIN FUNCTION --------------------------------------------------------------------------------------------------------
def main():
    # initialise the OB-1 manager
    Kenobi = OB1_manager()

    # append the experiment's starting time to the log file name
    date_time_string = (datetime.datetime.now()).strftime("_%d%m_%H%M")
    OB1_logfilename = r'logs/log'+ date_time_string + '_OB1.csv'
    valve_logfilename = r'logs/log' + date_time_string + '_valve.csv'
    recirc_logfilename = r'logs/log' + date_time_string + '_recirc.csv'

    # begin cruise control
    Kenobi.cruise_control(OB1_logfilename, valve_logfilename, recirc_logfilename)

    # plot the short-term memory at the end
    Kenobi.plot_stmemo(plotfilename='logs/final_stmemo' + date_time_string + '.png')

    # plot the logged data
    Kenobi.plot_log(show_safeguards=False,
                    OB1_logfilename=OB1_logfilename, valve_logfilename=valve_logfilename,
                    recirc_logfilename=recirc_logfilename,
                    plotfilename='logs/log' + date_time_string + '.png')

    return


# MAIN CALL ------------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    main()
