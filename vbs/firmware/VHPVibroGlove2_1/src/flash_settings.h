// Copyright 2024
// Minimal flash settings persistence for the VHP Vibro Glove firmware.

#ifndef VHPVIBROGLOVE2_1_SRC_FLASH_SETTINGS_H_
#define VHPVIBROGLOVE2_1_SRC_FLASH_SETTINGS_H_

#include "Settings.hpp"

// Path for the settings file. Must be a valid 8.3 FAT filename.
#define kFlashSettingsFile "settings.cfg"

namespace audio_tactile {

using Settings = ::Settings;

enum {
  kFlashWriteSuccess = 0,
  kFlashWriteUnkownError = 1,
  kFlashWriteErrorNotFormatted = 2,
};

class AudioToTactileFlashSettings {
 public:
  AudioToTactileFlashSettings();

  void Initialize();

  bool have_file_system() const { return have_file_system_; }

  bool ReadSettingsFile(Settings* settings);

  bool WriteSettingsFile(const Settings& settings);

 private:
  Settings last_written_settings_;
  bool have_file_system_;
};

extern AudioToTactileFlashSettings FlashSettings;

}  // namespace audio_tactile

#endif  // VHPVIBROGLOVE2_1_SRC_FLASH_SETTINGS_H_
