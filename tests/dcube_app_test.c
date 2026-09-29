#include "dcube_payload.h"
#include <assert.h>
#include <stdio.h>

int main(void)
{
    const uint32_t sequences[] = {0, 1, 255, 256, 65535, 65536, UINT32_C(0x12345678), UINT32_MAX};
    assert(DCUBE_NODE_COUNT == 48);
    for (unsigned int i = 0; i < DCUBE_NODE_COUNT; ++i) {
        assert(nodes[i] == (i < 20 ? 100 + i : 200 + i - 20));
        assert(payload_distribution[i] == nodes[i]);
        assert(dcube_lookup_node(dcube_hw_ids[i]) == (int)i);
        assert(dcube_nonzero_seed(0, dcube_hw_ids[i]) == dcube_hw_ids[i]);
        assert(dcube_nonzero_seed(123, dcube_hw_ids[i]) == 123);
        for (unsigned int j = i + 1; j < DCUBE_NODE_COUNT; ++j)
            assert(dcube_hw_ids[i] != dcube_hw_ids[j]);
        for (unsigned int s = 0; s < sizeof(sequences) / sizeof(sequences[0]); ++s) {
            uint8_t payload[DCUBE_PAYLOAD_SIZE];
            dcube_make_payload(payload, i, sequences[s]);
            assert(payload[0] == i && payload[1] == i && payload[2] == nodes[i]);
            assert(dcube_payload_round(payload) == sequences[s]);
            assert(dcube_payload_round(payload) != (uint32_t)(sequences[s] + 1));
            assert(dcube_payload_valid(payload, i));
            assert(!dcube_payload_valid(payload, (i + 1) % DCUBE_NODE_COUNT));
            assert(!dcube_payload_valid(payload, DCUBE_NODE_COUNT));
            // Every single-bit error, including any sequence byte, must be detected.
            for (unsigned int byte = 0; byte < sizeof(payload); ++byte)
                for (unsigned int bit = 0; bit < 8; ++bit) {
                    payload[byte] ^= 1u << bit;
                    assert(!dcube_payload_valid(payload, i));
                    payload[byte] ^= 1u << bit;
                }
        }
    }
    assert(dcube_lookup_node(0) == -1);
    assert(dcube_nonzero_seed(0, 0) == 1);
    assert(dcube_lookup_node(UINT32_MAX) == -1);
    // Replaced boards must not silently map using the old SyncCast IDs.
    assert(dcube_lookup_node(UINT32_C(0xdded6301)) == -1);
    assert(dcube_lookup_node(UINT32_C(0x566c29d8)) == -1);
    assert(dcube_lookup_node(UINT32_C(0x3a70e9ae)) == -1);
    assert(nodes[dcube_lookup_node(UINT32_C(0x981cbad9))] == 110);
    assert(nodes[dcube_lookup_node(UINT32_C(0xde83d0ed))] == 113);
    assert(nodes[dcube_lookup_node(UINT32_C(0xf946b1dd))] == 218);
    puts("48 mappings, unknown/replaced IDs, sequence boundaries, all payload single-bit errors: PASS");
    return 0;
}
