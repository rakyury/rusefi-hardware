# Power8GDI glue for the rusEFI simulator (shadow and apply modes).
# Upstream rusEFI is not modified: simulator/Makefile includes
# $(BOARD_DIR)/board_common.mk when BOARD_DIR is set.
#   make -C <rusefi>/simulator BOARD_DIR=<this dir>
P8_FW_DIR := $(BOARD_DIR)/..

MODULES_INC += $(P8_FW_DIR)/arbitration $(BOARD_DIR)
MODULES_CPPSRC += \
  $(P8_FW_DIR)/arbitration/intervention_accumulator.cpp \
  $(P8_FW_DIR)/arbitration/task_cycle.cpp \
  $(P8_FW_DIR)/arbitration/ignition_arbiter.cpp \
  $(BOARD_DIR)/p8_arbitration_sim.cpp
