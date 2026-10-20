; ---------------------------------------------------------------------------
; volcano_monitor - shared safety thresholds
;
; This file is the single source of truth for the warning levels.  The values
; are used by:
;   * asm/volcano_report.asm   (the assembly program, via %include)
;   * tools/gen_vectors.py     (the Logisim test-vector generator)
;   * circuit/volcano_monitor.circ (the Logisim circuit constants)
;
; Levels:
;   NORMAL  value <  WATCH
;   WATCH   WATCH <= value < DANGER
;   DANGER  value >= DANGER
;
; Sensor              unit                WATCH   DANGER
;   VIB  ground vibration index   (0-255)      40      70
;   TMP  temperature              (degC)       60      85
;   GAS  gas concentration        (ppm)       100     180
;   ACT  volcanic activity level  (0-255)      50      80
; ---------------------------------------------------------------------------

%ifndef THRESHOLDS_INC
%define THRESHOLDS_INC

; Sensor count
%define SENSOR_COUNT      4

; Watch thresholds, in sensor order VIB, TMP, GAS, ACT
%define T_VIB_WATCH       40
%define T_TMP_WATCH       60
%define T_GAS_WATCH       100
%define T_ACT_WATCH       50

; Danger thresholds, in sensor order VIB, TMP, GAS, ACT
%define T_VIB_DANGER      70
%define T_TMP_DANGER      85
%define T_GAS_DANGER      180
%define T_ACT_DANGER      80

; The emergency alarm is raised when this many sensors read DANGER
%define EMERGENCY_COUNT   2

; Human readable sensor names, used in the report
%define SENSOR_NAME_0     "Ground vibration"
%define SENSOR_NAME_1     "Temperature"
%define SENSOR_NAME_2     "Gas concentration"
%define SENSOR_NAME_3     "Volcanic activity"

%endif ; THRESHOLDS_INC
