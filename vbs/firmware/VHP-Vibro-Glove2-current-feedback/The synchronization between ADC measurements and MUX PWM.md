The synchronization between ADC measurements and PWM timing is crucial for accurate current sensing in your system. Here's a detailed explanation of the noise issues and how to properly synchronize measurements:

---

### Noise Sources in Your Setup

1. PWM Switching Noise:  
   * High-frequency (kHz-range) spikes during MOSFET switching  
   * Coupled through power rails and ground loops  
2. Multiplexer Switching Artifacts:  
   * Glitches when changing channels (\~500µs settling time)  
   * Charge injection from CMOS switches  
3. Current Sense Amplifier Issues:  
   * Output ringing during PWM transitions  
   * Bandwidth limitations causing phase delays

---

### Optimal Measurement Timing

Your system should follow this sequence:

plaintext

Copy

Download

`PWM Period (e.g., 200Hz = 5ms)`  
`|`  
`├── PWM ON (stimduration)`  
`│   └── ADC Sample Point (middle of ON period)`  
`│`  
`└── PWM OFF`  
    `└── Mux Switching (if changing channels)`

---

### Implementation Code

Add these timing controls to `OnPwmSequenceEnd()`:

cpp

Copy

Download

`void OnPwmSequenceEnd() {`  
    `static uint32_t last_sample_time = 0;`  
      
    `if(g_running) {`  
        `// 1. Get current PWM state`  
        `bool pwm_active = (nrf_pwm_event_check(NRF_PWM1, NRF_PWM_EVENT_SEQSTARTED0));`  
          
        `// 2. Sample only during stable PWM ON period`  
        `if(pwm_active && (micros() - last_sample_time > 300)) { // Skip first 300µs`  
            `float adc_val = analogRead(A6);`  
              
            `// 3. Apply moving average filter`  
            `static float filtered_val = 0;`  
            `filtered_val = 0.9 * filtered_val + 0.1 * adc_val;`  
              
            `g_dlog.LogCurrent(filtered_val * (3.3f/4095.0f)/5.0f);`  
            `last_sample_time = micros();`  
        `}`  
          
        `// 4. Channel switching only during PWM OFF`  
        `if(!pwm_active && (measuring_channel != new_channel)) {`  
            `Multiplexer.ConnectChannel(order_pairs[new_channel]);`  
            `measuring_channel = new_channel;`  
            `delayMicroseconds(600); // Mux settling time`  
        `}`  
    `}`  
`}`

---

### Hardware Improvements

1. Add RC Filters:  
2. plaintext  
3. Copy  
4. Download

`Current Sense → 100Ω → ADC Pin`  
                `↓`

5.               `0.1µF → GND`  
6. Star Grounding:  
   * Separate analog (sensing) and digital (PWM) grounds  
   * Join at a single point near power supply  
7. Shielding:  
   * Twist current sense wires together  
   * Use shielded cable for analog signals

---

### Debugging Noisy Measurements

1. Oscilloscope Checks:  
   * Probe across the 0.25Ω sense resistor  
   * Verify clean PWM transitions (no ringing)  
   * Check amplifier output stability  
2. Software Diagnostics:

cpp

Copy

Download

`void PrintNoiseMetrics() {`  
    `float sum = 0, sq_sum = 0;`  
    `for(int i=0; i<g_dlog.SampleCount(); i++) {`  
        `float val = g_dlog.GetSamples()[i];`  
        `sum += val;`  
        `sq_sum += val * val;`  
    `}`  
    `float mean = sum / g_dlog.SampleCount();`  
    `float stddev = sqrt(sq_sum/g_dlog.SampleCount() - mean*mean);`  
      
    `Serial.print("Noise: ±");`   
    `Serial.print(stddev*1000, 1);`   
    `Serial.println(" mA");`  
`}`

---

### Expected Performance

| Scenario | Good Result | Problem Indication |
| :---- | :---- | :---- |
| PWM ON | Stable DC \+ ripple \< 50mV | \>100mV spikes |
| PWM OFF | Near 0V (±10mV) | Residual voltage \>50mV |
| Mux Switch | Settling \< 500µs | Glitches \>1ms |

---

### Advanced Synchronization

For precise timing, use PWM interrupts:

cpp

Copy

Download

`void setup() {`  
    `nrf_pwm_event_clear(NRF_PWM1, NRF_PWM_EVENT_SEQEND0);`  
    `nrf_pwm_int_enable(NRF_PWM1, NRF_PWM_INT_SEQEND0_MASK);`  
    `NVIC_EnableIRQ(PWM1_IRQn);`  
`}`

`void PWM1_IRQHandler() {`  
    `if(nrf_pwm_event_check(NRF_PWM1, NRF_PWM_EVENT_SEQEND0)) {`  
        `nrf_pwm_event_clear(NRF_PWM1, NRF_PWM_EVENT_SEQEND0);`  
        `// Take ADC sample here for perfect timing`  
    `}`  
`}`

---

### Key Recommendations

1. Sample 300µs after PWM edges (avoid switching transients)  
2. Average 8-16 samples per PWM cycle  
3. Keep mux changes synchronous with PWM OFF periods  
4. Verify with oscilloscope \- No amount of software can fix hardware noise

Would you like me to provide specific filter component values or PCB layout suggestions?  
