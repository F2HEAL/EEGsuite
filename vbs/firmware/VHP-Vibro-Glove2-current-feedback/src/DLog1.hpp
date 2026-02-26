// SPDX-License-Identifier: AGPL-3.0-or-later
// DLog1.hpp - Single-channel current logger (raw values only)

#ifndef DLOG1_HPP_
#define DLOG1_HPP_

#include <Arduino.h>
#include <array>

class DLog {
private:
    static constexpr uint32_t kBufferSize = 50000;  // 50k samples (1 sec @ 50kHz)
    std::array<float, kBufferSize> buffer_;        // Stores current in Amperes
    uint32_t sample_count_ = 0;

public:
    // Reset the logger (clears all samples)
    void Reset() { 
        sample_count_ = 0;
        buffer_.fill(0.0f);
    }

    // Log a current measurement (in Amperes)
    void LogCurrent(float current_A) {
        if (sample_count_ < kBufferSize) {
            buffer_[sample_count_++] = current_A;
        }
    }

    // Get number of stored samples
    uint32_t SampleCount() const { 
        return sample_count_; 
    }

    // Print all samples to Serial (CSV format)
    void PrintRawData() const {
        Serial.println("SampleIndex,Current(A)");
        for (uint32_t i = 0; i < sample_count_; i++) {
            Serial.print(i);
            Serial.print(",");
            Serial.println(buffer_[i], 6);  // 6 decimal places
        }
    }

    // Get direct access to samples (for analysis)
    const float* GetSamples() const { 
        return buffer_.data(); 
    }
};

// Instantiate the global logger directly in header
// (Only do this in Arduino environment where we don't have proper .cpp files)
DLog g_dlog;

#endif  // DLOG1_HPP_