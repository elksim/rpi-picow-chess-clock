# Chess Clock

A simple chess clock implemented using a microcontroller and a potentiometer for input.

## TODOs

- [ ] message when time runs out
- [ ] Rolling average for potentiometer readings
- [ ] change selecting time from simply linear - we actually want to bias towards lower options, and perhaps implement snapping for higher numbers.
- [ ] Fix the weird display issues
  - sometimes text gets written to the wrong part of the screen. Probably due to editing the text_buffer while update_display is reading from it.
  - blinking input should immediately move when we change selection - might just be able to deinit blink timers and call update_display before we move

## TO-probablynot-DO

- [ ] could change update_display to only write characters that have changed instead of just writing the entirety of text_buffer every time?
- [ ] sounds, animations..
