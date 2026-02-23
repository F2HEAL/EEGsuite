import os
import logging
import pandas as pd
import numpy as np
import mne
import matplotlib.pyplot as plt
import json
import uuid
import html
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class SimpleReport:
    """Native HTML report generator for EEGsuite."""
    
    def __init__(self, output_dir: Path, title: str = "EEG Report"):
        self.output_dir = output_dir
        self.title = title
        self.sections = []
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "img").mkdir(parents=True, exist_ok=True)
    
    def add_section(self, title: str, content: Any = None, plot: Any = None, plot_caption: str = None):
        self.sections.append({
            'title': title,
            'content': content,
            'plot': plot,
            'plot_caption': plot_caption
        })
    
    def save(self, filename: str = "report.html") -> Path:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{self.title}</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background-color: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                h2 {{ color: #2980b9; margin-top: 30px; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
                .section {{ margin: 25px 0; }}
                .plot {{ max-width: 100%; height: auto; margin: 20px 0; border: 1px solid #ddd; }}
                .caption {{ font-style: italic; color: #7f8c8d; text-align: center; margin-bottom: 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ecf0f1; padding: 12px; text-align: left; }}
                th {{ background-color: #3498db; color: white; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                pre {{ background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 5px solid #3498db; overflow-x: auto; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{self.title}</h1>
        """
        
        for section in self.sections:
            html_content += f"<div class='section'><h2>{html.escape(section['title'])}</h2>"
            
            content = section['content']
            if content is not None:
                if isinstance(content, pd.DataFrame):
                    html_content += content.to_html(classes='dataframe') if not content.empty else "<p>No data</p>"
                elif isinstance(content, dict):
                    html_content += f"<pre>{html.escape(json.dumps(content, indent=2))}</pre>"
                elif isinstance(content, str):
                    html_content += f"<p>{html.escape(content)}</p>"
                else:
                    html_content += f"<pre>{html.escape(str(content))}</pre>"
            
            if section['plot'] is not None:
                plot_filename = f"plot_{uuid.uuid4().hex}.png"
                plot_path = self.output_dir / "img" / plot_filename
                section['plot'].savefig(plot_path, bbox_inches='tight', dpi=100)
                plt.close(section['plot'])
                
                html_content += f'<img src="img/{plot_filename}" class="plot">'
                if section['plot_caption']:
                    html_content += f'<p class="caption">{html.escape(section["plot_caption"])}</p>'
            
            html_content += "</div>"
        
        html_content += "</div></body></html>"
        
        output_path = self.output_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return output_path

class EEGVisualizer:
    """Native Offline Analysis tool for EEGsuite."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sfreq = 0.0
        self.raw = None

    def load_data(self, csv_file: Path):
        """Loads CSV data and creates MNE object."""
        df = pd.read_csv(csv_file, header=None)
        
        # Format: [timestamp, Ch1...Ch32, marker]
        timestamps = df.iloc[:, 0].values
        eeg_data = df.iloc[:, 1:33].values.T * 1e6 # To microvolts
        markers = df.iloc[:, 33].values
        
        # Calculate sfreq
        if len(timestamps) > 1:
            self.sfreq = 1.0 / np.median(np.diff(timestamps))
        else:
            self.sfreq = 512.0 # Fallback
            
        ch_names = self.config.get('channels', [f'Ch{i+1}' for i in range(32)])
        if len(ch_names) > 32:
            ch_names = ch_names[:32]
            
        info = mne.create_info(ch_names=ch_names, sfreq=self.sfreq, ch_types='eeg')
        self.raw = mne.io.RawArray(eeg_data, info)
        
        # Add annotations
        self._add_annotations(timestamps, markers)

        # Apply global channel picking
        picks = self.config.get('pick_channels')
        if picks:
            valid_picks = [ch for ch in picks if ch in self.raw.ch_names]
            if valid_picks:
                self.raw.pick_channels(valid_picks)
                logger.info("Global channel pick applied: %s", valid_picks)

    def _add_annotations(self, timestamps, markers):
        valid_mask = ~np.isnan(markers)
        if not np.any(valid_mask):
            return
            
        marker_indices = np.where(valid_mask)[0]
        marker_values = markers[valid_mask]
        onsets = timestamps[marker_indices] - timestamps[0]
        
        marker_map = {
            0.0: 'Stimulation READY [0]',
            1.0: 'Stimulation ON [1]',
            11.0: 'Stimulation OFF [11]',
            3.0: 'Baseline_VHP_OFF [3]',
            33.0: 'Baseline_VHP_ON [33]',
            31.0: 'Baseline_NoContact [31]',
            333.0: 'Baseline_PreSweep [333]'
        }
        
        descriptions = [marker_map.get(m, f"Event_{int(m)}") for m in marker_values]
        annots = mne.Annotations(onset=onsets, duration=[0.01]*len(onsets), description=descriptions)
        self.raw.set_annotations(annots)

    def create_timeseries_plot(self, start: float, duration: float):
        """Creates a timeseries plot with markers."""
        t_max = self.raw.times[-1]
        t_start = max(0, min(start, t_max - 0.1))
        t_end = min(t_start + duration, t_max)
        
        # Simplified slice for plotting
        start_idx, stop_idx = self.raw.time_as_index([t_start, t_end])
        data, times = self.raw[:, start_idx:stop_idx]
        
        fig, ax = plt.subplots(figsize=(15, 8))
        # Plot only first channel for clarity
        ax.plot(times, data[0], color='black', lw=0.5, alpha=0.7)
        ax.set_title(f"EEG Timeseries (Channel 1) - {t_start:.1f}s to {t_end:.1f}s")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Amplitude (µV)")
        
        # Add event markers with the correct labels
        if self.raw.annotations:
            for annot in self.raw.annotations:
                onset = annot['onset']
                if t_start <= onset <= t_end:
                    desc = annot['description']
                    color = 'green' if '[1]' in desc else 'red' if '[11]' in desc else 'orange'
                    ax.axvline(onset, color=color, linestyle='--', alpha=0.8)
                    ax.text(onset, ax.get_ylim()[1], desc, 
                            rotation=90, va='top', fontsize=8,
                            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7))
        
        plt.tight_layout()
        return fig

    def create_psd_plot(self):
        """Create PSD plot"""
        fmin, fmax = self.config.get('psd_fmin', 1.0), self.config.get('psd_fmax', 60.0)
        try:
            psd = self.raw.compute_psd(fmin=fmin, fmax=fmax, method='welch')
            fig = psd.plot(average=True, show=False)
            fig.axes[0].set_title(f'Power Spectral Density ({fmin}-{fmax} Hz)')
            return fig
        except Exception as e:
            logger.error("Error creating PSD plot: %s", e)
            return None

    def create_erp_plot(self, event_type: str = 'Stimulation ON [1]'):
        """Create ERP plot for specific event type on selected channels."""
        if not self.raw.annotations:
            logger.warning("No annotations found in raw data.")
            return None
        
        events, event_id = mne.events_from_annotations(self.raw)
        logger.info("Found event IDs: %s", event_id)
        
        if event_type not in event_id:
            logger.warning("Event type '%s' not found in data.", event_type)
            return None
            
        target_id = event_id[event_type]
        n_occurrences = np.sum(events[:, 2] == target_id)
        logger.info("Event '%s' (ID %d) occurs %d times in annotations.", 
                    event_type, target_id, n_occurrences)
            
        # Get settings from config
        tmax = self.config.get('erp_duration', 1.0)
                
        try:
            # We use the specific ID for this event type
            epochs = mne.Epochs(self.raw, events, event_id=target_id,
                               tmin=-0.2, tmax=tmax, baseline=(-0.2, 0),
                               preload=True, verbose=True,
                               on_missing='warning')
            
            # Log why epochs were dropped
            if len(epochs.drop_log) > 0:
                for i, log in enumerate(epochs.drop_log):
                    if log:
                        logger.warning("Epoch %d dropped because: %s", i, log)

            logger.info("Created %d epochs for '%s'.", len(epochs), event_type)
            
            if len(epochs) == 0:
                return None
            evoked = epochs.average()
            
            # Use evoked.plot() but handle title manually to avoid NameError
            fig = evoked.plot(show=False)
            ch_info = ", ".join(evoked.ch_names)
            fig.suptitle(f'ERP: {event_type} (n={len(epochs)}, Channels: {ch_info})', y=1.02)
            return fig
        except Exception as e:
            logger.error("Error creating ERP plot for %s: %s", event_type, e)
            return None

    def create_frequency_band_plot(self, band_name: str, fmin: float, fmax: float):
        """Create plot for specific frequency band."""
        try:
            psd = self.raw.compute_psd(fmin=fmin, fmax=fmax, method='welch')
            fig = psd.plot(average=False, show=False, spatial_colors=False)
            fig.axes[0].set_title(f'{band_name} ({fmin}-{fmax} Hz) Power by Channel')
            return fig
        except Exception as e:
            logger.error("Error creating %s plot: %s", band_name, e)
            return None

    def create_stim_comparison_plot(self):
        """Compare Stimulation ON vs Baseline1."""
        if not self.raw.annotations:
            return None
            
        try:
            # Find first Stim ON and first Baseline1
            stim_onset = None
            base_onset = None
            for onset, desc in zip(self.raw.annotations.onset, self.raw.annotations.description):
                if 'Stimulation ON [1]' in desc and stim_onset is None:
                    stim_onset = onset
                if 'Baseline_VHP_OFF [3]' in desc and base_onset is None:
                    base_onset = onset
            
            if stim_onset is None or base_onset is None:
                return None
                
            duration = 5.0 # Compare 5 seconds
            raw_stim = self.raw.copy().crop(tmin=stim_onset, tmax=min(stim_onset + duration, self.raw.times[-1]))
            raw_base = self.raw.copy().crop(tmin=base_onset, tmax=min(base_onset + duration, self.raw.times[-1]))
            
            psd_stim = raw_stim.compute_psd(fmin=1, fmax=55, method='welch')
            psd_base = raw_base.compute_psd(fmin=1, fmax=55, method='welch')
            
            fig, ax = plt.subplots(figsize=(10, 6))
            freqs = psd_stim.freqs
            data_stim = 10 * np.log10(psd_stim.get_data().mean(axis=0))
            data_base = 10 * np.log10(psd_base.get_data().mean(axis=0))
            
            ax.plot(freqs, data_base, color='gray', alpha=0.6, label='Baseline (VHP OFF)')
            ax.plot(freqs, data_stim, color='green', label='Stimulation ON', linewidth=2)
            ax.set_title('Stimulation vs. Baseline Power Spectrum')
            ax.set_xlabel('Frequency (Hz)')
            ax.set_ylabel('Power (dB)')
            ax.legend()
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            return fig
        except Exception as e:
            logger.error("Error creating comparison plot: %s", e)
            return None

    def generate_report(self, csv_file: Path, output_dir: Path, start: float, duration: float):
        """Generates the full HTML report."""
        report = SimpleReport(output_dir, title=f"EEG Analysis: {csv_file.name}")
        
        # 1. Info section
        info = {
            "File": str(csv_file),
            "Duration (s)": round(self.raw.times[-1], 2),
            "Sampling Rate (Hz)": round(self.sfreq, 2),
            "Channels": len(self.raw.ch_names),
            "Total Events": len(self.raw.annotations) if self.raw.annotations else 0
        }
        report.add_section("File Information", content=info)
        
        # 2. Timeseries section
        fig_ts = self.create_timeseries_plot(start, duration)
        report.add_section("Timeseries Analysis", plot=fig_ts, 
                          plot_caption=f"Segment from {start}s with {duration}s duration")
        
        # 3. PSD section
        fig_psd = self.create_psd_plot()
        if fig_psd:
            report.add_section("Power Spectral Density", plot=fig_psd,
                              plot_caption="Average power spectral density across all channels")
            
        # 4. ERP section
        fig_erp = self.create_erp_plot('Stimulation ON [1]')
        if fig_erp:
            report.add_section("Event-Related Potential (ERP)", plot=fig_erp,
                              plot_caption="ERP for Stimulation ON [1] events")
            
        # 5. Stimulation Comparison
        fig_comp = self.create_stim_comparison_plot()
        if fig_comp:
            report.add_section("Stimulation vs Baseline", plot=fig_comp,
                              plot_caption="Comparison of PSD: Stimulation ON (Green) vs Baseline (Gray)")
            
        # 6. Frequency Bands
        freq_bands = {
            'Alpha (8-13 Hz)': (8, 13),
            'Beta (13-30 Hz)': (13, 30),
            'Gamma (30-45 Hz)': (30, 45)
        }
        for band_name, (fmin, fmax) in freq_bands.items():
            fig_band = self.create_frequency_band_plot(band_name, fmin, fmax)
            if fig_band:
                report.add_section(f"Frequency Band: {band_name}", plot=fig_band,
                                  plot_caption=f"Power distribution for {band_name}")
        
        report_path = report.save(f"{csv_file.stem}_report.html")
        return report_path
