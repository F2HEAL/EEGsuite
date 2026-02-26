// SPDX-License-Identifier: AGPL-3.0-or-later

#ifndef SETTINGS_HPP_
#define SETTINGS_HPP_

#include <stdint.h>
#include <array>
#include <cstdio>  // For snprintf

constexpr char name[] = "F2Heal VHP";

/**
 * Default settings.
 *
 * These settings will be used when the device is powered up. 
 */
struct Settings {
    /*
     * Configuration constants
     */
    const uint32_t default_channels = 8;  /* Number of channels silence is played
                                             on when stream is not playing */
  
    const bool     start_stream_on_power_on = false; /* Start Stream on Power On */

    /*
     * The default values for starting the Stream, see Stream.hpp for explanation.
     *
     * These values are configurable using the Bluetooth Web UI.
     */
    bool chan8 = true;
    uint32_t samplerate = 46875; //46875 | 30000
    uint32_t stimfreq = 40;
    uint32_t stimduration = 8000;
    uint32_t cycleperiod = 64000;
    uint32_t pauzecycleperiod = 1;
    uint32_t pauzedcycles = 0;
    uint16_t jitter = 0;

    // Volume settings
    uint8_t volume = 100;  // Default volume (0-100)
    uint32_t vol_amplitude = 208;  // Maximum amplitude scaling

    bool test_mode = true;
    uint16_t single_channel = 1;

    /**
     * Gets the default parameter string as const char*
     */
    const char* get_default_parameter_string() const {
        static char buffer[64];  // static to persist between calls
        
        snprintf(buffer, sizeof(buffer), 
                 "V%u F%u D%u Y%u P%u Q%u J%u M%u C%u",
                 volume,
                 stimfreq,
                 stimduration,
                 cycleperiod,
                 pauzecycleperiod,
                 pauzedcycles,
                 jitter,
                 test_mode ? 1 : 0,
                 single_channel);
        
        return buffer;
    }
  
} g_settings;

#endif