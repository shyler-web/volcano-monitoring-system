# Volcano Monitoring System - build and verification
#
#   make            build the assembly program
#   make run        run it on the main dataset
#   make vectors    regenerate + run the Logisim test vectors
#   make check      run every automated check
#   make clean      remove build artefacts
#
# If "nasm" is not on your PATH and it lives in ~/tools/nasm/bin, run
#   make NASM=~/tools/nasm/bin/nasm

NASM      ?= nasm
CC        ?= gcc
LD        ?= ld

ROOT      := $(CURDIR)
ASM_DIR   := $(ROOT)/asm
OUT_DIR   := $(ROOT)/out
CIRC      := $(ROOT)/circuit/volcano_monitor.circ
VECTORS   := $(ROOT)/circuit/volcano_monitor_vectors.txt
LOGISIM   ?= $(HOME)/tools/logisim-evolution/bin/logisim-evolution

.PHONY: all run vectors check clean dirs report

all: dirs $(OUT_DIR)/volcano_report

dirs:
	@mkdir -p $(OUT_DIR)

$(OUT_DIR)/volcano_report: $(ASM_DIR)/volcano_report.asm $(ASM_DIR)/thresholds.inc | dirs
	$(NASM) -f elf64 -I $(ASM_DIR)/ $(ASM_DIR)/volcano_report.asm -o $(OUT_DIR)/volcano_report.o
	$(LD) -o $@ $(OUT_DIR)/volcano_report.o
	@echo "built $@"

run: all
	@cd $(ROOT) && ./out/volcano_report data/sensor_readings.csv

report: run
	@echo
	@echo "--- report file written to out/volcano_report.txt ---"

# regenerate the Logisim test vectors from the shared thresholds
vectors:
	@python3 $(ROOT)/tools/gen_vectors.py

# full verification: assembly output vs the python reference model, and the
# Logisim circuit against the test vectors
check: all
	@bash $(ROOT)/tools/check_all.sh

clean:
	rm -f $(OUT_DIR)/volcano_report $(OUT_DIR)/volcano_report.o $(OUT_DIR)/volcano_report.txt
	rm -f $(ROOT)/circuit/lbl_test*.circ $(ROOT)/circuit/probe*.circ
	rm -rf $(ROOT)/circuit/.logisim-mcp
