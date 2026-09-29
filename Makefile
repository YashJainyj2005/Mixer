EMBUILD ?= /Applications/SEGGER Embedded Studio for ARM 5.30/bin/emBuild
PYTHON ?= python3
DCUBE_SLOT_US ?= 5000
DCUBE_ROUND_SLOTS ?= 360

DCUBE_OUTPUT := tutorial/nRF52840/Output/DCUBE_Release/Exe
DCUBE_IMAGE := $(DCUBE_OUTPUT)/Tutorial
ifeq ($(DCUBE_ROUND_SLOTS),360)
DCUBE_ROUND_SUFFIX :=
else
DCUBE_ROUND_SUFFIX := _round$(DCUBE_ROUND_SLOTS)slots
endif
DCUBE_VARIANT_IMAGE := $(DCUBE_OUTPUT)/Tutorial_slot$(DCUBE_SLOT_US)us$(DCUBE_ROUND_SUFFIX)

.PHONY: all dcube verify test
all: dcube

# Override DCUBE_SLOT_US or DCUBE_ROUND_SLOTS for experiment variants.
# Override EMBUILD for another SES installation. No testbed submission is performed.
dcube:
	@case "$(DCUBE_SLOT_US)" in ''|*[!0-9]*) echo 'DCUBE_SLOT_US must be a whole number of microseconds' >&2; exit 2;; esac
	@test "$(DCUBE_SLOT_US)" -ge 1300 || { echo 'DCUBE_SLOT_US must be at least 1300 us for this 8-byte IEEE 802.15.4 build' >&2; exit 2; }
	@case "$(DCUBE_ROUND_SLOTS)" in ''|*[!0-9]*) echo 'DCUBE_ROUND_SLOTS must be a whole number' >&2; exit 2;; esac
	@test "$(DCUBE_ROUND_SLOTS)" -ge 1 || { echo 'DCUBE_ROUND_SLOTS must be positive' >&2; exit 2; }
	cd tutorial/nRF52840 && "$(EMBUILD)" -rebuild -config DCUBE_Release -project Tutorial -D "DCUBE_SLOT_US=$(DCUBE_SLOT_US)" -D "DCUBE_ROUND_SLOTS=$(DCUBE_ROUND_SLOTS)" tutorial.emProject
	$(PYTHON) tools/verify_dcube_image.py
	cp "$(DCUBE_IMAGE).hex" "$(DCUBE_VARIANT_IMAGE).hex"
	cp "$(DCUBE_IMAGE).elf" "$(DCUBE_VARIANT_IMAGE).elf"
	cp "$(DCUBE_IMAGE).map" "$(DCUBE_VARIANT_IMAGE).map"
	@echo "D-Cube $(DCUBE_SLOT_US) us / $(DCUBE_ROUND_SLOTS) slots image: $(DCUBE_VARIANT_IMAGE).hex"

verify:
	$(PYTHON) tools/verify_dcube_image.py

test:
	$(PYTHON) -m unittest discover -s tests -v
