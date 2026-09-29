#ifndef MIXER_DCUBE_PAYLOAD_H
#define MIXER_DCUBE_PAYLOAD_H

#include "dcube_config.h"
#include <string.h>

// One message per node; message index equals dense logical ID.
// Bytes 0..6 retain the tutorial format. The final byte is a CRC-8 over every
// preceding byte, so a single-bit error in the 8-byte SyncCast-sized message
// cannot be mistaken for a valid sequence number.
static inline uint8_t dcube_payload_crc8(const uint8_t *data, unsigned int length)
{
    uint8_t crc = 0;
    for (unsigned int i = 0; i < length; ++i) {
        crc ^= data[i];
        for (unsigned int bit = 0; bit < 8; ++bit)
            crc = (crc & 0x80u) ? (uint8_t)((crc << 1) ^ 0x07u) : (uint8_t)(crc << 1);
    }
    return crc;
}

static inline void dcube_make_payload(uint8_t data[DCUBE_PAYLOAD_SIZE],
                                     unsigned int index, uint32_t sequence)
{
    data[0] = (uint8_t)index;
    data[1] = (uint8_t)index;
    data[2] = nodes[index];
    data[3] = (uint8_t)sequence;
    data[4] = (uint8_t)(sequence >> 8);
    data[5] = (uint8_t)(sequence >> 16);
    data[6] = (uint8_t)(sequence >> 24);
    for (unsigned int i = 7; i + 1 < DCUBE_PAYLOAD_SIZE; ++i)
        data[i] = (uint8_t)(0xa5u ^ index ^ nodes[index] ^ i ^ data[3 + (i % 4)]);
    data[DCUBE_PAYLOAD_SIZE - 1] = dcube_payload_crc8(data, DCUBE_PAYLOAD_SIZE - 1);
}

static inline uint32_t dcube_payload_round(const uint8_t *data)
{
    return (uint32_t)data[3] | ((uint32_t)data[4] << 8) |
           ((uint32_t)data[5] << 16) | ((uint32_t)data[6] << 24);
}

static inline int dcube_payload_valid(const uint8_t *data, unsigned int index)
{
    uint8_t expected[DCUBE_PAYLOAD_SIZE];
    if (index >= DCUBE_NODE_COUNT)
        return 0;
    dcube_make_payload(expected, index, dcube_payload_round(data));
    return memcmp(data, expected, sizeof(expected)) == 0;
}

#endif
