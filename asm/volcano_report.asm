; ===========================================================================
;  Volcano Monitoring System - offline analysis and warning report
;  Target : x86-64 Linux, NASM syntax
;           nasm -f elf64 volcano_report.asm -o volcano_report.o
;           gcc -no-pie volcano_report.o -o volcano_report
;
;  What it does
;  ------------
;  1. Reads a recorded sensor file (CSV): vibration, temp_c, gas_ppm, activity
;  2. Computes the minimum, the maximum and the average of every sensor
;  3. Counts how many samples were on WATCH and how many were on DANGER
;  4. Derives the overall severity and the emergency-alarm condition
;  5. Writes the final warning report to stdout and to out/volcano_report.txt
;
;  The thresholds come from thresholds.inc - the same values the Logisim
;  circuit uses - so the hardware and the software always agree.
; ===========================================================================

%include "thresholds.inc"

%define SYS_read   0
%define SYS_write  1
%define SYS_open   2
%define SYS_close  3
%define SYS_exit   60

%define O_RDONLY   0

%define FILEBUF_SIZE   65536
%define OUTBUF_SIZE    16384

; ---------------------------------------------------------------------------
;  Section .rodata - the literal text of the report
; ---------------------------------------------------------------------------
section .rodata

title_line:      db "VOLCANO MONITORING SYSTEM - FINAL WARNING REPORT", 10, 0
rule_line:       db "--------------------------------------------------------------", 10, 0
txt_samples:     db "Recorded samples analysed : ", 0
txt_newline:     db 10, 0
txt_colon:       db ": ", 0
txt_min:         db "  minimum = ", 0
txt_max:         db "   maximum = ", 0
txt_avg:         db "   average = ", 0
txt_watchcount:  db "  samples on WATCH  = ", 0
txt_dangercount: db "   samples on DANGER = ", 0
txt_sevlabel:    db "  final severity = ", 0
txt_overall:     db "OVERALL STATUS  : ", 0
txt_sensorsdanger: db "Sensors at DANGER: ", 0
txt_watchsamples:  db "Samples on WATCH or worse: ", 0
txt_alarm:       db "EMERGENCY ALARM : ", 0
txt_alarm_yes:   db "RAISED", 0
txt_alarm_no:    db "not raised", 0
txt_action:      db "ACTION          : ", 0
txt_action_normal: db "Continue routine monitoring. No evacuation required.", 0
txt_action_watch:  db "Increase the sampling rate and warn the duty scientist.", 0
txt_action_danger: db "Evacuate the exclusion zone. Volcanic activity is dangerous.", 0
txt_thresholds:  db "Warning thresholds", 10, 0
txt_th_watch:    db "  WATCH  >= ", 0
txt_th_danger:   db "   DANGER >= ", 0
txt_rule2:       db "--------------------------------------------------------------", 10, 0
txt_end:         db "--------------------------------------------------------------", 10, 0
; severity names
sev_normal:      db "NORMAL", 0
sev_watch:       db "WATCH", 0
sev_danger:      db "DANGER", 0

; sensor names and units
name_0:          db "Ground vibration", 0
name_1:          db "Temperature", 0
name_2:          db "Gas concentration", 0
name_3:          db "Volcanic activity", 0
unit_0:          db "index (0-255)", 0
unit_1:          db "degC", 0
unit_2:          db "ppm", 0
unit_3:          db "index (0-255)", 0

; ---------------------------------------------------------------------------
;  Section .data - tables and pointers
; ---------------------------------------------------------------------------
section .data

default_path:    db "data/sensor_readings.csv", 0
report_path:     db "out/volcano_report.txt", 0

; watch and danger threshold of each sensor, in sensor order VIB, TMP, GAS, ACT
thresholds:
    dd T_VIB_WATCH,  T_VIB_DANGER
    dd T_TMP_WATCH,  T_TMP_DANGER
    dd T_GAS_WATCH,  T_GAS_DANGER
    dd T_ACT_WATCH,  T_ACT_DANGER

; pointer tables (the strings have different lengths, so index them by pointer)
sensor_names:
    dq name_0, name_1, name_2, name_3
sensor_units:
    dq unit_0, unit_1, unit_2, unit_3
severity_table:
    dq sev_normal, sev_watch, sev_danger

; ---------------------------------------------------------------------------
;  Section .bss - working memory
; ---------------------------------------------------------------------------
section .bss

filebuf:     resb FILEBUF_SIZE
outbuf:      resb OUTBUF_SIZE
numbuf:      resb 24
vals:        resq 4                    ; the four readings of the current row

; per sensor statistics, 64 bytes each:
;   +0  minimum   +8  maximum   +16 sum   +24 count   +32 watch   +40 danger
stats:       resq 48

outlen:      resq 1
samplecount: resq 1
watch_total: resq 1
danger_total:resq 1
overall:     resq 1                    ; 0 normal, 1 watch, 2 danger
emergency:   resq 1

; ---------------------------------------------------------------------------
;  Section .text
; ---------------------------------------------------------------------------
section .text
global _start

_start:
    ; ---- 1. which file to read ---------------------------------------
    mov     rax, [rsp]                ; argc
    cmp     rax, 2
    jl      .use_default
    mov     rsi, [rsp + 16]           ; argv[1]
    jmp     .have_path
.use_default:
    mov     rsi, default_path
.have_path:

    ; ---- 2. open and read the whole file into filebuf -----------------
    mov     rax, SYS_open
    mov     rdi, rsi
    xor     esi, esi                   ; O_RDONLY
    xor     edx, edx
    syscall
    cmp     rax, 0
    jl      .open_error
    mov     r12, rax                   ; file descriptor

    xor     r13, r13                  ; bytes read so far
.read_loop:
    mov     rax, SYS_read
    mov     rdi, r12
    lea     rsi, [filebuf + r13]
    mov     rdx, FILEBUF_SIZE
    sub     rdx, r13
    syscall
    cmp     rax, 0
    jle     .read_done
    add     r13, rax
    cmp     r13, FILEBUF_SIZE
    jl      .read_loop
.read_done:
    mov     rax, SYS_close
    mov     rdi, r12
    syscall

    ; ---- 3. reset the statistics --------------------------------------
    call    init_stats

    ; ---- 4. skip the header line, then read every row -----------------
    lea     r12, [filebuf]             ; cursor
    lea     r15, [filebuf + r13]       ; one past the last byte of data
    call    skip_line                  ; throws away "vibration,temp_c,..."

.parse_row:
    cmp     r12, r15
    jae     .parse_done
    call    parse_number
    mov     [vals], rax
    call    skip_separator
    call    parse_number
    mov     [vals + 8], rax
    call    skip_separator
    call    parse_number
    mov     [vals + 16], rax
    call    skip_separator
    call    parse_number
    mov     [vals + 24], rax
    call    update_stats
    call    skip_line
    jmp     .parse_row
.parse_done:

    ; ---- 5. compose the report ----------------------------------------
    call    build_report

    ; ---- 6. write the report to stdout --------------------------------
    mov     rax, SYS_write
    mov     rdi, 1                     ; stdout
    mov     rsi, outbuf
    mov     rdx, [outlen]
    syscall

    ; ---- 7. and save it to the report file ----------------------------
    mov     rax, SYS_open
    mov     rdi, report_path
    mov     esi, 0x241                 ; O_WRONLY | O_CREAT | O_TRUNC
    mov     edx, 0o644             ; rw-r--r--
    syscall
    cmp     rax, 0
    jl      .no_report_file
    mov     r12, rax
    mov     rax, SYS_write
    mov     rdi, r12
    mov     rsi, outbuf
    mov     rdx, [outlen]
    syscall
    mov     rax, SYS_close
    mov     rdi, r12
    syscall
.no_report_file:

    ; ---- 8. exit -------------------------------------------------------
    mov     rax, SYS_exit
    xor     rdi, rdi
    syscall

.open_error:
    mov     rax, SYS_write
    mov     rdi, 2                     ; stderr
    mov     rsi, err_open
    mov     rdx, err_open_len
    syscall
    mov     rax, SYS_exit
    mov     rdi, 1
    syscall

; ===========================================================================
;  init_stats - reset every per sensor accumulator
; ===========================================================================
init_stats:
    push    rbx
    xor     rbx, rbx
    mov     rcx, 4
.init_loop:
    mov     rdx, rbx
    shl     rdx, 6
    lea     rax, [stats + rdx]
    mov     qword [rax],      -1       ; minimum, replaced on the first sample
    mov     qword [rax + 8],  0       ; maximum
    mov     qword [rax + 16], 0       ; sum
    mov     qword [rax + 24], 0       ; sample count
    mov     qword [rax + 32], 0       ; WATCH count
    mov     qword [rax + 40], 0       ; DANGER count
    inc     rbx
    loop    .init_loop
    pop     rbx
    ret

; ===========================================================================
;  skip_line - move the cursor (r12) to the start of the next line
; ===========================================================================
skip_line:
.scan:
    cmp     r12, r15
    jae     .finished
    movzx   rdx, byte [r12]
    cmp     dl, 10
    je      .advance
    inc     r12
    jmp     .scan
.advance:
    inc     r12
.finished:
    ret

; ===========================================================================
;  skip_separator - move the cursor past one ',' or blank
; ===========================================================================
skip_separator:
    movzx   rdx, byte [r12]
    cmp     dl, ','
    je      .advance
    cmp     dl, ' '
    je      .advance
    cmp     dl, 13                     ; CR
    je      .advance
    ret
.advance:
    inc     r12
    ret

; ===========================================================================
;  parse_number - read one decimal number
;  in : cursor in r12
;  out: rax = value, cursor advanced past the digits
; ===========================================================================
parse_number:
    xor     rax, rax
    movzx   rdx, byte [r12]
    cmp     dl, '0'
    jb      .done
    cmp     dl, '9'
    ja      .done
.digit:
    movzx   rdx, byte [r12]
    sub     edx, '0'
    imul    rax, rax, 10
    add     rax, rdx
    inc     r12
    movzx   rdx, byte [r12]
    cmp     dl, '0'
    jb      .done
    cmp     dl, '9'
    ja      .done
    jmp     .digit
.done:
    ret

; ===========================================================================
;  update_stats - fold the four readings of vals[] into the statistics
; ===========================================================================
update_stats:
    push    rbx
    push    r14
    xor     r14, r14
.update_loop:
    cmp     r14, 4
    jae     .update_done

    mov     rax, [vals + r14 * 8]      ; the reading
    mov     rcx, r14
    shl     rcx, 6
    lea     rbx, [stats + rcx]         ; its statistics block

    ; minimum
    mov     rcx, [rbx]
    cmp     rax, rcx
    jae     .min_done
    mov     [rbx], rax
.min_done:

    ; maximum
    mov     rcx, [rbx + 8]
    cmp     rax, rcx
    jbe     .max_done
    mov     [rbx + 8], rax
.max_done:

    ; sum and sample count
    add     [rbx + 16], rax
    inc     qword [rbx + 24]

    ; watch / danger counters
    lea     rcx, [thresholds]
    mov     rdx, r14
    shl     rdx, 3
    add     rcx, rdx
    mov     edx, [rcx]                ; watch threshold
    cmp     rax, rdx
    jb      .no_watch
    inc     qword [rbx + 32]
.no_watch:
    mov     edx, [rcx + 4]            ; danger threshold
    cmp     rax, rdx
    jb      .no_danger
    inc     qword [rbx + 40]
.no_danger:

    inc     r14
    jmp     .update_loop
.update_done:
    pop     r14
    pop     rbx
    ret

; ===========================================================================
;  emit_char - append one character to the report buffer
;  in : dil = character
; ===========================================================================
emit_char:
    push    rax
    mov     rax, [outlen]
    cmp     rax, OUTBUF_SIZE
    jae     .done
    mov     [outbuf + rax], dil
    inc     qword [outlen]
.done:
    pop     rax
    ret

; ===========================================================================
;  emit_str - append a zero terminated string to the report buffer
;  in : rsi = pointer to the string
; ===========================================================================
emit_str:
    push    rcx
    push    rdx
    push    rsi
    movzx   edx, byte [rsi]
    test    dl, dl
    jz      .done
.loop:
    movzx   edx, byte [rsi]
    test    dl, dl
    jz      .done
    mov     rax, [outlen]
    cmp     rax, OUTBUF_SIZE
    jae     .done
    mov     [outbuf + rax], dl
    inc     qword [outlen]
    inc     rsi
    jmp     .loop
.done:
    pop     rsi
    pop     rdx
    pop     rcx
    ret

; ===========================================================================
;  emit_number - append an unsigned decimal number
;  in : rax = value
; ===========================================================================
emit_number:
    push    rbx
    push    rcx
    push    rdx
    mov     rbx, 20
    mov     byte [numbuf + rbx], 0
    test    rax, rax
    jnz     .convert
    dec     rbx
    mov     byte [numbuf + rbx], '0'
    jmp     .emit
.convert:
    mov     rcx, 10
.digit:
    xor     rdx, rdx
    div     rcx                       ; rax = value / 10, rdx = remainder
    add     dl, '0'
    dec     rbx
    mov     [numbuf + rbx], dl
    test    rax, rax
    jnz     .digit
.emit:
    mov     rsi, numbuf
    add     rsi, rbx
    call    emit_str
    pop     rdx
    pop     rcx
    pop     rbx
    ret

; ===========================================================================
;  emit_average - append sum/count with one decimal place
;  in : rax = sum, rcx = count
; ===========================================================================
emit_average:
    push    rbx
    push    r12
    push    r13
    test    rcx, rcx
    jnz     .have_count
    mov     rax, 0
    call    emit_number                ; no samples at all
    jmp     .finished
.have_count:
    xor     rdx, rdx
    div     rcx                       ; rax = integer part, rdx = remainder
    mov     r12, rdx                  ; keep the remainder
    mov     r13, rcx                  ; keep the count
    call    emit_number                ; print the integer part
    mov     rax, r12
    imul    rax, rax, 10              ; remainder * 10
    xor     rdx, rdx
    div     r13                       ; rax = (remainder * 10) / count
    add     al, '0'
    mov     [numbuf], al
    mov     byte [numbuf + 1], 0
    mov     dil, '.'
    call    emit_char
    mov     rsi, numbuf
    call    emit_str
.finished:
    pop     r13
    pop     r12
    pop     rbx
    ret

; ===========================================================================
;  build_report - compose the whole warning report into outbuf
; ===========================================================================
build_report:
    push    rbx
    push    r14
    push    r15

    ; ---------------- title ---------------------------------------------
    mov     rsi, title_line
    call    emit_str
    mov     rsi, rule_line
    call    emit_str

    ; ---------------- number of samples ---------------------------------
    mov     rax, [stats + 24]          ; sample count of the first sensor
    mov     [samplecount], rax
    mov     rsi, txt_samples
    call    emit_str
    mov     rax, [samplecount]
    call    emit_number
    mov     rsi, txt_newline
    call    emit_str
    mov     rsi, txt_newline
    call    emit_str

    ; ---------------- per sensor block ----------------------------------
    xor     r14, r14
.sensor_loop:
    cmp     r14, 4
    jae     .sensors_done

    mov     rcx, r14
    shl     rcx, 6
    lea     rbx, [stats + rcx]
    mov     rcx, r14
    shl     rcx, 3

    ; sensor name and unit
    mov     rsi, [sensor_names + rcx]
    call    emit_str
    mov     rsi, txt_colon
    call    emit_str
    mov     rsi, [sensor_units + rcx]
    call    emit_str
    mov     rsi, txt_newline
    call    emit_str

    ; minimum, maximum, average
    mov     rsi, txt_min
    call    emit_str
    mov     rax, [rbx]
    call    emit_number
    mov     rsi, txt_max
    call    emit_str
    mov     rax, [rbx + 8]
    call    emit_number
    mov     rsi, txt_avg
    call    emit_str
    mov     rax, [rbx + 16]            ; sum
    mov     rcx, [rbx + 24]            ; count
    call    emit_average
    mov     rsi, txt_newline
    call    emit_str

    ; how many samples were on WATCH and on DANGER
    mov     rsi, txt_watchcount
    call    emit_str
    mov     rax, [rbx + 32]
    call    emit_number
    mov     rsi, txt_dangercount
    call    emit_str
    mov     rax, [rbx + 40]
    call    emit_number
    mov     rsi, txt_newline
    call    emit_str

    ; final severity of this sensor, judged by its worst reading
    mov     rax, [rbx + 8]
    lea     rcx, [thresholds]
    mov     rdx, r14
    shl     rdx, 3
    add     rcx, rdx
    mov     edx, [rcx + 4]             ; danger threshold
    cmp     rax, rdx
    jb      .not_danger
    mov     r15, 2
    jmp     .print_sev
.not_danger:
    mov     edx, [rcx]                 ; watch threshold
    cmp     rax, rdx
    jb      .not_watch
    mov     r15, 1
    jmp     .print_sev
.not_watch:
    xor     r15, r15
.print_sev:
    mov     rsi, txt_sevlabel
    call    emit_str
    mov     rcx, r15
    shl     rcx, 3
    mov     rsi, [severity_table + rcx]
    call    emit_str
    mov     rsi, txt_newline
    call    emit_str
    mov     rsi, txt_newline
    call    emit_str

    inc     r14
    jmp     .sensor_loop
.sensors_done:

    mov     rsi, txt_rule2
    call    emit_str

    ; ---------------- thresholds used -----------------------------------
    mov     rsi, txt_thresholds
    call    emit_str
    xor     r14, r14
.threshold_loop:
    cmp     r14, 4
    jae     .thresholds_done
    mov     rcx, r14
    shl     rcx, 3
    mov     rsi, [sensor_names + rcx]
    call    emit_str
    mov     rsi, txt_colon
    call    emit_str
    mov     rsi, txt_th_watch
    call    emit_str
    mov     eax, [thresholds + rcx]
    call    emit_number
    mov     rsi, txt_th_danger
    call    emit_str
    mov     eax, [thresholds + rcx + 4]
    call    emit_number
    mov     rsi, txt_newline
    call    emit_str
    inc     r14
    jmp     .threshold_loop
.thresholds_done:
    mov     rsi, txt_rule2
    call    emit_str

    ; ---------------- overall verdict -----------------------------------
    call    compute_overall

    mov     rsi, txt_overall
    call    emit_str
    mov     rax, [overall]
    shl     rax, 3
    mov     rsi, [severity_table + rax]
    call    emit_str
    mov     rsi, txt_newline
    call    emit_str

    mov     rsi, txt_sensorsdanger
    call    emit_str
    mov     rax, [danger_total]
    call    emit_number
    mov     rsi, txt_newline
    call    emit_str

    mov     rsi, txt_watchsamples
    call    emit_str
    mov     rax, [watch_total]
    call    emit_number
    mov     rsi, txt_newline
    call    emit_str

    mov     rsi, txt_alarm
    call    emit_str
    mov     rax, [emergency]
    cmp     rax, 0
    je      .no_alarm
    mov     rsi, txt_alarm_yes
    jmp     .print_alarm
.no_alarm:
    mov     rsi, txt_alarm_no
.print_alarm:
    call    emit_str
    mov     rsi, txt_newline
    call    emit_str

    mov     rsi, txt_action
    call    emit_str
    mov     rax, [overall]
    cmp     rax, 2
    je      .act_danger
    cmp     rax, 1
    je      .act_watch
    mov     rsi, txt_action_normal
    jmp     .print_action
.act_watch:
    mov     rsi, txt_action_watch
    jmp     .print_action
.act_danger:
    mov     rsi, txt_action_danger
.print_action:
    call    emit_str
    mov     rsi, txt_newline
    call    emit_str

    mov     rsi, txt_end
    call    emit_str

    pop     r15
    pop     r14
    pop     rbx
    ret

; ===========================================================================
;  compute_overall - decide the overall severity and the alarm condition
;  Every sensor is judged by the worst reading it ever produced.
; ===========================================================================
compute_overall:
    push    rbx
    push    r14
    push    r15

    xor     r14, r14                  ; sensor index
    xor     r15, r15                  ; overall severity
    xor     rbx, rbx                  ; sensors that reached DANGER
.next_sensor:
    cmp     r14, 4
    jae     .done_loop

    mov     rcx, r14
    shl     rcx, 6
    lea     rax, [stats + rcx]
    mov     rcx, [rax + 8]            ; the worst reading of this sensor
    lea     rdx, [thresholds]
    mov     rsi, r14
    shl     rsi, 3
    add     rdx, rsi
    mov     esi, [rdx + 4]            ; danger threshold
    cmp     rcx, rsi
    jb      .not_danger
    inc     rbx
    mov     r15, 2
    jmp     .next_iter
.not_danger:
    mov     esi, [rdx]                ; watch threshold
    cmp     rcx, rsi
    jb      .next_iter
    cmp     r15, 2
    je      .next_iter
    mov     r15, 1
.next_iter:
    inc     r14
    jmp     .next_sensor
.done_loop:
    mov     [overall], r15
    mov     [danger_total], rbx

    ; total number of samples that were on WATCH or worse
    xor     r14, r14
    xor     rbx, rbx
.count_loop:
    cmp     r14, 4
    jae     .count_done
    mov     rcx, r14
    shl     rcx, 6
    lea     rax, [stats + rcx + 32]
    mov     rax, [rax]
    add     rbx, rax
    inc     r14
    jmp     .count_loop
.count_done:
    mov     [watch_total], rbx

    ; the alarm is raised when EMERGENCY_COUNT sensors reached DANGER
    mov     rax, [danger_total]
    cmp     rax, EMERGENCY_COUNT
    jb      .no_emergency
    mov     qword [emergency], 1
    jmp     .finished
.no_emergency:
    mov     qword [emergency], 0
.finished:
    pop     r15
    pop     r14
    pop     rbx
    ret

; ---------------------------------------------------------------------------
;  error text
; ---------------------------------------------------------------------------
section .rodata
err_open:        db "volcano_report: cannot open the sensor data file", 10
err_open_len     equ $ - err_open

section .note.GNU-stack noalloc noexec nowrite progbits
