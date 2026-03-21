# plot_manager.py
"""
Handles EEG data plotting, PSD calculation, and real-time updates.
"""
import numpy as np
import logging
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QScrollArea, QCheckBox
import pyqtgraph as pg
from pyqtgraph import ViewBox

from scipy.signal import welch

from scipy.stats import kurtosis, skew

from modules.config_channels import CHANNEL_MAPPING, VIRTUAL_CHANNEL_NAME

import scipy.signal as signal





pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

# Channel mapping EEG Viewer RT (moved to config_channels.py)
#CHANNEL_MAPPING = {1: "T7", 2: "T8", 3: "C3", 4: "C4", 5: "FC3", 6: "FC4", 7: "CP3", 8: "CP4"} # FG_P 16/5
#CHANNEL_MAPPING = {1: "T7", 2: "T8", 5: "C3", 6: "C4", 9: "FC3", 10: "FC4", 13: "CP3", 14: "CP4"}
#CHANNEL_MAPPING = {1: "T7", 2: "C3", 5: "T8", 6: "FC4", 9: "FC3", 10: "C4", 13: "CP3", 14: "CP4"} # FG_P 06/11

def safe_get_band_power(freqs, psd, freq_start, freq_end):
    mask = (freqs >= freq_start) & (freqs <= freq_end)
    if not np.any(mask):
        return 0.0
    return np.trapz(psd[mask], freqs[mask])
#    return np.trapezoid(psd[mask], freqs[mask])


def spectral_entropy(psd_values):
    psd_values = np.array(psd_values, dtype=np.float64)
    psd_norm = psd_values / (np.sum(psd_values) + 1e-10)
    return -np.sum(psd_norm * np.log2(psd_norm + 1e-10))


def line_noise_ratio(freqs, psd, target_freq=50.0, tol=1.0):
    band = (freqs > target_freq - tol) & (freqs < target_freq + tol)
    total_power = np.sum(psd[(freqs > 1) & (freqs < 45)]) + 1e-10
    line_power = np.sum(psd[band])
    return line_power / total_power


class PlotManager:
    def __init__(self, ui, board_shim, filters, exg_channels, virtual_index, sampling_rate, main_widget, channel_names=None, data_fetchers=None):
        self.ui = ui
        self.board_shim = board_shim
        self.filters = filters
        self.exg_channels = exg_channels
        self.virtual_index = virtual_index
        self.sampling_rate = sampling_rate
        self.main_widget = main_widget
        self.channel_names = channel_names
        self.data_fetchers = data_fetchers
        self.psd_size = max(64, min(1024, 2 ** int(np.log2(sampling_rate))))
        self.num_points = int(sampling_rate * 4)
        self.pens_used = []  
        self._init_plot()  # <- this builds the GUI on the provided main_widget

    def _init_plot(self):
        #self.main_widget = self.ui.control_container.parent()

        # Time plots
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.time_plot_container = QWidget()
        self.time_plot_layout = QVBoxLayout()
        self.time_plot_container.setLayout(self.time_plot_layout)
        self.scroll.setWidget(self.time_plot_container)

        # Create plots and labels
        self.curves, self.labels, self.psd_curves, self.channel_checkboxes = [], [], [], []
        self.channel_widgets = []

        self.pens = [pg.mkPen(c, width=2) for c in ['#A54E4E', '#A473B6', '#5B45A4', '#2079D2', '#32B798', '#2FA537', '#9DA52F', '#A57E2F']]
        logging.debug("EXG channel list: %s", self.exg_channels)

        for i in range(len(self.exg_channels)):
            if self.channel_names:
                ch_name = self.channel_names[i]
            else:
                channel_num = self.exg_channels[i]
                ch_name = VIRTUAL_CHANNEL_NAME if i == self.virtual_index else CHANNEL_MAPPING.get(channel_num, f"CH{channel_num}")


            channel_widget = QWidget()
            layout = QVBoxLayout()

            plot = pg.PlotWidget()
            plot.setXRange(0, self.num_points)
            plot.enableAutoRange(axis='x', enable=False)
            plot.setMaximumHeight(100)
            plot.setLabel('left', f"{ch_name} (\u00B5V)")
            plot.showGrid(y=True)
            pen = pg.mkPen('blue', width=2, style=Qt.DashLine) if i == self.virtual_index else self.pens[i % len(self.pens)]
            curve = plot.plot(pen=pen)

            label1 = QLabel()
            label2 = QLabel()
            for lbl in [label1, label2]:
                lbl.setAlignment(Qt.AlignRight)
                lbl.setStyleSheet("font-size: 9pt")

            layout.addWidget(plot)
            layout.addWidget(label1)
            layout.addWidget(label2)
            channel_widget.setLayout(layout)

            self.time_plot_layout.addWidget(channel_widget)
            self.curves.append(curve)
            self.labels.append((label1, label2))
            self.channel_widgets.append(channel_widget)
            self.pens_used.append(pen)  # Store actual pen used


            cb = QCheckBox(ch_name)
            cb.setChecked(True)
            cb.stateChanged.connect(self._update_channel_visibility)
            self.channel_checkboxes.append(cb)

        self.ui.control_vbox.addWidget(QLabel("Channels ON/OFF"))
        cb_group = QWidget()
        cb_layout = QHBoxLayout()
        for cb in self.channel_checkboxes:
            cb_layout.addWidget(cb)
        cb_group.setLayout(cb_layout)
        self.ui.control_vbox.addWidget(cb_group)

        # PSD plot
        self.psd_plot_widget = pg.GraphicsLayoutWidget()
        self.psd_plot = self.psd_plot_widget.addPlot(title="Power Spectral Density (PSD)")
        self.psd_plot.setLogMode(False, True)
        self.psd_plot.setLabel('left', 'Power (\u00B5V²/Hz)')
        self.psd_plot.setLabel('bottom', 'Frequency (Hz)')
        self.psd_plot.showGrid(x=True, y=True)
#        self.psd_curves = [self.psd_plot.plot(pen=self.pens[i % len(self.pens)]) for i in range(len(self.exg_channels))]
        self.psd_curves = [self.psd_plot.plot(pen=pen) for pen in self.pens_used]

        # Band power bar chart
        self.band_plot_widget = pg.GraphicsLayoutWidget()
        self.band_plot = self.band_plot_widget.addPlot(title="Band Power")
        self.band_plot.setLabel('left', 'Power (%)')
        self.band_plot.setLabel('bottom', 'Frequency Bands')
        self.band_plot.getAxis('bottom').setTicks([[ (i+1, label) for i, label in enumerate(['\u03B4', '\u03B8', '\u03B1', '\u03B2', 'h-\u03B2', '\u03B3', 'h-\u03B3']) ]])
        self.band_plot.showGrid(x=True, y=True)
        self.bar = pg.BarGraphItem(x=list(range(1, 8)), height=[0]*7, width=0.8)
        self.band_plot.addItem(self.bar)

        # Layout all widgets
        layout = QHBoxLayout()
        layout.addWidget(self.scroll, stretch=3)

        right_panel = QVBoxLayout()
        right_panel.addWidget(self.ui.control_container)
        right_panel.addWidget(self.psd_plot_widget)
        right_panel.addWidget(self.band_plot_widget)
        container = QWidget()
        container.setLayout(right_panel)

        layout.addWidget(container, stretch=2)
        self.main_widget.setLayout(layout)

        # Y-axis sync
        self.ui.y_apply_btn.clicked.connect(self._apply_y_range)
        self.ui.y_auto_checkbox.stateChanged.connect(self._apply_y_range)
        self.ui.psd_y_apply_btn.clicked.connect(self._apply_psd_y_range)
        self.ui.psd_y_auto_checkbox.stateChanged.connect(self._apply_psd_y_range)

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(250)

    def _apply_y_range(self):
        auto = self.ui.y_auto_checkbox.isChecked()
        for curve in self.curves:
            vb = curve.getViewBox()
            vb.enableAutoRange(ViewBox.YAxis, enable=auto)
            if not auto:
                try:
                    ymin = float(self.ui.y_min_input.text())
                    ymax = float(self.ui.y_max_input.text())
                    vb.setYRange(ymin, ymax)
                except ValueError:
                    pass

    def _apply_psd_y_range(self):
        auto = self.ui.psd_y_auto_checkbox.isChecked()
        self.psd_plot.enableAutoRange(axis='y', enable=auto)
        if not auto:
            try:
                ymin = float(self.ui.psd_y_min_input.text())
                ymax = float(self.ui.psd_y_max_input.text())
                self.psd_plot.setYRange(ymin, ymax)
            except ValueError:
                pass

    def _update_channel_visibility(self):
        for i, (cb, widget) in enumerate(zip(self.channel_checkboxes, self.channel_widgets)):
            widget.setVisible(cb.isChecked())
            self.curves[i].setVisible(cb.isChecked())
            self.psd_curves[i].setVisible(cb.isChecked())

    def update(self):
        data = self.board_shim.get_current_board_data(self.num_points)
        avg_bands = [0] * 7

        for i in range(len(self.exg_channels)):
            if not self.channel_checkboxes[i].isChecked():
                self.curves[i].setData([])
                self.psd_curves[i].setData([], [])
                continue

            if self.data_fetchers and self.data_fetchers[i]:
                sig = self.data_fetchers[i](data)
            else:
                sig = data[self.exg_channels[i]] if i != self.virtual_index else data[self.exg_channels[2]] - data[self.exg_channels[3]]
            
            sig = self.filters.apply_filters(sig, i)
            self.curves[i].setData(sig.tolist())

            ptp = max(sig) - min(sig)
            rms = np.sqrt(np.mean(sig**2))
            dc = np.mean(sig)
            flat = np.mean(np.abs(np.diff(sig)) < 3)
            k = kurtosis(sig)
            s = skew(sig)

            color = "green"
            status = "OK"
            if ptp < 10 or flat > 0.95:
                status, color = "FLAT", "gray"
            elif ptp > 1000:
                status, color = "NOISY", "red"
            elif rms > 100:
                status, color = "HIGH RMS", "darkgreen"
            elif k > 10:
                status, color = "SPIKY", "orange"

            label1, label2 = self.labels[i]
            label1.setText(f"<span style='color:{color}'>PTP: {ptp:.1f} | RMS: {rms:.1f} | DC: {dc:.1f} | Flat: {flat:.2f} | Kurtosis: {k:.2f} | Skew: {s:.2f} | {status}</span>")

            if sig.shape[0] > self.psd_size:
                freqs, psd = welch(sig, fs=self.sampling_rate, nperseg=self.psd_size, window='blackmanharris')
                self.psd_curves[i].setData(freqs[:300], psd[:300])

                delta = safe_get_band_power(freqs, psd, 1.0, 4.0)
                theta = safe_get_band_power(freqs, psd, 4.0, 8.0)
                alpha = safe_get_band_power(freqs, psd, 8.0, 13.0)
                beta = safe_get_band_power(freqs, psd, 13.0, 20.0)
                h_beta = safe_get_band_power(freqs, psd, 20.0, 30.0)
                gamma = safe_get_band_power(freqs, psd, 30.0, 60.0)
                h_gamma = safe_get_band_power(freqs, psd, 60.0, 100.0)

                avg_bands = [sum(x) for x in zip(avg_bands, [delta, theta, alpha, beta, h_beta, gamma, h_gamma])]

                ln_ratio = line_noise_ratio(freqs, psd)
                muscle_ratio = (gamma + h_gamma) / (alpha + beta + 1e-10)
                entropy = spectral_entropy(psd)

                status2, color2 = "UNKNOWN", "black"
                if 2.5 < entropy < 4.8:
                    status2, color2 = "human EEG alike", "green"
                elif entropy > 4.8:
                    status2, color2 = "RANDOM NOISE alike", "red"

                label2.setText(f"<span style='color:{color2}'>LNR: {ln_ratio:.2f} | MR: {muscle_ratio:.2f} | Ent: {entropy:.2f} | δ: {delta:.1f} | θ: {theta:.1f} | α: {alpha:.1f} | β: {beta:.1f} | h-β: {h_beta:.1f} | γ: {gamma:.1f} | h-γ: {h_gamma:.1f} | {status2}</span>")

        total_power = sum(avg_bands) + 1e-10
        norm_bands = [x / total_power * 100 for x in avg_bands]
        self.bar.setOpts(height=norm_bands)
