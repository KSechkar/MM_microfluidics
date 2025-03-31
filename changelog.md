# Changelog
A log of requested and implemented changes to the code and/or the microfluidics setup.

## TODO:
Changes to make in the code:
- Add the 'urgently cut pressure off' command (functionally, just set_press to 0 mbar)
- Add interfacing with the Ubuntu microscope computer via a web socket using extra input and output queues. Idris to provide example code
  - Recieving commands, reporting that the OB-1 is running, giving latest readings (instead of the live plot)
  - To load calibration upon commands from the microscope computer (?)
    - May be hard due to the ESI API being bad
- Add MUX distirubitor connection for chemical input control


Validate during the next deployment:
- How accurate our 'medium left' estimates are - related to whether the sensors are actually well-calibrated

To perform using the ESI GUI:
- Calibrate flow sensors

## Latest version: 25 Mar 2025

- Multichannel support added in the new script _multichannel_experiment.py_