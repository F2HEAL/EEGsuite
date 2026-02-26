// SPDX-License-Identifier: AGPL-3.0-or-later
// 20251016 bepg + 20251104

const char* FIRMWARE_VERSION = "SERCOM_2_0_3_CURRENT_SENSE_v1";  // volume correction + parameter string + current feedback


#include "src/PwmTactor.hpp"
#include "src/BatteryMonitor.hpp"
#include "src/BleComm.hpp"
#include "src/SStream.hpp"
#include "src/Settings.hpp"
#include "src/Max14661.hpp"
#include "src/DLog1.hpp"

using namespace audio_tactile;

SStream *g_stream = 0;
bool g_ble_connected = false;
bool g_running = false;
// uint8_t g_volume = 75; // was 25 // moved to settings.hpp  
// uint16_t g_volume_lvl = g_volume * g_settings.vol_amplitude / 100;
uint16_t g_volume_lvl;  // Will be calculated in setup()

uint64_t g_running_since = 0;

String serialBuffer = "";

// Current Sensing Objects
DLog g_dlog;
int measuring_channel = 0;
int new_channel = 0;

void setup() {

    nrf_gpio_cfg_output(kLedPinBlue);
    nrf_gpio_cfg_output(kLedPinGreen);  
    nrf_gpio_pin_set(kLedPinBlue);
    
    // Initialize Multiplexer
    Multiplexer.Initialize();
    
    PwmTactor.OnSequenceEnd(OnPwmSequenceEnd);
    PwmTactor.Initialize();
    
    nrf_pwm_task_trigger(NRF_PWM1, NRF_PWM_TASK_SEQSTART0);
    nrf_pwm_task_trigger(NRF_PWM2, NRF_PWM_TASK_SEQSTART0);
    
    PuckBatteryMonitor.InitializeLowVoltageInterrupt();
    PuckBatteryMonitor.OnLowBatteryEventListener(LowBatteryWarning);

    // Create BLE name with version (using char array instead of String)
    char bleName[32];  // BLE names have max 31 chars + null terminator
    snprintf(bleName, sizeof(bleName), "F2Heal VHP v%s", FIRMWARE_VERSION);
    
    BleCom.Init(bleName, OnBleEvent);

    // Initialize volume level based on settings
    g_volume_lvl = g_settings.volume * g_settings.vol_amplitude / 100;

    SetSilence();

    nrf_gpio_cfg_input(kTactileSwitchPin, NRF_GPIO_PIN_PULLUP);
    attachInterrupt(kTactileSwitchPin_nrf, ToggleStream, RISING);

    nrf_gpio_cfg_input(kTTL1Pin, NRF_GPIO_PIN_NOPULL);
    attachInterrupt(kTTL1Pin_nrf, StartStream, RISING);
    attachInterrupt(kTTL1Pin_nrf, StopStream, FALLING);
    
    nrf_gpio_pin_clear(kLedPinBlue);
    nrf_gpio_pin_clear(kLedPinGreen);  
    
    if(g_settings.start_stream_on_power_on) {
        ToggleStream();
    }
}

void SetSilence() {
    g_volume_lvl = g_settings.volume * g_settings.vol_amplitude / 100;
}

void OnPwmSequenceEnd() {
    static uint32_t last_sample_time = 0;
    
    if(g_running) {
        // --- Current Sensing Logic Start ---
        // 1. Get current PWM state
        bool pwm_active = (nrf_pwm_event_check(NRF_PWM1, NRF_PWM_EVENT_SEQSTARTED0));
          
        // 2. Sample only during stable PWM ON period (skip first 300us of transient)
        if(pwm_active && (micros() - last_sample_time > 300)) { 
            // Read from A6 (Pin D10) which is configured for Current Sense
            // Default 12-bit res, 3.6V ref
            float adc_val = analogRead(A6); 
              
            // 3. Apply moving average filter
            static float filtered_val = 0;
            filtered_val = 0.9 * filtered_val + 0.1 * adc_val;
              
            // Convert to Amps: (ADC_Val * (V_Ref / Resolution)) / Gain_V_per_A
            // Assuming 20x gain on 0.25 ohm resistor -> 5V/A (Verify hardware gain!)
            // Re-using the conversion from the doc: filtered_val * (3.3f/4095.0f)/5.0f
            g_dlog.LogCurrent(filtered_val * (3.6f/4095.0f)/5.0f); 
            last_sample_time = micros();
        }
          
        // 4. Channel switching only during PWM OFF
        // Only switch if we need to measure a different channel
        if(!pwm_active && (measuring_channel != new_channel)) {
            Multiplexer.ConnectChannel(new_channel); // Connect directly to channel index
            measuring_channel = new_channel;
            delayMicroseconds(600); // Mux settling time
        }
        // --- Current Sensing Logic End ---

        g_stream->next_sample_frame();
        
        const auto active_channel = g_stream->current_active_channel();
        
        // Update new_channel for the next mux switch opportunity
        new_channel = active_channel;
        
        for(uint32_t channel = 0; channel < g_stream->channels(); channel++)
            if(channel==active_channel) {
                uint16_t* cp = PwmTactor.GetChannelPointer(channel);
                g_stream->set_chan_samples(cp, channel);

                if(!g_settings.chan8) {
                    uint16_t* cp = PwmTactor.GetChannelPointer(7-channel);
                    g_stream->set_chan_samples(cp, channel);
                }
            } else {
                PwmTactor.SilenceChannel(channel, g_volume_lvl);
                if(!g_settings.chan8)
                    PwmTactor.SilenceChannel(7-channel, g_volume_lvl);
            }
    } else {
        for(uint32_t i = 0; i < g_settings.default_channels; i++)
            PwmTactor.SilenceChannel(i, g_volume_lvl);
    }    
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();

    if (cmd == '\n' || cmd == '\r') {
      // End of a command
      if (serialBuffer.length() > 0) {
        processSerialCommand(serialBuffer);
        serialBuffer = "";
      }
    }
    else {
      serialBuffer += cmd;
    }
  }
}

void processSerialCommand(String cmd) {
  if (cmd.length() == 0) return;

  if (cmd.length() == 1) {
    char c = cmd.charAt(0);
    
    if (c == '1') {
      StartStream();
      Serial.write('1');
    }
    else if (c == '0') {
      StopStream();
      Serial.write('0');
    }
    else if (c == 'T') {
      ToggleStream();
      Serial.write('T');
    }
    else if (c == 'L') {
      Serial.write('L');
    }
    else if (c == 'S') {  // Added 'S' command to get version
      Serial.print("FW Version: ");
      Serial.println(FIRMWARE_VERSION);
    }
    else if (c == 'C') { // Added 'C' command to dump current log
        g_dlog.PrintRawData();
        g_dlog.Reset(); // Clear after dumping
    }

    else if (c == 'X') {
      // Use the dynamically generated parameter string
      const char* paramString = g_settings.get_default_parameter_string();
      Serial.print(paramString);
    }

    else {
      Serial.print("Unknown: ");
      Serial.println(c);
    }
  }
  else {
    // Multi-character command, e.g. V128 or F250
    char commandType = cmd.charAt(0);
    int value = cmd.substring(1).toInt();

    switch (commandType) {
      case 'V':
        g_settings.volume = constrain(value, 0, 100);  // Changed from g_volume
        Serial.print("'volume' set to ");
        Serial.println(g_settings.volume);  // Changed from g_volume
        SetSilence();  // Update the actual output level
        break;

      case 'F':
        g_settings.stimfreq = constrain(value, 1, 400);
        Serial.print("'stimfreq' set to ");
        Serial.println(g_settings.stimfreq);
        break;

      case 'D':
        g_settings.stimduration = constrain(value, 1, 65535);
        Serial.print("'stimduration' set to ");
        Serial.println(g_settings.stimduration);
        break;

      case 'Y':
        g_settings.cycleperiod = constrain(value, 1, 65535);
        Serial.print("'cycleperiod' set to ");
        Serial.println(g_settings.cycleperiod);
        break;

      case 'P':
        g_settings.pauzecycleperiod = constrain(value, 0, 100);
        Serial.print("'pauzecycleperiod' set to ");
        Serial.println(g_settings.pauzecycleperiod);
        break;

      case 'Q':
        g_settings.pauzedcycles = constrain(value, 0, 100);
        Serial.print("'pauzedcycles' set to ");
        Serial.println(g_settings.pauzedcycles);
        break;

      case 'J':
        g_settings.jitter = constrain(value, 0, 1000);
        Serial.print("'jitter' set to ");
        Serial.println(g_settings.jitter);
        break;

      case 'M':
        g_settings.test_mode = (value != 0);
        Serial.print("'test_mode' set to ");
        Serial.println(g_settings.test_mode ? "true" : "false");
        break;

      case 'C':
        g_settings.single_channel = constrain(value, 0, 8);
        Serial.print("'single_channel' set to ");
        Serial.println(g_settings.single_channel);
        break;

      default:
        Serial.print("Unknown command: ");
        Serial.println(cmd);
        break;
    }
  }
}


void LowBatteryWarning() {
    nrf_gpio_pin_set(kLedPinBlue);  
}

void OnBleEvent() {
    switch (BleCom.event()) {
    case BleEvent::kConnect:
        g_ble_connected = true;
        break;
    case BleEvent::kDisconnect:
        g_ble_connected = false;
        break;
    case BleEvent::kInvalidMessage:
        break;
    case BleEvent::kMessageReceived:
        HandleMessage(BleCom.rx_message());
        break;
    }
}

void StartStream() {
    if(!g_running) ToggleStream();
}

void StopStream() {
    if(g_running) ToggleStream();
}

volatile unsigned long g_last_toggle = 0;

void ToggleStream() {
    auto now = millis();
    if(now - g_last_toggle < 250) return;
    g_last_toggle = now;
    
    if(g_running) {
        g_running = false;    
        nrf_gpio_pin_clear(kLedPinGreen);    
        delete g_stream;
    } else {
        nrf_gpio_pin_set(kLedPinGreen);
        g_stream = new SStream(g_settings.chan8,
                     g_settings.samplerate,
                     g_settings.stimfreq,
                     g_settings.stimduration,
                     g_settings.cycleperiod,
                     g_settings.pauzecycleperiod,
                     g_settings.pauzedcycles,
                     g_settings.jitter,
                     g_settings.volume * g_settings.vol_amplitude / 100, // *800 /512,
                     g_settings.test_mode,
                     g_settings.single_channel);
        g_running = true;
        g_running_since = millis(); 
    }
    
    if(g_ble_connected) {
        SendStatus();    
    }
}

void SendStatus() {
    uint16_t battery_voltage_uint16 = PuckBatteryMonitor.MeasureBatteryVoltage();
    float battery_voltage_float = PuckBatteryMonitor.ConvertBatteryVoltageToFloat(battery_voltage_uint16);
    
    uint64_t running_period = 0;
    if(g_running) {
        running_period = millis() - g_running_since;
    }

    // Use the new method that takes settings directly
    BleCom.tx_message().WriteStatus(g_running, running_period, battery_voltage_float, FIRMWARE_VERSION, g_settings);
    BleCom.SendTxMessage();
}

void HandleMessage(const Message& message) {
    switch (message.type()) {
    case MessageType::kVolume:
        message.Read(&g_settings.volume);
        SetSilence();    
        break;
    case MessageType::kGetVolume:
        BleCom.tx_message().WriteVolume(g_settings.volume);
        BleCom.SendTxMessage();
        break;
    case MessageType::kToggle:
        ToggleStream();
        break;
    case MessageType::k8Channel:
        message.Read(&g_settings.chan8);
        break;
    case MessageType::kStimFreq:
        message.Read(&g_settings.stimfreq);
        break;
    case MessageType::kStimDur:
        message.Read(&g_settings.stimduration);
        break;
    case MessageType::kCyclePeriod:
        message.Read(&g_settings.cycleperiod);
        break;
    case MessageType::kPauzeCyclePeriod:
        message.Read(&g_settings.pauzecycleperiod);
        break;
    case MessageType::kPauzedCycles:
        message.Read(&g_settings.pauzedcycles);
        break;
    case MessageType::kJitter:
        message.Read(&g_settings.jitter);
        break;
    case MessageType::kSingleChannel:
        message.Read(&g_settings.single_channel);
        break;    
    case MessageType::kTestMode:
        message.Read(&g_settings.test_mode);
        break;
    case MessageType::kGetSettingsBatch:
        BleCom.tx_message().WriteSettings(g_settings);
        BleCom.SendTxMessage();
        break;
    case MessageType::kGetStatusBatch:
        SendStatus();
        break;
    case MessageType::kGetVersion:  // Added case for version request
        BleCom.tx_message().WriteVersion(FIRMWARE_VERSION);
        BleCom.SendTxMessage();
        break;   
    default:
        break;
    }
}

namespace std {
    void __throw_length_error(char const* e) {
        while (true) {}    
    }
}	
