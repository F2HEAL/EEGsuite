// SPDX-License-Identifier: AGPL-3.0-or-later
// SimpleFilter.hpp - Low-pass filter for current measurements

#ifndef SIMPLE_FILTER_HPP_
#define SIMPLE_FILTER_HPP_

/**
 * First-order IIR low-pass filter for smoothing noisy measurements.
 * 
 * Filter equation: y[n] = alpha * x[n] + (1 - alpha) * y[n-1]
 * 
 * where:
 *   alpha = cutoff_freq / (sampling_freq + cutoff_freq)
 *   
 * This provides -3dB attenuation at the cutoff frequency.
 * 
 * Example usage:
 *   SimpleFilter filter(5860, 150);  // 5860 Hz sampling, 150 Hz cutoff
 *   for each new sample:
 *     filtered_value = filter.Update(raw_value);
 */
class SimpleFilter {
private:
    float alpha_;         // Filter coefficient
    float last_output_;   // Previous output for IIR feedback
    bool initialized_;    // Track if we've received first sample

public:
    /**
     * Initialize a first-order low-pass filter.
     *
     * @param sampling_freq Sampling rate in Hz (e.g., 5860)
     * @param cutoff_freq   Cutoff frequency in Hz (e.g., 150)
     *                      Use higher values to pass more signal (less filtering)
     *                      Use lower values for more aggressive filtering
     */
    SimpleFilter(float sampling_freq, float cutoff_freq)
        : last_output_(0.0f), initialized_(false) {
        // Calculate filter coefficient
        // alpha ranges from 0 (heavily filtered) to 1 (no filtering)
        alpha_ = cutoff_freq / (sampling_freq + cutoff_freq);
    }

    /**
     * Apply filter to new sample.
     *
     * @param raw_value Raw measurement
     * @return Filtered output
     */
    float Update(float raw_value) {
        if (!initialized_) {
            // Initialize with first sample
            last_output_ = raw_value;
            initialized_ = true;
            return raw_value;
        }
        
        // Apply first-order IIR filter
        float filtered = alpha_ * raw_value + (1.0f - alpha_) * last_output_;
        last_output_ = filtered;
        return filtered;
    }

    /**
     * Reset filter state (useful between streams).
     */
    void Reset() {
        last_output_ = 0.0f;
        initialized_ = false;
    }

    /**
     * Set initial value (helps avoid transients when starting).
     */
    void SetInitial(float value) {
        last_output_ = value;
        initialized_ = true;
    }
};

#endif // SIMPLE_FILTER_HPP_
