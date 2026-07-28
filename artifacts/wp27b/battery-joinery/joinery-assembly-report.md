# WP2.7 joinery assembly report

- system: joinery-bootstrap-v0 (L1+L2+L4, bootstrap stand-in blocks)
- vintage: 2026-07-26.1; n_paths 1024; months 120; seed 20260727
- criterion_bearing: True
- battery verdict (unfiltered): PASS (0 enforce failures of 5)

## Unfiltered ensemble

### Waypoint tolerance
- all decades within tolerance: True (1024 of 1024)
- floor-clamped cells: 26004

### Reconciliation adjustment distribution (mean |x-z| per decade, working space)
- policy_rate (additive): p50 2.86737, p90 5.10771, max 14.91989, flagged decades 1023
- cpi (proportional_via_log): p50 0.16745, p90 0.56993, max 1.88570, flagged decades 839
- equity_mkt (additive_log_returns): p50 0.01110, p90 0.01838, max 0.04282, flagged decades 120
- ig_spread (additive_band): p50 0.02425, p90 0.08216, max 0.27783, flagged decades 0

### Support diagnostics
- extrapolation quantile: p99 of historical self-distances
- extrapolation share: mean 0.8799, max 1.0000
- decades flagged off-support (share > 0.25): 1009
- regime-mix TV distance: mean 0.3357
- pooled regime mix: EXP 0.419, SLOW 0.093, REC 0.269, CRI 0.079, STAG 0.037, REF 0.104
- sampler stratum fallbacks: {}

### Acceptance filter
- enabled: False; metrics ['skew', 'excess_kurtosis', 'hill_tail_index_5pct'] on ['equity_mkt', 'smb', 'hml', 'mom']
- rejected 0 decade(s) (cap 10%)

## Filtered ensemble

### Waypoint tolerance
- all decades within tolerance: True (1024 of 1024)
- floor-clamped cells: 26427

### Reconciliation adjustment distribution (mean |x-z| per decade, working space)
- policy_rate (additive): p50 2.87407, p90 4.97793, max 14.91989, flagged decades 1023
- cpi (proportional_via_log): p50 0.16534, p90 0.55611, max 1.88570, flagged decades 842
- equity_mkt (additive_log_returns): p50 0.01118, p90 0.01873, max 0.04316, flagged decades 125
- ig_spread (additive_band): p50 0.02416, p90 0.08803, max 0.27783, flagged decades 0

### Support diagnostics
- extrapolation quantile: p99 of historical self-distances
- extrapolation share: mean 0.8836, max 1.0000
- decades flagged off-support (share > 0.25): 1009
- regime-mix TV distance: mean 0.3310
- pooled regime mix: EXP 0.425, SLOW 0.093, REC 0.263, CRI 0.083, STAG 0.037, REF 0.100
- sampler stratum fallbacks: {}

### Acceptance filter
- enabled: True; metrics ['skew', 'excess_kurtosis', 'hill_tail_index_5pct'] on ['equity_mkt', 'smb', 'hml', 'mom']
- rejected 102 decade(s) (cap 10%)
  - decade 877 (seed 27205690, score 3.056) -> replacement index 1024 (seed 28369783, score 1.727)
  - decade 710 (seed 25883217, score 2.953) -> replacement index 1025 (seed 28377702, score 1.630)
  - decade 498 (seed 24204389, score 2.942) -> replacement index 1026 (seed 28385621, score 1.685)
  - decade 334 (seed 22905673, score 2.926) -> replacement index 1027 (seed 28393540, score 1.995)
  - decade 602 (seed 25027965, score 2.885) -> replacement index 1028 (seed 28401459, score 1.216)
  - decade 936 (seed 27672911, score 2.850) -> replacement index 1029 (seed 28409378, score 1.272)
  - decade 469 (seed 23974738, score 2.670) -> replacement index 1030 (seed 28417297, score 1.672)
  - decade 572 (seed 24790395, score 2.614) -> replacement index 1031 (seed 28425216, score 2.161)
  - decade 80 (seed 20894247, score 2.533) -> replacement index 1032 (seed 28433135, score 1.928)
  - decade 173 (seed 21630714, score 2.532) -> replacement index 1033 (seed 28441054, score 1.678)
  - decade 369 (seed 23182838, score 2.516) -> replacement index 1034 (seed 28448973, score 1.854)
  - decade 995 (seed 28140132, score 2.507) -> replacement index 1035 (seed 28456892, score 1.229)
  - decade 745 (seed 26160382, score 2.504) -> replacement index 1036 (seed 28464811, score 1.143)
  - decade 345 (seed 22992782, score 2.441) -> replacement index 1037 (seed 28472730, score 1.590)
  - decade 58 (seed 20720029, score 2.423) -> replacement index 1038 (seed 28480649, score 3.189)
  - decade 768 (seed 26342519, score 2.422) -> replacement index 1039 (seed 28488568, score 1.833)
  - decade 740 (seed 26120787, score 2.412) -> replacement index 1040 (seed 28496487, score 1.404)
  - decade 40 (seed 20577487, score 2.407) -> replacement index 1041 (seed 28504406, score 1.169)
  - decade 997 (seed 28155970, score 2.402) -> replacement index 1042 (seed 28512325, score 1.101)
  - decade 436 (seed 23713411, score 2.396) -> replacement index 1043 (seed 28520244, score 1.834)
  - decade 935 (seed 27664992, score 2.371) -> replacement index 1044 (seed 28528163, score 1.370)
  - decade 739 (seed 26112868, score 2.370) -> replacement index 1045 (seed 28536082, score 2.338)
  - decade 386 (seed 23317461, score 2.361) -> replacement index 1046 (seed 28544001, score 1.194)
  - decade 181 (seed 21694066, score 2.343) -> replacement index 1047 (seed 28551920, score 1.530)
  - decade 537 (seed 24513230, score 2.335) -> replacement index 1048 (seed 28559839, score 1.719)
  - decade 815 (seed 26714712, score 2.319) -> replacement index 1049 (seed 28567758, score 1.393)
  - decade 931 (seed 27633316, score 2.319) -> replacement index 1050 (seed 28575677, score 0.943)
  - decade 708 (seed 25867379, score 2.316) -> replacement index 1051 (seed 28583596, score 1.365)
  - decade 827 (seed 26809740, score 2.316) -> replacement index 1052 (seed 28591515, score 1.631)
  - decade 820 (seed 26754307, score 2.306) -> replacement index 1053 (seed 28599434, score 2.202)
  - decade 244 (seed 22192963, score 2.304) -> replacement index 1054 (seed 28607353, score 2.266)
  - decade 331 (seed 22881916, score 2.294) -> replacement index 1055 (seed 28615272, score 1.222)
  - decade 12 (seed 20355755, score 2.293) -> replacement index 1056 (seed 28623191, score 1.445)
  - decade 100 (seed 21052627, score 2.291) -> replacement index 1057 (seed 28631110, score 1.640)
  - decade 283 (seed 22501804, score 2.282) -> replacement index 1058 (seed 28639029, score 1.477)
  - decade 394 (seed 23380813, score 2.275) -> replacement index 1059 (seed 28646948, score 1.435)
  - decade 1010 (seed 28258917, score 2.262) -> replacement index 1060 (seed 28654867, score 1.921)
  - decade 1005 (seed 28219322, score 2.256) -> replacement index 1061 (seed 28662786, score 2.315)
  - decade 15 (seed 20379512, score 2.256) -> replacement index 1062 (seed 28670705, score 1.714)
  - decade 235 (seed 22121692, score 2.252) -> replacement index 1063 (seed 28678624, score 2.561)
  - decade 665 (seed 25526862, score 2.247) -> replacement index 1064 (seed 28686543, score 0.906)
  - decade 467 (seed 23958900, score 2.241) -> replacement index 1065 (seed 28694462, score 1.489)
  - decade 310 (seed 22715617, score 2.227) -> replacement index 1066 (seed 28702381, score 1.034)
  - decade 431 (seed 23673816, score 2.227) -> replacement index 1067 (seed 28710300, score 1.429)
  - decade 859 (seed 27063148, score 2.223) -> replacement index 1068 (seed 28718219, score 1.244)
  - decade 204 (seed 21876203, score 2.217) -> replacement index 1069 (seed 28726138, score 1.474)
  - decade 754 (seed 26231653, score 2.216) -> replacement index 1070 (seed 28734057, score 0.971)
  - decade 847 (seed 26968120, score 2.204) -> replacement index 1071 (seed 28741976, score 2.627)
  - decade 251 (seed 22248396, score 2.200) -> replacement index 1072 (seed 28749895, score 1.168)
  - decade 349 (seed 23024458, score 2.198) -> replacement index 1073 (seed 28757814, score 0.997)
  - decade 319 (seed 22786888, score 2.195) -> replacement index 1074 (seed 28765733, score 1.673)
  - decade 878 (seed 27213609, score 2.194) -> replacement index 1075 (seed 28773652, score 1.702)
  - decade 589 (seed 24925018, score 2.190) -> replacement index 1076 (seed 28781571, score 1.567)
  - decade 795 (seed 26556332, score 2.190) -> replacement index 1077 (seed 28789490, score 1.231)
  - decade 292 (seed 22573075, score 2.187) -> replacement index 1078 (seed 28797409, score 1.170)
  - decade 311 (seed 22723536, score 2.173) -> replacement index 1079 (seed 28805328, score 1.124)
  - decade 106 (seed 21100141, score 2.172) -> replacement index 1080 (seed 28813247, score 1.444)
  - decade 265 (seed 22359262, score 2.170) -> replacement index 1081 (seed 28821166, score 1.565)
  - decade 759 (seed 26271248, score 2.162) -> replacement index 1082 (seed 28829085, score 1.278)
  - decade 208 (seed 21907879, score 2.160) -> replacement index 1083 (seed 28837004, score 1.893)
  - decade 722 (seed 25978245, score 2.158) -> replacement index 1084 (seed 28844923, score 1.415)
  - decade 909 (seed 27459098, score 2.157) -> replacement index 1085 (seed 28852842, score 1.593)
  - decade 622 (seed 25186345, score 2.156) -> replacement index 1086 (seed 28860761, score 1.237)
  - decade 223 (seed 22026664, score 2.154) -> replacement index 1087 (seed 28868680, score 1.678)
  - decade 6 (seed 20308241, score 2.154) -> replacement index 1088 (seed 28876599, score 1.493)
  - decade 105 (seed 21092222, score 2.152) -> replacement index 1089 (seed 28884518, score 2.574)
  - decade 443 (seed 23768844, score 2.147) -> replacement index 1090 (seed 28892437, score 1.789)
  - decade 700 (seed 25804027, score 2.142) -> replacement index 1091 (seed 28900356, score 2.664)
  - decade 992 (seed 28116375, score 2.141) -> replacement index 1092 (seed 28908275, score 1.913)
  - decade 617 (seed 25146750, score 2.136) -> replacement index 1093 (seed 28916194, score 1.247)
  - decade 147 (seed 21424820, score 2.135) -> replacement index 1094 (seed 28924113, score 1.421)
  - decade 889 (seed 27300718, score 2.121) -> replacement index 1095 (seed 28932032, score 1.090)
  - decade 673 (seed 25590214, score 2.119) -> replacement index 1096 (seed 28939951, score 1.752)
  - decade 194 (seed 21797013, score 2.118) -> replacement index 1097 (seed 28947870, score 0.992)
  - decade 810 (seed 26675117, score 2.117) -> replacement index 1098 (seed 28955789, score 1.076)
  - decade 196 (seed 21812851, score 2.109) -> replacement index 1099 (seed 28963708, score 1.045)
  - decade 377 (seed 23246190, score 2.105) -> replacement index 1100 (seed 28971627, score 1.173)
  - decade 300 (seed 22636427, score 2.104) -> replacement index 1101 (seed 28979546, score 1.383)
  - decade 51 (seed 20664596, score 2.099) -> replacement index 1102 (seed 28987465, score 1.953)
  - decade 45 (seed 20617082, score 2.099) -> replacement index 1103 (seed 28995384, score 2.433)
  - decade 475 (seed 24022252, score 2.098) -> replacement index 1104 (seed 29003303, score 2.428)
  - decade 844 (seed 26944363, score 2.097) -> replacement index 1105 (seed 29011222, score 1.058)
  - decade 411 (seed 23515436, score 2.096) -> replacement index 1106 (seed 29019141, score 1.540)
  - decade 770 (seed 26358357, score 2.091) -> replacement index 1107 (seed 29027060, score 1.107)
  - decade 306 (seed 22683941, score 2.088) -> replacement index 1108 (seed 29034979, score 1.088)
  - decade 350 (seed 23032377, score 2.080) -> replacement index 1109 (seed 29042898, score 1.358)
  - decade 209 (seed 21915798, score 2.074) -> replacement index 1110 (seed 29050817, score 2.194)
  - decade 427 (seed 23642140, score 2.072) -> replacement index 1111 (seed 29058736, score 1.521)
  - decade 199 (seed 21836608, score 2.065) -> replacement index 1112 (seed 29066655, score 0.981)
  - decade 636 (seed 25297211, score 2.065) -> replacement index 1113 (seed 29074574, score 2.140)
  - decade 809 (seed 26667198, score 2.064) -> replacement index 1114 (seed 29082493, score 1.398)
  - decade 433 (seed 23689654, score 2.063) -> replacement index 1115 (seed 29090412, score 1.833)
  - decade 943 (seed 27728344, score 2.062) -> replacement index 1116 (seed 29098331, score 1.109)
  - decade 1014 (seed 28290593, score 2.059) -> replacement index 1117 (seed 29106250, score 0.801)
  - decade 814 (seed 26706793, score 2.058) -> replacement index 1118 (seed 29114169, score 1.434)
  - decade 851 (seed 26999796, score 2.058) -> replacement index 1119 (seed 29122088, score 2.054)
  - decade 846 (seed 26960201, score 2.057) -> replacement index 1120 (seed 29130007, score 1.449)
  - decade 11 (seed 20347836, score 2.057) -> replacement index 1121 (seed 29137926, score 1.429)
  - decade 298 (seed 22620589, score 2.057) -> replacement index 1122 (seed 29145845, score 1.288)
  - decade 412 (seed 23523355, score 2.057) -> replacement index 1123 (seed 29153764, score 1.427)
  - decade 905 (seed 27427422, score 2.054) -> replacement index 1124 (seed 29161683, score 2.197)
  - decade 522 (seed 24394445, score 2.052) -> replacement index 1125 (seed 29169602, score 1.738)
