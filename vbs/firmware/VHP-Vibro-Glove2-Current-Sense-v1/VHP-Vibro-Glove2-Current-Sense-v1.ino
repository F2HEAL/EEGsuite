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
#include "src/SimpleFilter.hpp"

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
SimpleFilter g_current_filter(5860.0f, 150.0f);  // 5860 Hz sampling, 150 Hz cutoff
int measuring_channel = -1; // Force connection on first update
int new_channel = 0;

// Runtime Load Estimation (Peak Current Monitor)
bool g_continuous_load_output = false;

void setup() {
    Serial.begin(115200);
    delay(500); 
    
    nrf_gpio_cfg_output(kLedPinBlue);
    nrf_gpio_cfg_output(kLedPinGreen);  
    nrf_gpio_pin_set(kLedPinBlue);

    // Hardware Enable: Pin 42 set to 0 (Matches known-working FW)
    nrf_gpio_cfg_output(42);
    nrf_gpio_pin_write(42, 0); 
    
    // --- FORCE SETTINGS FOR 40Hz OSCILLOSCOPE MODE ---
    g_settings.stimfreq = 40;        
    g_settings.single_channel = 5;   // Force WebUI Channel 5
    g_settings.volume = 80;          
    g_settings.chan8 = true;         
    g_settings.test_mode = true;     
    Serial.println("FORCED MODE: 40Hz, WebUI CH5 (PCB CH4), Volume 80%");

    Multiplexer.Initialize();
    Multiplexer.Enable();
    Multiplexer.ConnectChannel(order_pairs[4]); // Pre-connect Mux to CH5
    measuring_channel = 4;
    
    PwmTactor.OnSequenceEnd(OnPwmSequenceEnd);
    PwmTactor.Initialize();
    
    // PWM0 is auto-triggered on nRF52 Arduino, only trigger 1 and 2
    nrf_pwm_task_trigger(NRF_PWM1, NRF_PWM_TASK_SEQSTART0);
    nrf_pwm_task_trigger(NRF_PWM2, NRF_PWM_TASK_SEQSTART0);
    
    PuckBatteryMonitor.InitializeLowVoltageInterrupt();
    PuckBatteryMonitor.OnLowBatteryEventListener(LowBatteryWarning);

    char bleName[32];
    snprintf(bleName, sizeof(bleName), "F2Heal VHP v%s", FIRMWARE_VERSION);
    BleCom.Init(bleName, OnBleEvent);

    g_volume_lvl = g_settings.volume * g_settings.vol_amplitude / 100;
    SetSilence();

    nrf_gpio_cfg_input(kTactileSwitchPin, NRF_GPIO_PIN_PULLUP);
    attachInterrupt(kTactileSwitchPin_nrf, ToggleStream, RISING);

    nrf_gpio_cfg_input(kTTL1Pin, NRF_GPIO_PIN_NOPULL);
    attachInterrupt(kTTL1Pin_nrf, StartStream, RISING);
    attachInterrupt(kTTL1Pin_nrf, StopStream, FALLING);
    
    nrf_gpio_pin_clear(kLedPinBlue);
    nrf_gpio_pin_clear(kLedPinGreen);  
    
    if(g_settings.start_stream_on_power_on) ToggleStream();
}

void SetSilence() {
    g_volume_lvl = g_settings.volume * g_settings.vol_amplitude / 100;
}

void OnPwmSequenceEnd() {
    if(g_running) {
        g_stream->next_sample_frame();
        const auto active_channel = g_stream->current_active_channel();
        
        // Match Old FW logic: Only update Mux or Sample, never both at once.
        if(active_channel != (uint32_t)measuring_channel) {
            measuring_channel = active_channel;
            Multiplexer.ConnectChannel(order_pairs[measuring_channel]);
        } else {
            // Use A6 for current sensing (PCB AIN6)
            int16_t raw_adc = analogRead(A6);
            
            // --- Current Calibration Block ---
            const float ADC_REF = 3.6f;
            const float GAIN_V_PER_A = 5.0f; 
            const float CAL_FACTOR = 1.0f;   
            
            // BIAS SETTING: Set to 0.0 for unipolar, 1.8 for mid-point biased hardware
            const float ADC_BIAS_VOLTS = 0.0f; 
            
            float voltage_at_pin = (raw_adc / 1023.0f) * ADC_REF;
            float current_amps = ((voltage_at_pin - ADC_BIAS_VOLTS) / GAIN_V_PER_A) * CAL_FACTOR;
            
            // Update VCA Load Estimation (Leaky Peak Detector)
            if (current_amps > g_settings.vca_load_estimation) {
                g_settings.vca_load_estimation = current_amps;
            } else {
                g_settings.vca_load_estimation *= 0.9999f; 
            }

            // Estimate drive voltage from PWM
            float voltage_est = (float)PwmTactor.GetChannelPointer(active_channel)[0] * (3.7f / 512.0f);
            
            g_dlog.Log(voltage_est, current_amps);
        }

        // Update PWM buffers
        for(uint32_t channel = 0; channel < g_stream->channels(); channel++) {
            if(channel==active_channel) {
                uint16_t* cp = PwmTactor.GetChannelPointer(channel);
                g_stream->set_chan_samples(cp, channel);
            } else {
                PwmTactor.SilenceChannel(channel, g_volume_lvl);
            }
        }
    } else {
        for(uint32_t i = 0; i < g_settings.default_channels; i++)
            PwmTactor.SilenceChannel(i, g_volume_lvl);
    }    
}

void loop() {
  // Continuous Load Output Logic
  static unsigned long last_load_print = 0;
  if (g_continuous_load_output && (millis() - last_load_print > 100)) {
      last_load_print = millis();
      Serial.print("vca_load_estimation:");
      Serial.println(g_settings.vca_load_estimation, 4);
  }

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
      g_continuous_load_output = false; // Stop continuous output on '0'
      Serial.write('0');
    }
    else if (c == 'T') {
      ToggleStream();
      Serial.write('T');
    }
    else if (c == 'L') {
      Serial.write('L');
    }
    else if (c == 'w') { // Lowercase 'w' for continuous load output
      g_continuous_load_output = !g_continuous_load_output;
      if (g_continuous_load_output) Serial.println("Continuous load output enabled");
      else Serial.println("Continuous load output disabled");
    }
    else if (c == 'S') {  // Added 'S' command to get version
      Serial.print("FW Version: ");
      Serial.println(FIRMWARE_VERSION);
    }
    else if (c == 'C') { // Added 'C' command to dump current log
        g_dlog.PrintRawData();
        g_dlog.Reset(); // Clear after dumping
    }
    else if (c == 'W') { // 'W' for Weight/Work/Load estimation
        Serial.print("vca_load_estimation:");
        Serial.println(g_settings.vca_load_estimation, 4);
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
        // Reset the current log when starting a new stream to capture from the beginning
        g_dlog.Reset();
        g_current_filter.Reset();  // Reset filter to avoid startup transients 
        g_settings.vca_load_estimation = 0.0f; // Reset load estimation for new stream
        
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
    