import io
import sys
import time

import folium
import sqlite3
import pandas as pd
from PySide2 import QtWidgets, QtWebEngineWidgets, QtCore
from dataclasses import dataclass
from shapely.geometry import shape
import geojson
import geojsoncontour
import numpy
import branca
from scipy.interpolate import griddata
import matplotlib.pyplot as plt
import math
import scipy as sp
import scipy.ndimage

start_coords = [54.12, 8.37]
min_time = QtCore.QDateTime(QtCore.QDate(2013, 1, 1), QtCore.QTime(0, 0))
max_time = QtCore.QDateTime(QtCore.QDate(2013, 12, 31), QtCore.QTime(23, 59))

# start time when launching the program
begin_start_time = QtCore.QDateTime(QtCore.QDate(2013, 6, 1), QtCore.QTime(0, 0))


@dataclass
class map_data:
    data_obs: pd.DataFrame = pd.DataFrame()
    data_bw: pd.DataFrame = pd.DataFrame()
    data_fw: pd.DataFrame = pd.DataFrame()


# build a string compatible to the data we have from a QDateTime object
def datetime_to_timestring(date_time: QtCore.QDateTime):
    time_str = date_time.date().year().__str__()
    if date_time.date().month() < 10:
        time_str += "0"
    time_str += date_time.date().month().__str__()
    if date_time.date().day() < 10:
        time_str += "0"
    time_str += date_time.date().day().__str__()
    if date_time.time().hour() < 10:
        time_str += "0"
    time_str += date_time.time().hour().__str__()
    if date_time.time().minute() < 10:
        time_str += "0"
    time_str += date_time.time().minute().__str__()
    return time_str


# build QDateTime from time string
def timestring_to_datetime(time_str: str):
    date_time = QtCore.QDateTime()
    date_time.setDate(QtCore.QDate(
        int(time_str[0:4]),
        int(time_str[4:6]),
        int(time_str[6:8])
    ))
    date_time.setTime(QtCore.QTime(
        int(time_str[8:10]),
        int(time_str[10:12])
    ))
    return date_time


# for debugging
def write_html_to_file(html: str):
    f = open("Test.html", "a")
    f.truncate(0)
    f.write(html)
    f.close()


def create_salinity_df(md: map_data):
    # construct dataframe with salinity
    df = md.data_obs[['latitude', 'longitude', 'sensor_1']]
    md.data_bw = md.data_bw[['latitude', 'longitude', 'sensor_1']]
    md.data_fw = md.data_fw[['latitude', 'longitude', 'sensor_1']]

    df = df.append(md.data_bw)
    df = df.append(md.data_fw)

    return df


class map_view(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.update_button = QtWidgets.QPushButton("Update")
        self.next_day_button = QtWidgets.QPushButton(">")
        self.prev_day_button = QtWidgets.QPushButton("<")
        self.display_points_checkbox = QtWidgets.QCheckBox()
        self.gaussfilter_label = QtWidgets.QLabel("Smoothening: ")
        self.gaussfilter_spinbox = QtWidgets.QSpinBox()
        self.salinity_spinbox = QtWidgets.QDoubleSpinBox()
        self.date_label = QtWidgets.QLabel()
        self.date_label.setFixedHeight(20)
        self.fol_map = folium.Map(location=start_coords, zoom_start=10)
        self.web_view = QtWebEngineWidgets.QWebEngineView()
        self.web_view.loadFinished.connect(lambda: self.update_finished())
        self.start_datetime_edit = QtWidgets.QDateTimeEdit()
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.runtime_ds = map_data()

        print("started loading...")
        start_time = time.time()
        self.read_db()
        self.read_polygon()
        print("loading done in " + str(time.time() - start_time) + " seconds")

        self.setCentralWidget(self.create_gui())

    # put all db data into a runtime data structure
    def read_db(self):
        db = sqlite3.connect("data/data_test.db")
        query_obs = "SELECT * FROM OBS"
        self.runtime_ds.data_obs = pd.read_sql_query(query_obs, db)
        query_bw = "SELECT * FROM BW"
        self.runtime_ds.data_bw = pd.read_sql_query(query_bw, db)
        query_fw = "SELECT * FROM FW"
        self.runtime_ds.data_fw = pd.read_sql_query(query_fw, db)
        db.close()

        # get min and max sal values
        self.sal_max_global = math.ceil(max(self.runtime_ds.data_obs['sensor_1'].max(),
                                            self.runtime_ds.data_bw['sensor_1'].max(),
                                            self.runtime_ds.data_fw['sensor_1'].max()))
        self.sal_min_global = math.floor(min(self.runtime_ds.data_obs['sensor_1'].min(),
                                             self.runtime_ds.data_bw['sensor_1'].min(),
                                             self.runtime_ds.data_fw['sensor_1'].min()))

    # read polygon data needed to construct visualizations
    def read_polygon(self):
        with open("data/GermanyPolygon.json") as f:
            gj = geojson.load(f)
        self.ger_polygon = shape(gj)

    # returns an object (currently "struct" of dataframes) which contains the data relevant for the given time
    def get_data_for_time_range(self, start_datetime: QtCore.QDateTime, end_datetime: QtCore.QDateTime):
        start_time_str = datetime_to_timestring(start_datetime)
        end_time_str = datetime_to_timestring(end_datetime)

        m_data = map_data()

        m_data.data_obs = self.runtime_ds.data_obs[
            self.runtime_ds.data_obs["time"].between(str.encode(start_time_str), str.encode(end_time_str))]
        m_data.data_bw = self.runtime_ds.data_bw[
            self.runtime_ds.data_bw["initial_time"].between(int(start_time_str), int(end_time_str))]
        m_data.data_fw = self.runtime_ds.data_fw[
            self.runtime_ds.data_fw["initial_time"].between(int(start_time_str), int(end_time_str))]

        return m_data

    # update map when new time was selected
    def update_map(self):
        print("started updating...")
        start_time = time.time()
        # set label to updating
        self.date_label.setText("Updating...")

        # deactivate UI
        self.start_datetime_edit.setEnabled(False)
        self.prev_day_button.setEnabled(False)
        self.next_day_button.setEnabled(False)
        self.update_button.setEnabled(False)

        QtCore.QCoreApplication.processEvents()

        start_datetime = self.start_datetime_edit.dateTime()
        end_datetime = self.start_datetime_edit.dateTime().addDays(1)

        # get data
        m_data = self.get_data_for_time_range(start_datetime, end_datetime)

        # rebuild map
        self.fol_map = folium.Map(location=start_coords, zoom_start=10)

        # draw contour map or circles
        sal_val = self.salinity_spinbox.value()
        if self.display_points_checkbox.isChecked():
            self.draw_points(m_data, sal_val)
        else:
            self.draw_contour_map(m_data, sal_val)

        # convert map to bytes and set html to webview
        data = io.BytesIO()
        self.fol_map.location = start_coords
        self.fol_map.save(data, close_file=False)
        html = data.getvalue().decode()
        self.web_view.setHtml(html)
        self.web_view.setVisible(True)

        # reactivate UI
        self.start_datetime_edit.setEnabled(True)
        self.prev_day_button.setEnabled(start_datetime.addDays(-1) >= min_time)
        self.next_day_button.setEnabled(start_datetime.addDays(1) <= max_time)
        self.update_button.setEnabled(True)

        print("updating done in " + str(time.time() - start_time) + " seconds")

    # add a marker for each measurement in the given color
    # If to many markers are created (around >5000), view will not render
    def draw_circle_markers(self, df: pd.DataFrame, color: str):
        for index, row in df.iterrows():
            coords = [row['latitude'], row['longitude']]
            folium.vector_layers.Circle(
                location=coords, radius=5, color=color, fill=True, fillOpacity=1.0, fillColor=color
            ).add_to(self.fol_map)

    def draw_points(self, md: map_data, sal_val: float):
        df = create_salinity_df(md)
        if df.empty:
            return

        # color stuff for the map
        sal_min = df['sensor_1'].min()
        sal_max = df['sensor_1'].max()
        # make sure salinity is between min and max
        if sal_val < sal_min:
            levels = [sal_min, sal_min + 0.5 * (sal_max - sal_min), sal_max]
            colors = ['#77b5d4', '#06618f']
        elif sal_val > sal_max:
            levels = [sal_min, sal_min + 0.5 * (sal_max - sal_min), sal_max]
            colors = ['#b5212f', '#de7881']
        else:
            levels = [sal_min, sal_min + 0.7 * (sal_val - sal_min), sal_val, sal_val + 0.3 * (sal_max - sal_val),
                      sal_max]
            colors = ['#b5212f', '#de7881', '#77b5d4', '#06618f']

        # scale values for colors
        col_map = branca.colormap.StepColormap(colors, vmin=sal_min, vmax=sal_max, index=levels)
        col_map.caption = "Salinity in PSU"

        # reduce dataframe size
        df = self.reduce_dataframe_size(df)

        for i in range(len(colors)):
            points = df[df['sensor_1'].between(levels[i], levels[i + 1])]
            self.draw_circle_markers(points, colors[i])

        # add legend
        self.fol_map.add_child(col_map)

    # TODO: rework this, use for demo purposes only !!!
    def reduce_dataframe_size(self, df: pd.DataFrame):
        target_size = 2000
        if len(df.index) < target_size:
            return df
        step_size = int(len(df.index) / target_size)
        df = df.iloc[::step_size, :]

        return df

    # draw contour map
    def draw_contour_map(self, md: map_data, sal_val: float):
        df = create_salinity_df(md)
        if df.empty:
            return

        # color stuff for the map
        sal_min = df['sensor_1'].min()
        sal_max = df['sensor_1'].max()
        # make sure salinity is between min and max
        if sal_val < sal_min:
            levels = [sal_min, sal_min + 0.3 * (sal_max - sal_min), sal_max]
            colors = ['#77b5d4', '#06618f']
        elif sal_val > sal_max:
            levels = [sal_min, sal_min + 0.7 * (sal_max - sal_min), sal_max]
            colors = ['#b5212f', '#de7881']
        else:
            levels = [sal_min, sal_min + 0.7 * (sal_val - sal_min), sal_val, sal_val + 0.3 * (sal_max - sal_val),
                      sal_max]
            colors = ['#b5212f', '#de7881', '#77b5d4', '#06618f']

        # scale values for colors
        col_map = branca.colormap.StepColormap(colors, vmin=sal_min, vmax=sal_max, index=levels)
        col_map.caption = "Salinity in PSU"

        # data to lists
        x_data = numpy.asarray(df.longitude.tolist())
        y_data = numpy.asarray(df.latitude.tolist())
        z_data = numpy.asarray(df.sensor_1.tolist())

        # build grid
        x_lin = numpy.linspace(numpy.min(x_data), numpy.max(x_data), 500)
        y_lin = numpy.linspace(numpy.min(y_data), numpy.max(y_data), 500)
        x_mesh, y_mesh = numpy.meshgrid(x_lin, y_lin)

        # add sensor values to grid
        z_mesh = griddata((x_data, y_data), z_data, (x_mesh, y_mesh), method='linear')

        # optional gaussian filter to smoothen contour map
        if self.gaussfilter_spinbox.value() > 0:
            gauss_strength = self.gaussfilter_spinbox.value()
            sigma = [gauss_strength, gauss_strength]
            z_mesh = sp.ndimage.filters.gaussian_filter(z_mesh, sigma, mode='constant')

        contourf = plt.contourf(x_mesh, y_mesh, z_mesh, levels, alpha=0.5, colors=colors, linestyles='None',
                                vmin=sal_min,
                                vmax=sal_max)

        gj = geojsoncontour.contourf_to_geojson(
            contourf=contourf,
            min_angle_deg=3.0,
            ndigits=5,
            stroke_width=1,
            fill_opacity=0.5)

        folium.GeoJson(
            gj,
            style_function=lambda x: {
                'color': x['properties']['stroke'],
                'weight': x['properties']['stroke-width'],
                'fillColor': x['properties']['fill'],
                'opacity': 0.6,
            }).add_to(self.fol_map)

        # add legend
        self.fol_map.add_child(col_map)

    def update_finished(self):
        # update label
        self.date_label.setText(
            "Currently displaying: " + self.start_datetime_edit.dateTime().toString() + " to " + self.start_datetime_edit.dateTime().addDays(1).toString())

    # create the GUI consisting of a map, a date-time selection field and an update button
    def create_gui(self):
        # build start date time edit
        self.start_datetime_edit.setDateTimeRange(min_time, max_time)
        self.start_datetime_edit.setCalendarPopup(1)
        self.start_datetime_edit.setDateTime(begin_start_time)
        self.start_datetime_edit.setMinimumWidth(120)
        self.start_datetime_edit.dateChanged.connect(lambda: self.update_map())
        self.prev_day_button.setFixedWidth(50)
        self.prev_day_button.setToolTip("Previous Day")
        self.prev_day_button.clicked.connect(lambda: self.start_datetime_edit.setDateTime(
            self.start_datetime_edit.dateTime().addDays(-1)))
        self.next_day_button.setFixedWidth(50)
        self.next_day_button.setToolTip("Next Day")
        self.next_day_button.clicked.connect(lambda: self.start_datetime_edit.setDateTime(
            self.start_datetime_edit.dateTime().addDays(1)))

        # build button
        self.update_button.clicked.connect(lambda: self.update_map())

        # build labels
        from_label = QtWidgets.QLabel("Analyze Data for 24 hours, starting from: ")
        from_label.setFixedHeight(20)

        # build slider stuff
        self.slider.setFixedWidth(300)
        self.slider.setMinimum(self.sal_min_global * 100.0)
        self.slider.setMaximum(self.sal_max_global * 100.0)
        self.slider.valueChanged.connect(lambda: self.salinity_changed(1))
        slider_current_label = QtWidgets.QLabel("Selected Salinity:")
        slider_current_label.setFixedHeight(20)
        self.salinity_spinbox.setMinimum(self.sal_min_global)
        self.salinity_spinbox.setMaximum(self.sal_max_global)
        self.salinity_spinbox.valueChanged.connect(lambda: self.salinity_changed(0))
        self.salinity_spinbox.setValue(25.0)

        # build display settings
        self.gaussfilter_label.setFixedHeight(20)
        self.gaussfilter_spinbox.setMinimum(0)
        self.gaussfilter_spinbox.setMaximum(5)
        self.gaussfilter_spinbox.setToolTip("The amount by which the contour map is smoothened. 0 means no "
                                            "smoothening, while 5 is the highest amount. The smoothening "
                                            "effect is achieved through a Gaussian blur.")
        display_points_label = QtWidgets.QLabel("Display data as points: ")
        self.display_points_checkbox.setChecked(False)
        self.display_points_checkbox.clicked.connect(lambda: self.show_points_slot())

        # build upper layout
        status_layout = QtWidgets.QHBoxLayout()
        status_layout.addWidget(self.date_label)
        status_layout.addStretch(1)
        status_layout.addWidget(self.gaussfilter_label)
        status_layout.addWidget(self.gaussfilter_spinbox)
        status_layout.addWidget(display_points_label)
        status_layout.addWidget(self.display_points_checkbox)

        # build lower layout
        control_layout = QtWidgets.QHBoxLayout()
        control_layout.addWidget(from_label)
        control_layout.addWidget(self.prev_day_button)
        control_layout.addWidget(self.start_datetime_edit)
        control_layout.addWidget(self.next_day_button)
        control_layout.addStretch(1)
        control_layout.addWidget(self.update_button)
        control_layout.addWidget(slider_current_label)
        control_layout.addWidget(self.salinity_spinbox)
        control_layout.addWidget(self.slider)

        # build main widget
        main_widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addWidget(self.web_view)
        main_layout.addLayout(status_layout)
        main_layout.addLayout(control_layout)
        main_widget.setLayout(main_layout)

        self.update_map()
        return main_widget

    def salinity_changed(self, on_slider: bool):
        if on_slider:
            if self.salinity_spinbox.value != self.slider.value:
                self.salinity_spinbox.setValue(self.slider.value() / 100.0)
        else:
            if self.salinity_spinbox.value != self.slider.value:
                self.slider.setValue(self.salinity_spinbox.value() * 100.0)

    def show_points_slot(self):
        state = self.display_points_checkbox.isChecked() == 0
        self.gaussfilter_label.setVisible(state)
        self.gaussfilter_spinbox.setVisible(state)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    Window = map_view()
    Window.resize(1600, 900)
    Window.setWindowTitle("Flaschenpost Analyzer")
    Window.showMaximized()

    sys.exit(app.exec_())
