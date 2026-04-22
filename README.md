# MM_microfluidics
Python code for controlling the Elveflow microfluidic system for mother machine experiments
in STeel Lab, University of Oxford.

Besides the main code for the controller, the folder _valve_validation_ allows to generate 
figures for Section 1 of Chapter 5 of Kirill Sechkar's DPhil thesis, which
illsutrate why a multi-inlet valve is desirable for accurate provision of
chemical signals to cells by pulse width modulation. Note that the source
images for _valve_validation.ipynb_ are not provided due to the large file size,
but are available from Kirill Sechkar upon request 
(kirill.sechkar@queens.ox.ac.uk and/or useful.instructive@proton.me).

---

# User manual version 22 Apr 26:
(see Steel Lab's _Microscope1_ notebook for the latest version)

## Set up and Run

### General Notes

* All components must be on the same level
* Waste outlet must be **submerged in solution**
* A 65 µm resistor piece is available in the blue bag

### Setup Scheme

```
Medium → Sensor → Resistance element → Filter? → Inlet needle → Chip → Outlet needle → Waste
```

* Tape only the **top bit of the platform**
* Otherwise, platform movement is impaired

* Medium source tubes fixed outside
* Sensor, resistance, and filter placed on incubator bottom tray
* Special bent needles introduced
* Valve usage:

  * Always start from inlet 1
  * Use ascending order for concentrations
  * Save without units in settings file

* Filter is typically **not used** anymore (reduces bubbles and leaks)

## Assembly Steps

1. Assemble setup, *but*:

   * Don't connect needles to chip
   * Don't connect OB-1 to sensor or pressure hose
   * Don't include resistance element (use square adapter instead)

2. Set up the pressure supply:
   1. Flip toggle **off**
   2. Turn supply on
   3. Set pressure to **5 atm / 5000 mbar**
   4. Flip toggle **on**

3. Connect power and pressure supplies to the OB-1
   1. Connect the OB-1 to power source (via a cable and a plug)
   2. Connect the OB-1 to the USB-A communication cable
   3. Connect the OB-1 to the pressure source (via a large black tube))
   4. Press the on-off button on the OB-1


4. Connect the valve (if in use)
   1. Connect the valve to the power source (via a cable on top of the incubator
   2. Connect the OB-1 to the USB-A communication cable (labelled and found UNDER the incubator)

5. Launch Kirill's OB-1 Manager on the Microfluidics PC:
   1. Open Pycharm (project MM_microfluidics)
   2. Navigate to Microfluidics_trial
   3. In the Pycharm terminal, enter
    ```bash
    python3 ./one_stop_shop.py
    ```

6. The program will navigate you through setting up and running the controller, including how to best fill your tubing with liquid before the experiment

## After the experiment
1. Finish running the OB-1 Manager by...
   - Sending the stop command to the OB-1
   - Close the liveplot window (the script assumes you want to look at it and does not finish as long as it is open)
2. Clean the tubing
   1. Disassemble the setup
   2. Get a 50 ml syringe with a 21 gauge needle, fill with isopropanol
   3. Flush isopropanol through every piece of tubing
      - If there is an end free of a PEEK connector screw, just get the needle in
      - If there are PEEK connectors all around, get the needle into a short piece of tubing with a PEEK connector at the other end (there is one in the box precisely for this purpose), join the tubing with a connector
          - This is how you connect to the resistor
      - Squeezing liquid through the resistor is hard but worth it - do this until you see a few droplets come out of the other end
      - Using tubing with a PEEK, connect to the sensor and clean it as well
      - Repeat the above steps with Type II water
3. IF using a valve, clean it using water and isopropanol in a syringe by running python3 ./valve_clean.py
4. THROW AWAY the filter after every use
   - The rest of the components can be reused
5. Power down the pressure supply
   1. Turn the pressure supply toggle off
   2. If leaving for a long time, get rid of the built-up pressure
      1. Disconnect the black hose
      2. Turn the pressure supply toggle on
      3. Wait until the pressure dial reaches 0
      4. Turn the pressure supply toggle off
      5. Reconnect the black hose
6. Power down the OB-1
   1. Turn the OB-1 off
      - To avoid problems, this must be done after the pressure supply is disabled
   2. Disconnect the USB and power cables from the OB-1

## Notes on using Kirill's OB-1 Manager

- Settings and modes
  - Unless you want to manually specify all the settings and modes of the microfluidic controller, use a pre-saved settings file in the txt format
  - There are templates for experiments in Microfluidics_trial/templates:
    - ONE_CHAN_SETTINGS.txt -simple experiment with one channel (Channel 1)
    - TWO_CHAN_SETTINGS.txt -experiment with two channels
    - VALVE_SET_SETTINGS.txt -experiment with one channel and valve, allowing you to switch between valve inlets manually
    - VALVE_PWM_SETTINGS.txt -experiment with one channel and valve, allowing you to switch
    - RECIRC_AND_VALVE_SETTINGS.txt -experiment with one channel, one valve and one recirculator. Change the recirculator mode from 'manual' to 'scripted' to make the recirculatotr follow a program pre-specified in a .csv file (template provided)

  - **Do not change the order in which the parameters are specified, just the values!**
- Calibration
  - The script will ask you if you want to use a default calibration, load a saved file or do a new one
  - Defaults are not to be trusted
  - If you pick a saved calibration, you will be offered to check it -do a new calibration if the errors are too large
    - In any case, it's a good idea to recalibrate every month
  - Every new calibration will be saved for potential future use

- Logging
  - With every run, logs for the OB-1 and for the valve (if in use) will be kept
    - For the valve additionally, all errors will be logged in a txt file
  - Plots of system performance of the time will also be produced as pngs
  - If you've finished an experiment but aren't turning the OB-1 off (e.g. running it with ethanol), pause logging using the **pause_log** command to avoid saving unnecessary data
    - If you call it too early by mistake, you can reverse this with **resume_log**
  
- Commands (to be typed into the terminal):
  - At any given time, all commands you CAN give in your particular situation will be listed to you
  - Command list:
    - OB-1/flow/pressure control
        - **stop** - stop running the experiment and cuts off all pressure
            - Note: when you press stop, the script assumes you want to look at the liveplot window and does not finish as long as it is open
        - **set_ref_flow** - set the reference flow in a given channel
            - Note: if the channel had been supplied with constant pressure, this will change its mode
        - **set_const_press** - supply a constant pressure to a given channel
            - Note: if the channel had been tracking a reference flow, this will change its mode
        - **set_gains** - specify the new PID gains for a given channel's flow controller
        - **live_plot** - open a liveplot window if it was closed
        - **change_medium** - reset the medium-volume-in-source tracker when changing the source Falcon tube
        - **purge_integ** - purge (set to zero) the flow error integral for a given channel's PID flow controller
    - Valve
      - **set_valve_inlet** - set the valve to a given inlet
        - Note: only available in set mode
      - **set_input_conc** -set the input comound concentration to be achieved by PWM
        - Note: only available in pwm mode
      - **launch_valve_script** - launch the valve script
        - Note: only available in set_scripted and pwm_scripted modes
        - Recirculator
      - **set_recirc_state** - set the recicrulator to a given state (A or B)
        - Note: only available in manual mode
      - **launch_recirc_script** - launch the valve script
        - Note: only available in scripted mode
    - Logging
      - **pause_log** - pause logging of all data
      - **resume_log** - resume logging of all data
      
  - Valve scripts
    - You can program the valve with a script in the csv format (templates in Microfluidics_trial/templates)You choose the script once when you launch the OB-1 Manager, and cannot change it unless you relaunch
    - To give you time to set things up, **the script starts running only when you send the launch_script command**
    - If the valve is running in the set_scripted or pwm_scripted modes, the script gives will the valve timed commands (analogically to set_valve)inlet and set_input_conc) as if it was running in set or pwm modes
    - **The times specified are since you enter the launch_script command, NOT since you start the OB-1!**
  
## Troubleshooting
- If you see liquid flowing in the wrong direction, it is likely that you have a leak between inlet tube and chip input. You may want to check the filter that easily starts leaking
- If you see a weird and very blurry image, it is likely that this is caused by a water droplet around the inlet our outlet needle. In this case, first remove the holder from the stage, clean the chip, carefully push the needles further in.
  - If you see a high pressure but a flow rate that is too low, then:
      - Either some part in the circuit is clogged, most likely the resistance element or the filter
      - Or some part before the sensor is leaking, possibly also the air supply.
- If valve addition returns an error:
  - Open NIMAX and check the connected devices
  - Check the device name with 
  ```…ASLR[some number X]…``` in it (e.g. ASLR3)
  - In one_stop_shop.py, check that the same number X is found after 'ASLR' in the line:
   ```valve_error_msg = MUX_DRI_Initialization("ASRL[some number]::INSTR".encode('ascii'), byref(valve_instrid))```
- If mid-experiment communication with the OB-1 and/or sensors crashes with error -301708
   - ***Tell Kirill!*** This means we need to get a new USB cable
        - Because that's a USB port error we've been seeing, but all the three software fixes suggested online and by Gemini have been implemented, which means that hardware should be to blame
   - To relaunch microfludics (***DO follow this instruction!*** Or else you will just get another error -301706):
     1. Close PyCharm
     2. Turn off the OB-1 and disconnect *all* cables (power, all USB connections, sensors…)
     3. Wait at least 10 seconds
     4. Reconnect the cables and turn everything back one
- If during initialisation valve or recirculator initialisation and/or homing give off error -1073807298
  1. Open NI-VISA Interactive Control from the Windows Start menu
  2. Check if it sees the 'ASRL3' and 'ASRL8' devices -alias the valve and the recirculator respectively as of 6 April 2026
     - If it does and there are still errors, that's unprecedented, so tell Kirill!
     - If a device is missing, try to fix this:
       1. Yank out the devices' USB cables
       2. Flick the devices' toggles to 'O' and unplug them from power
       3. Reboot the PC
       4. Replug, turn on and reconnect the devices
       5. Go to NI-VISA and check again if it sees three 'ASRL' devices in total ('ASRL5' is irrelevant, the other two should be the valve and the recirculator)
       The formerly broken device may reappear under a different ASRL number than before -in this case, change the first few lines in one_stop_shop.py to match that and GIT PUSHso that change is saved for all
          - If the above fails, repeat all the steps above gain -but also replace the USB cables of the devices when they are turned off
          - If even that fails,that's unprecedented, so ***tell Kirill!***