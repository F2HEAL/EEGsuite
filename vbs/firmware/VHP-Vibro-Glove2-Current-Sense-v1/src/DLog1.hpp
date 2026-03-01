// SPDX-License-Identifier: AGPL-3.0-or-later
// DLog1.hpp - Dual-channel logger for Voltage (estimated) and Current

#ifndef DLOG1_HPP_
#define DLOG1_HPP_

#include <Arduino.h>
#include <array>

struct LogSample {
    float voltage; // Estimated voltage (from PWM)
    float current; // Measured current
};

class DLog {
private:
    // Buffer for ~0.85 seconds of data at 5.86 kHz (enough for >30 cycles at 40 Hz)
    static constexpr uint32_t kBufferSize = 5000;  
    std::array<LogSample, kBufferSize> buffer_; 
    volatile uint32_t sample_count_ = 0;

public:
    // Reset the logger
    void Reset() { 
        sample_count_ = 0;
    }

    // Log a sample pair
    void Log(float voltage_V, float current_A) {
        if (sample_count_ < kBufferSize) {
            buffer_[sample_count_] = {voltage_V, current_A};
            sample_count_++;
        }
    }

    // Get number of stored samples
    uint32_t SampleCount() const { 
        return sample_count_; 
    }

    // Print all samples to Serial (CSV format)
    void PrintRawData() const {
        Serial.println("SampleIndex,Voltage(V),Current(A)");
        for (uint32_t i = 0; i < sample_count_; i++) {
            Serial.print(i);
            Serial.print(",");
            Serial.print(buffer_[i].voltage, 4);
            Serial.print(",");
            Serial.println(buffer_[i].current, 6);
        }
    }
};

#endif // DLOG1_HPP_
