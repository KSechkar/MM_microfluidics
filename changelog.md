# Changelog
A log of requested and implemented changes to the code and/or the microfluidics setup.

## TODO:

Long-term
- Calibrate flow sensors using the ESI GUI
- Add interfacing with the Ubuntu microscope computer via a web socket using extra input and output queues. Idris to provide example code
  - Receiving commands, reporting that the OB-1 is running, giving latest readings (instead of the live plot)
  - To load calibration upon commands from the microscope computer (?)
    - May be hard due to the ESI API being bad

## Release notes 23 Dec 2025 (intermediate)
- !!!! To do on the actual New Hope controller PC: edit all templates, see what ASRL the recirculator really is, turn off emulation
- Added recirculator valve control in scipted and manual modes
- Improved log plotting

## Release notes 14 Jun 2025

- Added an emulator script for development without connected to a real OB-1 on a PC with NIMAX installed
  - Set the 'EMULATING' environment variable to 'True' to use it instead of a real OB-1
- Added optional valve controls - both with set valve inlets and PWM input concentration modulation with the valve
  - Online manual control with 'set' and 'pwm' modes respectively
  - Scripted control with 'set_scripted' and 'pwm_scripted' modes respectively