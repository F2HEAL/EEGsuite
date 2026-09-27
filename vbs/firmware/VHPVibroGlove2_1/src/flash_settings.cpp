#include "flash_settings.h"

#include <Arduino.h>
#include <Adafruit_SPIFlash.h>
#include <SPI.h>
#include <SdFat.h>
#include <stdlib.h>
#include <string.h>

namespace audio_tactile {

AudioToTactileFlashSettings FlashSettings;

namespace {
Adafruit_FlashTransport_QSPI g_flash_transport;
Adafruit_SPIFlash g_flash(&g_flash_transport);
FatFileSystem g_flash_file_system;
File g_flash_file;

void ParseSettingLine(const char* line, Settings* settings) {
  char key[32] = {0};
  char value[32] = {0};
  if (sscanf(line, "%31[^=]=%31s", key, value) != 2) {
    return;
  }

  const int parsed_value = atoi(value);
  if (strcmp(key, "volume") == 0) {
    settings->volume = static_cast<uint8_t>(parsed_value);
  } else if (strcmp(key, "vol_amplitude") == 0) {
    settings->vol_amplitude = static_cast<uint32_t>(parsed_value);
  } else if (strcmp(key, "stimfreq") == 0) {
    settings->stimfreq = static_cast<uint32_t>(parsed_value);
  } else if (strcmp(key, "stimduration") == 0) {
    settings->stimduration = static_cast<uint32_t>(parsed_value);
  } else if (strcmp(key, "cycleperiod") == 0) {
    settings->cycleperiod = static_cast<uint32_t>(parsed_value);
  } else if (strcmp(key, "pauzecycleperiod") == 0) {
    settings->pauzecycleperiod = static_cast<uint32_t>(parsed_value);
  } else if (strcmp(key, "pauzedcycles") == 0) {
    settings->pauzedcycles = static_cast<uint32_t>(parsed_value);
  } else if (strcmp(key, "jitter") == 0) {
    settings->jitter = static_cast<uint16_t>(parsed_value);
  } else if (strcmp(key, "test_mode") == 0) {
    settings->test_mode = (parsed_value != 0);
  } else if (strcmp(key, "single_channel") == 0) {
    settings->single_channel = static_cast<uint16_t>(parsed_value);
  } else if (strcmp(key, "chan8") == 0) {
    settings->chan8 = (parsed_value != 0);
  } else if (strcmp(key, "start_stream_on_power_on") == 0) {
    settings->start_stream_on_power_on = (parsed_value != 0);
  }
}
}  // namespace

AudioToTactileFlashSettings::AudioToTactileFlashSettings()
    : have_file_system_(false) {}

void AudioToTactileFlashSettings::Initialize() {
  g_flash.begin();
  have_file_system_ = g_flash_file_system.begin(&g_flash);
}

bool AudioToTactileFlashSettings::ReadSettingsFile(Settings* settings) {
  if (!have_file_system_ ||
      !(g_flash_file = g_flash_file_system.open(kFlashSettingsFile, FILE_READ))) {
    return false;
  }

  char line[128];
  while (g_flash_file.available()) {
    const int count = g_flash_file.fgets(line, sizeof(line));
    if (count <= 0) {
      break;
    }
    line[count] = '\0';
    ParseSettingLine(line, settings);
  }

  g_flash_file.close();
  last_written_settings_ = *settings;
  Serial.println("FlashSettings: Read " kFlashSettingsFile);
  return true;
}

bool AudioToTactileFlashSettings::WriteSettingsFile(const Settings& settings) {
  if (last_written_settings_ == settings) { return true; }

  if (!have_file_system_ ||
      !(g_flash_file = g_flash_file_system.open(
          kFlashSettingsFile,
          O_WRONLY | O_CREAT | O_TRUNC))) {
    Serial.println("Unknown error writing to flash");
    return false;
  }

  char line[128];
  snprintf(line, sizeof(line), "volume=%u\n", settings.volume);
  g_flash_file.write(line);
  snprintf(line, sizeof(line), "vol_amplitude=%u\n", settings.vol_amplitude);
  g_flash_file.write(line);
  snprintf(line, sizeof(line), "stimfreq=%u\n", settings.stimfreq);
  g_flash_file.write(line);
  snprintf(line, sizeof(line), "stimduration=%u\n", settings.stimduration);
  g_flash_file.write(line);
  snprintf(line, sizeof(line), "cycleperiod=%u\n", settings.cycleperiod);
  g_flash_file.write(line);
  snprintf(line, sizeof(line), "pauzecycleperiod=%u\n", settings.pauzecycleperiod);
  g_flash_file.write(line);
  snprintf(line, sizeof(line), "pauzedcycles=%u\n", settings.pauzedcycles);
  g_flash_file.write(line);
  snprintf(line, sizeof(line), "jitter=%u\n", settings.jitter);
  g_flash_file.write(line);
  snprintf(line, sizeof(line), "test_mode=%u\n", settings.test_mode ? 1u : 0u);
  g_flash_file.write(line);
  snprintf(line, sizeof(line), "single_channel=%u\n", settings.single_channel);
  g_flash_file.write(line);
  snprintf(line, sizeof(line), "chan8=%u\n", settings.chan8 ? 1u : 0u);
  g_flash_file.write(line);
  snprintf(line, sizeof(line), "start_stream_on_power_on=%u\n", settings.start_stream_on_power_on ? 1u : 0u);
  g_flash_file.write(line);

  g_flash_file.close();
  last_written_settings_ = settings;
  Serial.println("FlashSettings: Wrote " kFlashSettingsFile);
  return true;
}

}  // namespace audio_tactile
