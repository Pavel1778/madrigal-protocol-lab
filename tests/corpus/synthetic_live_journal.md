# Synthetic stand journal

One line per transaction: `timestamp | action | parameter | result`.
The timestamp is the relay's observation time of the request segment,
so it matches the capture exactly.

```
1791568880.875 | read | flow_rate | 1824
1791568880.996 | read | setpoint | 1861
1791568881.116 | read | calibration | 1898
1791568881.236 | set | limit | applied 100
1791568881.357 | set | deadband | applied 25
1791568881.477 | set | ramp | applied 7
1791568881.597 | measure | probe_x | 4 samples
1791568881.718 | measure | probe_y | 5 samples
1791568881.838 | measure | probe_x | 4 samples
1791568881.958 | measure | probe_y | 5 samples
1791568882.079 | measure | probe_x | 4 samples
```
