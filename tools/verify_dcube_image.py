"""Check the actual D-Cube HEX against its ELF and the observed 48-node roster."""

import argparse
import csv
import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tutorial/nRF52840/Output/DCUBE_Release/Exe/Tutorial"


def read_hex(path):
    memory = {}
    base = 0
    eof = False
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        if eof or not line.startswith(":"):
            raise ValueError(f"Invalid HEX record at line {number}")
        record = bytes.fromhex(line[1:])
        if len(record) < 5 or len(record) != record[0] + 5 or sum(record) % 256:
            raise ValueError(f"HEX length/checksum failure at line {number}")
        count, address, kind = record[0], int.from_bytes(record[1:3], "big"), record[3]
        data = record[4:-1]
        if kind == 0:
            for offset, value in enumerate(data):
                target = base + address + offset
                if target in memory:
                    raise ValueError(f"Overlapping HEX data at 0x{target:x}")
                memory[target] = value
        elif kind == 1 and count == 0 and address == 0:
            eof = True
        elif kind in (2, 4) and count == 2 and address == 0:
            base = int.from_bytes(data, "big") << (4 if kind == 2 else 16)
        elif kind in (3, 5) and count == 4 and address == 0:
            pass  # Entry metadata; the MCU boots through the vector table.
        else:
            raise ValueError(f"Unsupported/malformed HEX type {kind} at line {number}")
    if not eof or not memory:
        raise ValueError("HEX is empty or has no EOF record")
    return memory


def read_bytes(memory, address, size):
    try:
        return bytes(memory[address + i] for i in range(size))
    except KeyError as error:
        raise ValueError(f"Missing HEX byte at 0x{error.args[0]:x}") from error


def read_symbols(elf, nm):
    output = subprocess.check_output([nm, "-S", "--defined-only", str(elf)], text=True)
    symbols = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) in (3, 4):
            symbols[fields[-1]] = (int(fields[0], 16),
                                  int(fields[1], 16) if len(fields) == 4 else None)
    return symbols


def verify(hex_path, elf_path, roster_path, nm, objcopy):
    memory = read_hex(hex_path)
    if min(memory) != 0 or max(memory) >= 0x100000:
        raise ValueError("Expected a standalone nRF52840 flash image at address zero")
    with tempfile.TemporaryDirectory(prefix="mixer-hex-check-") as directory:
        exported = Path(directory) / "from-elf.hex"
        subprocess.run([objcopy, "-O", "ihex", str(elf_path), str(exported)], check=True)
        if read_hex(exported) != memory:
            raise ValueError("HEX contents do not match the ELF load image")

    symbols = read_symbols(elf_path, nm)
    stack, reset = struct.unpack("<II", read_bytes(memory, 0, 8))
    if not 0x20000000 < stack <= 0x20040000 or stack % 8:
        raise ValueError("Invalid initial stack pointer")
    if reset != (symbols["Reset_Handler"][0] | 1) or reset & ~1 not in memory:
        raise ValueError("Reset vector does not point to the ELF's Thumb reset handler")
    if symbols["__stack_size__"][0] < 4096 or stack != symbols["__stack_end__"][0]:
        raise ValueError("D-Cube build requires a 4 KiB stack and matching vector")

    with Path(roster_path).open(newline="") as stream:
        roster = list(csv.DictReader(stream))
    observers = [int(row["observer_id"]) for row in roster]
    hardware = [int(row["observed_deviceid0"], 16) for row in roster]
    if observers != list(range(100, 120)) + list(range(200, 228)):
        raise ValueError("Expected the ordered 48-observer roster")
    if len(set(hardware)) != 48:
        raise ValueError("Duplicate hardware IDs in roster")
    for name, expected in (("nodes", bytes(observers)),
                           ("dcube_hw_ids", struct.pack("<48I", *hardware))):
        address, size = symbols[name]
        if size != len(expected) or read_bytes(memory, address, size) != expected:
            raise ValueError(f"Firmware {name} does not match the observed roster")

    flash = bytes(memory[address] for address in sorted(memory))
    if (b"DCUBE boot hw0=" not in flash or
            b"DCUBE RNG zero seed replaced" not in flash or
            b"Node ID not set. enter value:" in flash):
        raise ValueError("Wrong firmware: expected unattended D-Cube startup")
    for metric in (b"latency_ms=", b"radio_on_ms=", b"goodput_kBps=",
                   b"reliability_pct="):
        if metric not in flash:
            raise ValueError(f"D-Cube image does not print {metric.decode()}")
    print(f"Verified: {hex_path}")
    print("HEX checksums/EOF, ELF match, reset/stack vectors, 48 IDs, per-round metrics: PASS")
    print(f"Flash load bytes: {len(memory)}; stack reservation: {symbols['__stack_size__'][0]} bytes")
    print(f"SHA256: {hashlib.sha256(Path(hex_path).read_bytes()).hexdigest()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hex", type=Path, default=OUTPUT.with_suffix(".hex"))
    parser.add_argument("--elf", type=Path, default=OUTPUT.with_suffix(".elf"))
    parser.add_argument("--roster", type=Path, default=ROOT / "docs/dcube-node-ids-observed.csv")
    parser.add_argument("--nm", default="arm-none-eabi-nm")
    parser.add_argument("--objcopy", default="arm-none-eabi-objcopy")
    args = parser.parse_args()
    try:
        verify(args.hex, args.elf, args.roster, args.nm, args.objcopy)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Verification failed: {error}\n")


if __name__ == "__main__":
    main()
