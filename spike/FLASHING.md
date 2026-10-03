# Flashing the spike image (user action, needs explicit approval)

Board: ONE WeAct CH584F (label it "spike"). Its current firmware is replaced.

1. WCHISPTool v4.0: Chip Series CH58x, Chip Model CH584, Dnld Port USB.
2. Untick "Automatic Download When Device Connect".
3. Object File1 = spike/out/spike_full_v1_plus_v2B.hex (ticked). Object File2-4 and DataFlash File empty/unticked.
4. Tick "Clear DataFlash" (mandatory: wipes old mesh data and the OTA image flag at DataFlash 0x7000).
5. Hold BOOT, plug USB, release BOOT, click Search, then Download. Expect "Succeed!" and Succ:1.
6. After the restart the LED blinks ONCE (version 1 is running). Note the result in RESULTS.md.

Version 2 sits in the update buffer (0x27000) and is only installed by the S5 test in TESTS.md.
To return to plain version 1 later, flash spike/out/spike_full_v1.hex the same way.
