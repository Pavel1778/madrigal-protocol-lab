# Action journal

One line per transaction: `timestamp | action | parameter | result`.
The timestamp is the capture time of the request packet in epoch seconds,
so it can be matched against the captures.

```
1700000000.004 | read | temperature | 1595
1700000000.006 | read | humidity | 2938
1700000000.008 | read | voltage | 3826
1700000000.010 | read | temperature | 397
1700000000.012 | read | humidity | 1757
1700000000.014 | read | voltage | 1816
1700000000.016 | read | temperature | 2363
1700000000.018 | read | humidity | 3976
1700000000.020 | read | voltage | 1739
1700000000.022 | read | temperature | 2695
1700000000.024 | read | humidity | 3587
1700000000.026 | read | voltage | 576
1700000000.028 | read | temperature | 2090
1700000000.030 | read | humidity | 1583
1700000000.032 | read | voltage | 1319
1700000000.034 | read | temperature | 727
1700000000.036 | read | humidity | 3647
1700000000.038 | read | voltage | 3002
1700000000.040 | read | temperature | 1569
1700000000.042 | read | humidity | 3864
1700000000.044 | read | voltage | 2670
1700000000.046 | read | temperature | 1956
1700000000.048 | read | humidity | 3308
1700000000.050 | read | voltage | 3459
1700000000.052 | read | temperature | 1706
1700000000.054 | read | humidity | 515
1700000000.056 | read | voltage | 3523
1700000000.058 | read | temperature | 3831
1700000000.060 | read | humidity | 2492
1700000000.062 | read | voltage | 1734
1700000000.064 | read | temperature | 907
1700000000.066 | read | humidity | 2691
1700000000.068 | read | voltage | 2189
1700000000.070 | read | temperature | 3232
1700000000.072 | read | humidity | 3107
1700000000.074 | read | voltage | 1876
1700000000.076 | read | temperature | 3464
1700000000.078 | read | humidity | 629
1700000000.080 | read | voltage | 3314
1700000000.082 | read | temperature | 3427
1700000000.084 | read | humidity | 53
1700000000.086 | read | voltage | 3801
1700000000.088 | read | temperature | 1775
1700000000.090 | read | humidity | 775
1700000000.092 | read | voltage | 2830
1700000000.094 | read | temperature | 179
1700000000.096 | read | humidity | 3038
1700000000.098 | read | voltage | 2945
1700000000.100 | read | temperature | 77
1700000000.102 | read | humidity | 2146
1700000000.104 | read | voltage | 1256
1700000000.106 | read | temperature | 283
1700000000.108 | read | humidity | 3537
1700000000.110 | read | voltage | 1481
1700000000.112 | read | temperature | 2275
1700000000.114 | read | humidity | 538
1700000000.116 | read | voltage | 1235
1700000000.118 | read | temperature | 3315
1700000000.120 | read | humidity | 2971
1700000000.122 | read | voltage | 3892
1700000001.129 | write | gain | applied 85
1700000001.131 | write | threshold | applied 255
1700000001.133 | write | mode | applied 159
1700000001.135 | write | gain | applied 92
1700000001.137 | write | threshold | applied 3
1700000001.139 | write | mode | applied 43
1700000001.141 | write | gain | applied 33
1700000001.143 | write | threshold | applied 16
1700000001.145 | write | mode | applied 177
1700000001.147 | write | gain | applied 226
1700000001.149 | write | threshold | applied 60
1700000001.151 | write | mode | applied 235
1700000001.153 | write | gain | applied 71
1700000001.155 | write | threshold | applied 91
1700000001.157 | write | mode | applied 102
1700000001.159 | write | gain | applied 228
1700000001.161 | write | threshold | applied 71
1700000001.163 | write | mode | applied 41
1700000001.165 | write | gain | applied 76
1700000001.167 | write | threshold | applied 159
1700000001.169 | write | mode | applied 172
1700000001.171 | write | gain | applied 192
1700000001.173 | write | threshold | applied 34
1700000001.175 | write | mode | applied 30
1700000001.177 | write | gain | applied 179
1700000001.179 | write | threshold | applied 237
1700000001.181 | write | mode | applied 29
1700000001.183 | write | gain | applied 98
1700000001.185 | write | threshold | applied 142
1700000001.187 | write | mode | applied 167
1700000001.189 | write | gain | applied 46
1700000001.191 | write | threshold | applied 143
1700000001.193 | write | mode | applied 78
1700000001.195 | write | gain | applied 128
1700000001.197 | write | threshold | applied 238
1700000001.199 | write | mode | applied 104
1700000001.201 | write | gain | applied 217
1700000001.203 | write | threshold | applied 57
1700000001.205 | write | mode | applied 163
1700000001.207 | write | gain | applied 125
1700000001.209 | write | threshold | applied 48
1700000001.211 | write | mode | applied 143
1700000001.213 | write | gain | applied 90
1700000001.215 | write | threshold | applied 6
1700000001.217 | write | mode | applied 7
1700000001.219 | write | gain | applied 202
1700000001.221 | write | threshold | applied 234
1700000001.223 | write | mode | applied 22
1700000001.225 | write | gain | applied 172
1700000001.227 | write | threshold | applied 122
1700000001.229 | write | mode | applied 139
1700000001.231 | write | gain | applied 241
1700000001.233 | write | threshold | applied 100
1700000001.235 | write | mode | applied 161
1700000001.237 | write | gain | applied 171
1700000001.239 | write | threshold | applied 9
1700000001.241 | write | mode | applied 68
1700000001.243 | write | gain | applied 147
1700000001.245 | write | threshold | applied 176
1700000001.247 | write | mode | applied 186
1700000002.254 | measure | channel_a | 52 samples
1700000002.256 | measure | channel_b | 10 samples
1700000002.258 | measure | probe | 30 samples
1700000002.260 | measure | channel_a | 31 samples
1700000002.262 | measure | channel_b | 33 samples
1700000002.264 | measure | probe | 63 samples
1700000002.266 | measure | channel_a | 22 samples
1700000002.268 | measure | channel_b | 39 samples
1700000002.270 | measure | probe | 30 samples
1700000002.272 | measure | channel_a | 23 samples
1700000002.274 | measure | channel_b | 31 samples
1700000002.276 | measure | probe | 54 samples
1700000002.278 | measure | channel_a | 24 samples
1700000002.280 | measure | channel_b | 7 samples
1700000002.282 | measure | probe | 9 samples
1700000002.284 | measure | channel_a | 56 samples
1700000002.286 | measure | channel_b | 36 samples
1700000002.288 | measure | probe | 4 samples
1700000002.290 | measure | channel_a | 48 samples
1700000002.292 | measure | channel_b | 26 samples
1700086400.004 | read | temperature | 7254
1700086400.006 | read | sample_rate | 7937
1700086400.008 | read | temperature | 7450
1700086400.010 | read | sample_rate | 5718
1700086400.012 | read | temperature | 5701
1700086400.014 | read | sample_rate | 7356
1700086400.016 | read | temperature | 4556
1700086400.018 | read | sample_rate | 7600
1700086400.020 | read | temperature | 7722
1700086400.022 | read | sample_rate | 7792
1700086400.024 | read | temperature | 4391
1700086400.026 | read | sample_rate | 6766
1700086400.028 | read | temperature | 5747
1700086400.030 | read | sample_rate | 6041
1700086400.032 | read | temperature | 8145
1700086400.034 | read | sample_rate | 5670
1700086400.036 | read | temperature | 7391
1700086400.038 | read | sample_rate | 6772
1700086400.040 | read | temperature | 7996
1700086400.042 | read | sample_rate | 5147
1700086401.049 | write | humidity | applied 2743
1700086401.051 | write | voltage | applied 2904
1700086401.053 | write | humidity | applied 3929
1700086401.055 | write | voltage | applied 3899
1700086401.057 | write | humidity | applied 3690
1700086401.059 | write | voltage | applied 1150
1700086401.061 | write | humidity | applied 3139
1700086401.063 | write | voltage | applied 2018
1700086401.065 | write | humidity | applied 2041
1700086401.067 | write | voltage | applied 2830
1700086401.069 | write | humidity | applied 2931
1700086401.071 | write | voltage | applied 3016
1700086401.073 | write | humidity | applied 2109
1700086401.075 | write | voltage | applied 1187
1700086401.077 | write | humidity | applied 1725
1700086401.079 | write | voltage | applied 3567
1700086401.081 | write | humidity | applied 1409
1700086401.083 | write | voltage | applied 1158
1700086401.085 | write | humidity | applied 2556
1700086401.087 | write | voltage | applied 2067
1700172800.004 | read | temperature | 259
1700172800.006 | read | humidity | 1234
1700172800.008 | write | gain | applied 200
1700172800.011 | read | voltage | 777
1700172800.013 | measure | channel_a | 8 samples
```
