# Run Mixer on the 48-node D-Cube testbed

The implemented target is **`DCUBE_Release`** in the existing nRF52840 SES project. It builds one Intel HEX image for all 48 boards. Its application generates one message per node per round and evaluates delivery through UART logs. It uses factory-ID lookup, with D-Cube binary patching disabled.

## Build and upload

From the repository root:

```sh
make dcube
```

This uses the installed SEGGER Embedded Studio for ARM 5.30, rebuilds the firmware and verifies the output. `make` is equivalent. On another installation, override the executable:

```sh
make dcube EMBUILD='/path/to/SEGGER/bin/emBuild'
```

The default slot is **5 ms**. To build a **2 ms** variant without editing the source configuration:

```sh
make dcube DCUBE_SLOT_US=2000
```

The round limit is **360 slots** by default. Set it independently or together with the slot duration:

```sh
make dcube DCUBE_ROUND_SLOTS=420
make dcube DCUBE_SLOT_US=1600 DCUBE_ROUND_SLOTS=420
```

`DCUBE_SLOT_US` is a whole number of microseconds; this 8-byte IEEE 802.15.4 build accepts values of at least 1300 us. This Make guard is a conservative build floor, not proof of runtime reliability: the 1500-us D-Cube logs report a calculated minimum of about 1199 us, leaving only about 101 us of calculated margin at 1300 us. Test shorter variants on D-Cube and check both timing counters and full decoded-message delivery. `DCUBE_ROUND_SLOTS` must be a positive whole number. Each successful build also saves variant-specific `.hex`, `.elf`, and `.map` files under `Output/DCUBE_Release/Exe/`. With the default 360 slots, filenames remain `Tutorial_slot2000us.hex`, `Tutorial_slot5000us.hex`, etc. A non-default round limit adds a suffix, for example `Tutorial_slot1600us_round420slots.hex`. The unsuffixed `Tutorial.hex` always contains the **most recently built** variant. Running plain `make dcube` again restores its 5 ms / 360-slot contents. The startup UART line prints the selected `slot_us` and `slots`, providing an on-testbed check of the uploaded image.

The verifier also needs `arm-none-eabi-nm` and `arm-none-eabi-objcopy` on PATH, as they are on this machine. To run it separately with other tool locations, pass `--nm` and `--objcopy` to `tools/verify_dcube_image.py`.

In the SES GUI, reload `tutorial/nRF52840/tutorial.emProject`, select **DCUBE_Release**, and build. The existing **PCA10056_Release** and **Debug** configurations still build the original two-node, interactive tutorial; their HEX files are not the D-Cube image.

For the 2 ms experiment, upload:

```text
tutorial/nRF52840/Output/DCUBE_Release/Exe/Tutorial_slot2000us.hex
```

For the default 5 ms experiment, use `Tutorial_slot5000us.hex` in the same directory. The corresponding ELF and map are next to each HEX. The images are standalone, start at flash address zero, and need no SoftDevice or additional bootloader. They are already Intel HEX; if a file chooser requires `.ihex`, copying one with that extension does not require conversion.

In D-Cube's Nordic queue, select your Mixer protocol entry and use:

| Setting | Initial run |
|---|---|
| Firmware | The matching slot-specific HEX under `Output/DCUBE_Release/Exe/` in the nRF52840 tutorial |
| Binary patching | **Off** |
| Serial logging | **On**, 115200 baud, 8-N-1, no flow control |
| Layout | **Empty Configuration**, where available |
| Interference/jamming | **Off** |
| Duration | About 300 seconds, subject to current portal limits |

The queue/UI procedure is documented in the [D-Cube usage guide](https://iti-testbed.tugraz.at/wiki/index.php/How_to_Use). Its [tutorial](https://iti-testbed.tugraz.at/wiki/images/b/bf/Dcube_tutorial.pdf) describes the Empty Configuration option for tests without mailbox traffic. No D-Cube job is submitted by `make` or the verification tools.

## Firmware settings

Edit `tutorial/nRF52840/dcube_config.h` and rebuild to change the D-Cube setup, except for slot duration and round limit, which can also be selected with the Make parameters above. The default settings are:

| Parameter | Value |
|---|---|
| Observer IDs | 100–119 and 200–227: all 48 nodes |
| Mixer logical IDs | 0–47, in roster order |
| Initiator | Observer **100** / logical **0** / message **0** |
| Message ownership | One message per node, message index = logical ID |
| Generation | 48 messages |
| Payload | 8 fully initialized bytes per message, matching SyncCast's application message size |
| PHY | IEEE 802.15.4, channel 26 |
| TX power | +8 dBm |
| Slot duration | 5 ms by default; configurable at build time |
| Maximum round | 360 slots by default = 1.8 seconds at 5 ms/slot |
| Inter-round gap | At least 1 second after nominal round end |
| Initiator delay | Additional 3 slots (15 ms) per round |
| First startup | Initiator waits 10 seconds; other nodes scan |
| Features | Requests and smart shutdown enabled; weak zeroes and warmstart disabled |
| Stack reservation | 4096 bytes |

At the default 5 ms setting, the nominal steady-state round period is about 2.815 seconds; with 2 ms slots it is about 1.726 seconds. Smart shutdown can stop radio participation earlier, but the application still waits until the nominal round deadline. The 5 ms settings completed 39 rounds on all 48 nodes in D-Cube job 123797. The 24-byte Mixer PHY payload takes approximately 1024 microseconds of 802.15.4 airtime before the remaining slot timing margins. The latest 5 ms logs print a calculated minimum slot of about 1.409 ms. A shorter build still needs a D-Cube run to establish its reliability and timing behavior.

The D-Cube configuration deliberately compiles the 802.15.4 transport. BLE requires a separate configuration that selects the BLE transport and revisits timing; changing only a PHY macro will fail the build. Use the same PHY, frequency, power, workload and logging policy when comparing with SyncCast.

The seed printed at startup must be nonzero. Mixer uses an XorShift generator that remains at zero forever if seeded with zero. Job **123793** hit this case at observers **100** and **207**, which then transmitted excessively and delayed or prevented full-rank decoding. The firmware now substitutes the board's unique factory ID whenever the original entropy product is zero and prints `DCUBE RNG zero seed replaced using factory ID` when this happens. Job **123797** subsequently reached rank 48 and decoded all messages in every logged node-round.

## Node identification and replacements

`DCUBE_NODE_ROSTER` is the single source of ordering for observer IDs, payload ownership and `FICR.DEVICEID[0]` lookup. All boards receive the same image. The lookup establishes identity before starting any Mixer round, without a console prompt or node-ID writes to UICR.

The roster uses observations from jobs **123764 and 123770**, including the newer IDs for observers 110, 113 and 218. These observations are recorded in `docs/dcube-node-ids-observed.csv`. Firmware reads and logs both factory-ID words, but lookup follows SyncCast's use of word zero. All 48 word-zero values are unique in the roster.

For a known board, startup includes lines like:

```text
DCUBE boot hw0=0xf2de209e hw1=0x........
DCUBE observer=100 logical=0 nodes=48 generation=48 initiator=100
DCUBE phy=IEEE802154 channel=26 tx_dbm=8 payload=8 slot_us=5000 slots=360 gap_ms=1000
```

Unknown hardware prints its factory IDs and `DCUBE ERROR unknown hardware ID`, then stays radio-silent. If a board has been replaced, use that observer's log to update its row in `dcube_config.h` and update the CSV with the new observation and provenance; rebuild. Do not assign an arbitrary existing identity to an unknown chip. A missing contributor prevents a complete 48-message exchange.

The observer's mailbox pins (P0.03/P0.04 and P1.01–P1.08) are left as inputs with no internal pulls. The application does not drive them or access the shared I2C mailbox. Nordic startup may still configure reset-pin UICR settings, independently of application identity.

## Interpreting results

For each observer, look for:

```text
# ID:100 round=7 rank=48 dec=48 !dec=0 weak=0 wrong=0 stale=0 synced=1 latency_ms=1200.000 radio_on_ms=300.000 goodput_kBps=0.320 reliability_pct=100.00
```

Here `dec` counts correctly formatted messages with the expected round number, `!dec` counts unavailable decoded rows, `wrong` counts payload-format/integrity failures, and `stale` counts otherwise valid messages from another round. `synced=1` means the initiator's message was decoded and validated as the reference for this round. **Require every shown success condition**, including `synced=1`, when counting complete rounds.

The metric values above are illustrative. Each round now prints these four measurements on the same result line:

| Field | Meaning |
|---|---|
| `latency_ms` | Time from the synchronized start of the network round to the last increase in this node's coding-matrix rank. Mixer timestamps the rank increase as it processes the innovative packet. If it received no new information, latency is zero. |
| `radio_on_ms` | Mixer's measured radio-on time for the round, converted from microseconds. The first round on non-initiators includes the initiator's 10-second startup wait while they scan; compare steady-state rounds separately. |
| `goodput_kBps` | `8-byte payload × 48 nodes ÷ latency in ms`. This is decimal kB/s; it equals 0.320 for a 1200 ms round. If latency is zero, the field is `NA` because division is undefined. The equivalent bit rate in kb/s is eight times the printed value. |
| `reliability_pct` | `valid, fresh decoded messages ÷ 48 × 100`. This includes the receiver's own message, as requested for the per-node metric. Round to two decimal places. |

The bit-based expression `payload bytes × 48 nodes × 8 ÷ latency ms` yields **kb/s**, not kB/s. Divide it by eight to obtain the printed kB/s. Goodput therefore uses the configured 48-node workload exactly as specified; `reliability_pct` shows whether every message was actually recovered. The rank timestamp is taken during packet processing, so it may be slightly later than the radio's packet arrival event.

The entire 8-byte payload is validated. It carries message index, logical and observer IDs, a 32-bit round number, and a CRC-8 integrity byte. This detects corrupted test content; it is not a cryptographic integrity scheme.

All nodes start their local counters at one. A late joiner may initially contribute that local sequence to a later network round. Such a contribution is reported as stale; the node adopts the initiator's round number and uses the next sequence in the next round. If the reference is unavailable/invalid, the current round is marked unsynchronized and the next round uses infinite scanning again. Inspect bootstrap/resynchronization rounds separately from steady state.

Download logs from **all 48 observers**. Verify startup mappings, match result lines by round number, and check all 48 result lines for each complete round. Full rank at one receiver is insufficient evidence of fleet completion. `dec=48` includes that receiver's own message: a full round represents **48 × 47 = 2256 remote deliveries**. Do not silently discard missing observers or missing rounds when computing reliability. The existing Mixer statistics and rank-up arrays remain available for diagnosing incomplete rounds and timing errors.

This application does not implement D-Cube's EEPROM/GPIO benchmark API. Its automatically generated UART workload therefore does not populate the official suite's delivery/latency measurements. Those require a separate integration, described by D-Cube's [special-features documentation](https://iti-testbed.tugraz.at/wiki/index.php/Special_Features). Serial logging and application idle periods also affect measured energy.

## Analyze downloaded logs

Use the Mixer analyzer on a D-Cube log directory:

```sh
python3 tools/analyze_mixer_logs.py logs_123790_mixer_first_run
```

It excludes `round=1` from all four averages by default, then prints every node's average over its remaining rounds and the fleet average of those per-node values. It writes `per_node_metrics.csv`, `fleet_summary.json`, a four-panel dashboard, and one plot per metric under `<log-directory>/analysis`. Use `--include-first-round` for an all-round comparison, `--no-plots` to only write the CSV/JSON and console report, or `--output-dir <directory>` to choose another destination. The analyzer accepts the current metric-enabled image and older Mixer logs; older logs are marked `derived` because latency comes from `rank_up_slot` and the other values are reconstructed from the logged configuration and counters.

## Local checks and remaining hardware check

```sh
make test
make verify
```

Host tests check all 48 identities and ownership assignments, reject unknown/old chip IDs, exercise sequence boundaries, and reject every single-bit payload corruption for eight sequence values at every node. The HEX parser is tested against malformed/truncated/overlapping records.

The image verifier checks record checksums and EOF, byte-for-byte agreement with the ELF load image, flash bounds, reset and stack vectors, the 4 KiB stack reservation, all 48 observer/hardware IDs against the recorded CSV, and the unattended startup marker. It prints a SHA-256 fingerprint for the generated HEX.

The firmware has been built locally using **SES 5.30**. The current metric-enabled image with the zero-seed guard uses 19,849 flash load bytes and 6,652 bytes of data/BSS, including the reserved stack and heap. Job **123790** used the earlier image without explicit metric fields and completed all 1,872 node-round results. Job **123793** used the metric-enabled image before the seed guard; 1,550 of its 1,872 node-round results reached full rank. Upload the current HEX for a new job to verify the seed fix and measure its effect.
