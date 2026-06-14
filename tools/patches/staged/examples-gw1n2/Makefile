YOSYS ?= yosys
YOSYS_FLAGS = -setundef
NEXTPNR ?= nextpnr-himbaechel
NEXTPNR_FLAGS ?= --timing-allow-fail -r

.DEFAULT_GOAL := all
.PHONY: all gw1n2 gw1n2-unpacked clean

# GW1N-2 (GW1N-UV2 family). The GW1N-2 die ships license-free in Gowin EDA only
# as GW1N-1P5C (same silicon), so the device uses GW1N-1P5C vendor data and a
# GW1N-1P5C partnumber; "--vopt family=GW1N-2" selects our chipdb -- the same
# idiom tangnano9k uses with "--vopt family=GW1N-9C".
gw1n2: blinky-gw1n2.fs

gw1n2-unpacked: blinky-gw1n2-unpacked.v

all: gw1n2

clean:
	rm -f *.json *.fs *-unpacked.v

%-gw1n2.fs: %-gw1n2.json
	gowin_pack -d GW1N-2 -o $@ $<

%-gw1n2.json: %-gw1n2-synth.json gw1n2.cst
	$(NEXTPNR) ${NEXTPNR_FLAGS} --json $< --write $@ --device GW1N-UV1P5QN48XFC7/I6 --vopt family=GW1N-2 --vopt cst=gw1n2.cst

%-gw1n2-synth.json: %.v
	$(YOSYS) -p "read_verilog $^; synth_gowin -json $@ ${YOSYS_FLAGS}"

# optional: read the bitstream back (sanity check, not required by CI)
%-gw1n2-unpacked.v: %-gw1n2.fs
	gowin_unpack -d GW1N-2 -o $@ $<
