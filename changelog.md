# Changelog
A log of requested and implemented changes to the code and/or the microfluidics setup.

## TODO:
Short-term
- Code a simple emulator, so that I don't have to book the microscope EVERY time!!
  - (Just a Python file with functions called the same as the ones in the SDK)
- Copy short-term memory into a dictionary, which is then live-plotted => wouldn't need 
to lock the memory for so long
- Fix the valve update issue

Longer-term
- Allow to switch between valve modes online
- Calibrate flow sensors using the ESI GUI

Very long-term
- Add interfacing with the Ubuntu microscope computer via a web socket using extra input and output queues. Idris to provide example code
  - Receiving commands, reporting that the OB-1 is running, giving latest readings (instead of the live plot)
  - To load calibration upon commands from the microscope computer (?)
    - May be hard due to the ESI API being bad

## Release notes 7 Apr 2025

- Very-very alpha version of valve control added!
  - ISSUE: Vulnerable to differences in source-to-valve tubing resistance between the inlets. 
    - SOLUTION: 1) Make sure to use new, fresh tubing every time. 2) Use a good, small-diameter
    resistor: common high resistance after the valve means differences in tubing before the 
    valve are not that relevant.
    - POTENTIAL LONG-TERM SOLUTION: Make integral controller memories different for each valve?
    But will require syncing with the OB-1, which we do not now...
  - ISSUE: takes time to update PWM concentrations; setting valve inlets sometimes does not work
    - SOLUTION: will just need to debug this implementation...
