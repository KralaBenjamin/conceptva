import io
import sys

import folium
import sqlite3
import pandas as pd
from PySide2 import QtWidgets, QtWebEngineWidgets, QtCore
from dataclasses import dataclass
import geopandas as gpd
from shapely.geometry import Polygon

start_coords = [54.12, 8.37]
min_time = QtCore.QDateTime(QtCore.QDate(2013, 1, 1), QtCore.QTime(0, 0))
max_time = QtCore.QDateTime(QtCore.QDate(2013, 12, 31), QtCore.QTime(23, 59))

# start and end times when launching the program
begin_start_time = QtCore.QDateTime(QtCore.QDate(2013, 6, 1), QtCore.QTime(0, 0))
begin_end_time = QtCore.QDateTime(QtCore.QDate(2013, 6, 2), QtCore.QTime(0, 0))


@dataclass
class map_data:
    data_obs: pd.DataFrame = pd.DataFrame()
    data_bw: pd.DataFrame = pd.DataFrame()
    data_fw: pd.DataFrame = pd.DataFrame()


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

        # load data
        print("loading")
        self.runtime_ds = map_data()
        db = sqlite3.connect("data/data_test.db")
        query_obs = "SELECT * FROM OBS"
        self.runtime_ds.data_obs = pd.read_sql_query(query_obs, db)
        query_bw = "SELECT * FROM BW"
        self.runtime_ds.data_bw = pd.read_sql_query(query_bw, db)
        query_fw = "SELECT * FROM FW"
        self.runtime_ds.data_fw = pd.read_sql_query(query_fw, db)
        print("loading complete")

        self.setCentralWidget(self.create_gui())

    # returns an object (currently "struct" of dataframes) which contains the data relevant for the given time
    def get_data_for_time_range(self, start_datetime: QtCore.QDateTime, end_datetime: QtCore.QDateTime):
        start_time_str = self.create_time_string(start_datetime)
        end_time_str = self.create_time_string(end_datetime)

        m_data = map_data()

        db = sqlite3.connect("data/data_test.db")

        query_obs = "SELECT * FROM OBS WHERE CAST(time as INT) BETWEEN " + start_time_str + " AND " + end_time_str
        m_data.data_obs = pd.read_sql_query(query_obs, db)

        # TODO: make this work properly and preferably faster
        try:
            query_bw = "SELECT * FROM BW WHERE CAST(label as INT) BETWEEN " + str(
                int(m_data.data_obs['label'].min())) + " AND " + str(int(m_data.data_obs['label'].max()))
            m_data.data_bw = pd.read_sql_query(query_bw, db)
        except:
            print("loading interpolated data failed")

        db.close()
        return m_data

    # build a string compatible to the data we have from a QDateTime object
    def create_time_string(self, date_time: QtCore.QDateTime):
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

    # update map when new time was selected
    def update_map(self):
        # set label to updating
        self.date_label.setText("Updating...")
        self.date_label.repaint()

        start_datetime = self.start_datetime_edit.dateTime()
        end_datetime = self.end_datetime_edit.dateTime()

        # get data
        m_data = self.get_data_for_time_range(start_datetime, end_datetime)

        # rebuild map
        self.fol_map = folium.Map(location=start_coords, zoom_start=10)
        # place markers on map
        #self.add_markers(m_data.data_obs, "#cf5a30")
        #self.add_markers(m_data.data_bw, "#55b33b")

        self.draw_polygon(m_data.data_bw, "#55b33b")

        # convert map to bytes and set html to webview
        data = io.BytesIO()
        self.fol_map.location = start_coords
        self.fol_map.save(data, close_file=False)
        html = data.getvalue().decode()
        self.write_html_to_file(html)
        self.web_view.setHtml(html)

    # for debugging
    def write_html_to_file(self, html):
        f = open("Test.html", "a")
        f.truncate(0)
        f.write(html)
        f.close()

    def add_markers(self, df, color):
        for index, row in df.iterrows():
            coords = [row['latitude'], row['longitude']]
            folium.vector_layers.CircleMarker(
                location=coords, radius=5, color=color, fill=True, fillOpacity=1.0, fillColor=color
            ).add_to(self.fol_map)

    def draw_polygon(self, df, color):
        lat_point_list = df['latitude'].tolist()
        lon_point_list = df['longitude'].tolist()

        polygon_geom = Polygon(zip(lon_point_list, lat_point_list))
        polygon_geom = polygon_geom.convex_hull
        folium.GeoJson(polygon_geom).add_to(self.fol_map)

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

        # build lower layout
        control_layout = QtWidgets.QHBoxLayout()
        control_layout.addWidget(from_label)
        control_layout.addWidget(self.start_datetime_edit)
        control_layout.addWidget(until_label)
        control_layout.addWidget(self.end_datetime_edit)
        control_layout.addWidget(button)
        control_layout.addStretch(1)

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
