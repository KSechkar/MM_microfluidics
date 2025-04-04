# Changelog
A log of requested and implemented changes to the code and/or the microfluidics setup.

## TODO:
Changes to make in the code:
- Add the 'urgently cut pressure off' command (functionally, just set_press to 0 mbar)
- Add interfacing with the Ubuntu microscope computer via a web socket using extra input and output queues. Idris to provide example code
  - Recieving commands, reporting that the OB-1 is running, giving latest readings (instead of the live plot)
  - To load calibration upon commands from the microscope computer (?)
    - May be hard due to the ESI API being bad
- Add distirbution valve connection for chemical input control
  - HOW? Focus only on PWM if short on time
    - ! Valve running in a separate multiprocessing thread
      - ! OR same if our dt_check is usually < 0.5s (LOOK WHAT IT IS!!!)
    - ! Swap user_cmd_queue for user_OB1_cmd_queue, add user_valve_cmd_queue
    - ! PWM, manual switch & timed switch modes - CHOSEN AT TIME OF START!!
    - ! PWM commands calculated whenever new input set
    - ! No need to do steps, use CONTINUOUS WAIT TIMES BETWEEN SWITCHING!
    - ! valve channel AND PWM setpoint + params still recorded in the common stmemo
      - ! But plotted only if applicable
    - ! Copy valve state into OB-1 states to allow reading without locking valve action


Validate during the next deployment:
- How accurate our 'medium left' estimates are - related to whether the sensors are actually well-calibrated

To perform using the ESI GUI:
- Calibrate flow sensors

## Latest version: 25 Mar 2025

- Multichannel support added in the new script _multichannel_experiment.py_

