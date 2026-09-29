#ifndef MIXER_DCUBE_CONFIG_H
#define MIXER_DCUBE_CONFIG_H

#include <stdint.h>

// Initial functional-test settings; tune only after checking delivery/timing logs.
// Match the SyncCast application message size for directly comparable runs.
#define DCUBE_PAYLOAD_SIZE       8
#ifndef DCUBE_ROUND_SLOTS
#define DCUBE_ROUND_SLOTS        360
#endif
#ifndef DCUBE_SLOT_US
#define DCUBE_SLOT_US            5000
#endif
#define DCUBE_CHANNEL            26
#define DCUBE_TX_POWER_DBM        8
#define DCUBE_BOOTSTRAP_DELAY_MS  10000
#define DCUBE_INTER_ROUND_MS     1000

// Observer ID, FICR.DEVICEID[0]. Observed in D-Cube jobs 123764 and 123770.
// Hardware replacements require updating this roster. Unknown chips stay silent.
// Keep one authoritative ordering for membership, message ownership and lookup.
#define DCUBE_NODE_ROSTER(X) \
    X(100, 0xf2de209e) \
    X(101, 0x92dcf7d2) \
    X(102, 0xbc490582) \
    X(103, 0xab51cee7) \
    X(104, 0x3ee55eab) \
    X(105, 0x9daeea76) \
    X(106, 0x0dbf423a) \
    X(107, 0x515bdc2a) \
    X(108, 0x167c7c75) \
    X(109, 0xe6a5f30e) \
    X(110, 0x981cbad9) \
    X(111, 0xa01ae253) \
    X(112, 0x0a578336) \
    X(113, 0xde83d0ed) \
    X(114, 0x58fc2226) \
    X(115, 0xc6e11c58) \
    X(116, 0x78ce6791) \
    X(117, 0xd4f3c2f3) \
    X(118, 0x3d8de8c4) \
    X(119, 0x122611e5) \
    X(200, 0xf111de36) \
    X(201, 0x97d52940) \
    X(202, 0x8bb27b6d) \
    X(203, 0xbd95c7bb) \
    X(204, 0x54b410fb) \
    X(205, 0x4993dd66) \
    X(206, 0x461994ed) \
    X(207, 0x4692c6b5) \
    X(208, 0xc6238a40) \
    X(209, 0xcf827d40) \
    X(210, 0x0192e724) \
    X(211, 0xcd0e34d4) \
    X(212, 0x42bc13bb) \
    X(213, 0x55c93b01) \
    X(214, 0x1723391c) \
    X(215, 0x60256590) \
    X(216, 0x01717d05) \
    X(217, 0x6391c2fb) \
    X(218, 0xf946b1dd) \
    X(219, 0x80adfe3c) \
    X(220, 0xccf7a663) \
    X(221, 0x80d0b065) \
    X(222, 0x506fcdaa) \
    X(223, 0xcc49bcab) \
    X(224, 0x72eef57a) \
    X(225, 0x7424d2d8) \
    X(226, 0x652725e7) \
    X(227, 0x74729f06)

#define DCUBE_OBSERVER_ENTRY(observer, hardware) observer,
static const uint8_t nodes[] = { DCUBE_NODE_ROSTER(DCUBE_OBSERVER_ENTRY) };
static const uint8_t payload_distribution[] = { DCUBE_NODE_ROSTER(DCUBE_OBSERVER_ENTRY) };
#undef DCUBE_OBSERVER_ENTRY

#define DCUBE_HARDWARE_ENTRY(observer, hardware) UINT32_C(hardware),
static const uint32_t dcube_hw_ids[] = { DCUBE_NODE_ROSTER(DCUBE_HARDWARE_ENTRY) };
#undef DCUBE_HARDWARE_ENTRY

#define DCUBE_NODE_COUNT (sizeof(nodes) / sizeof(nodes[0]))

// Returns the dense Mixer index, never an observer ID; -1 means unknown hardware.
static inline int dcube_lookup_node(uint32_t hardware_id)
{
    for (unsigned int i = 0; i < DCUBE_NODE_COUNT; ++i)
        if (dcube_hw_ids[i] == hardware_id)
            return (int)i;
    return -1;
}

// XorShift stays at zero forever when seeded with zero. The RNG byte can
// legitimately be zero, so use the unique factory ID in that case.
static inline uint32_t dcube_nonzero_seed(uint32_t raw_seed, uint32_t hardware_id)
{
    return raw_seed ? raw_seed : (hardware_id ? hardware_id : UINT32_C(1));
}

#endif
