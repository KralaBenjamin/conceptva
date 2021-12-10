import io
import sys
import time

import folium
import sqlite3
import pandas as pd
from PySide2 import QtWidgets, QtWebEngineWidgets, QtCore
from dataclasses import dataclass
from shapely.geometry import Polygon
from shapely.geometry import shape
import geojson
import geojsoncontour
import numpy
import branca
from scipy.interpolate import griddata
import matplotlib.pyplot as plt

start_coords = [54.12, 8.37]
min_time = QtCore.QDateTime(QtCore.QDate(2013, 1, 1), QtCore.QTime(0, 0))
max_time = QtCore.QDateTime(QtCore.QDate(2013, 12, 31), QtCore.QTime(23, 59))

# start and end times when launching the program
begin_start_time = QtCore.QDateTime(QtCore.QDate(2013, 6, 1), QtCore.QTime(0, 0))
begin_end_time = QtCore.QDateTime(QtCore.QDate(2013, 6, 1), QtCore.QTime(12, 0))


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


class map_view(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.date_label = QtWidgets.QLabel()
        self.date_label.setFixedHeight(20)
        self.fol_map = folium.Map(location=start_coords, zoom_start=10)
        self.web_view = QtWebEngineWidgets.QWebEngineView()
        self.web_view.loadFinished.connect(lambda: self.update_finished())
        self.start_datetime_edit = QtWidgets.QDateTimeEdit()
        self.end_datetime_edit = QtWidgets.QDateTimeEdit()
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
        self.process_extrapolated_data(self.runtime_ds.data_bw)
        query_fw = "SELECT * FROM FW"
        self.runtime_ds.data_fw = pd.read_sql_query(query_fw, db)
        self.process_extrapolated_data(self.runtime_ds.data_fw)
        db.close()

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
        # TODO: make this work properly
        # set label to updating
        self.date_label.setText("Updating...")

        start_datetime = self.start_datetime_edit.dateTime()
        end_datetime = self.end_datetime_edit.dateTime()

        # get data
        m_data = self.get_data_for_time_range(start_datetime, end_datetime)

        # rebuild map
        self.fol_map = folium.Map(location=start_coords, zoom_start=10)

        # self.draw_polygon(m_data.data_bw, "#cf5a30")
        # self.draw_polygon(m_data.data_fw, "#de59c1")
        # self.draw_polygon(m_data.data_obs, "#55b33b")
        self.draw_contour_map(m_data, 25.0)

        # convert map to bytes and set html to webview
        data = io.BytesIO()
        self.fol_map.location = start_coords
        self.fol_map.save(data, close_file=False)
        html = data.getvalue().decode()
        self.web_view.setHtml(html)

    # add a marker for each measurement in the given color
    # If to many markers are created (around >5000), view will not render
    def add_markers(self, df: pd.DataFrame, color: str):
        for index, row in df.iterrows():
            coords = [row['latitude'], row['longitude']]
            folium.vector_layers.CircleMarker(
                location=coords, radius=5, color=color, fill=True, fillOpacity=1.0, fillColor=color
            ).add_to(self.fol_map)

    # draw a convex polygon over the given points. Much faster than markers, though not as accurate
    def draw_polygon(self, df: pd.DataFrame, color: str):
        try:
            lat_point_list = df['latitude'].tolist()
            lon_point_list = df['longitude'].tolist()
        except:
            # empty df or some other error
            print("Couldn't draw polygon")
            return

        polygon_geom = Polygon(zip(lon_point_list, lat_point_list))
        polygon_geom = polygon_geom.convex_hull
        polygon_geom = polygon_geom.difference(self.ger_polygon)
        folium.GeoJson(
            polygon_geom,
            style_function=lambda feature: {
                'fillColor': color,
                'color': color,
                'weight': 1,
                'fillOpacity': 0.5,
            }
        ).add_to(self.fol_map)

    # draw contour map
    def draw_contour_map(self, md: map_data, sal_val: float):
        # construct dataframe with salinity
        df = md.data_obs[['latitude', 'longitude', 'sensor_1']]
        #self.process_extrapolated_data(md.data_bw)
        md.data_bw = md.data_bw[['latitude', 'longitude', 'sensor_1']]
        #self.process_extrapolated_data(md.data_fw)
        md.data_fw = md.data_fw[['latitude', 'longitude', 'sensor_1']]

        df = df.append(md.data_bw)
        df = df.append(md.data_fw)

        # color stuff for the map
        colors = ['#b5212f', '#de7881', '#77b5d4', '#06618f']
        sal_min = df['sensor_1'].min()
        sal_max = df['sensor_1'].max()
        # make sure salinity is between min and max
        # TODO: look into this
        sal_val = numpy.clip(sal_val, sal_min, sal_max)
        # scale values for colors
        levels = [sal_min, sal_min + 0.5 * (sal_val - sal_min), sal_val, sal_val + 0.5 * (sal_max - sal_val)]
        col_map = branca.colormap.LinearColormap(colors, vmin=sal_min, vmax=sal_max).to_step(index=levels)

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

        # TODO: Gaussian filter ?

        contourf = plt.contourf(x_mesh, y_mesh, z_mesh, levels, alpha=0.5, colors=colors, linestyles='None', vmin=sal_min,
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

    # add salinity values to extrapolated points
    # TODO: this is slow as hell
    # TODO: should probably be done when loading db
    def process_extrapolated_data(self, df: pd.DataFrame):
        sal_list = []
        for index, row in df.iterrows():
            id = row['label']
            mask = self.runtime_ds.data_obs['label'].values == id
            sal = self.runtime_ds.data_obs[mask]['sensor_1'].values[0]
            sal_list.append(sal)
        df['sensor_1'] = sal_list

    def update_finished(self):
        # update label
        self.date_label.setText(
            "Currently displaying: " + self.start_datetime_edit.dateTime().toString() + " to " + self.end_datetime_edit.dateTime().toString())

    def start_datetime_changed(self):
        self.end_datetime_edit.setDateTimeRange(self.start_datetime_edit.dateTime(), max_time)

    # create the GUI consisting of a map, a date-time selection field and an update button
    def create_gui(self):
        # build upper layout
        status_layout = QtWidgets.QHBoxLayout()
        status_layout.addWidget(self.date_label)

        # build start date time edit
        self.start_datetime_edit.setDateTimeRange(min_time, max_time)
        self.start_datetime_edit.setCalendarPopup(1)
        self.start_datetime_edit.setDateTime(begin_start_time)
        self.start_datetime_edit.setMinimumWidth(120)
        self.start_datetime_edit.dateTimeChanged.connect(lambda: self.start_datetime_changed())

        # build end date time edit
        self.end_datetime_edit.setDateTimeRange(begin_start_time, max_time)
        self.end_datetime_edit.setCalendarPopup(1)
        self.end_datetime_edit.setDateTime(begin_end_time)
        self.end_datetime_edit.setMinimumWidth(120)

        # build button
        button = QtWidgets.QPushButton("Update")
        button.clicked.connect(lambda: self.update_map())

        # build labels
        from_label = QtWidgets.QLabel("Analyze Data from: ")
        from_label.setFixedHeight(20)
        until_label = QtWidgets.QLabel(" until: ")
        until_label.setFixedHeight(20)

        # build slider stuff
        self.slider.setFixedWidth(200)
        slider_current_label = QtWidgets.QLabel("Selected Salinity:")
        slider_current_label.setFixedHeight(20)
        salinity_spinbox = QtWidgets.QDoubleSpinBox()

        # build lower layout
        control_layout = QtWidgets.QHBoxLayout()
        control_layout.addWidget(from_label)
        control_layout.addWidget(self.start_datetime_edit)
        control_layout.addWidget(until_label)
        control_layout.addWidget(self.end_datetime_edit)
        control_layout.addWidget(button)
        control_layout.addStretch(1)
        control_layout.addWidget(slider_current_label)
        control_layout.addWidget(salinity_spinbox)
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


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    Window = map_view()
    Window.resize(1600, 900)
    Window.setWindowTitle("Flaschenpost Analyzer")
    Window.showMaximized()

    sys.exit(app.exec_())
