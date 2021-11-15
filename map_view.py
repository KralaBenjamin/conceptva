import io
import sys

import xarray
import folium
from PySide2 import QtWidgets, QtWebEngineWidgets, QtCore

start_coords = [54.15, 8.37]
min_time = QtCore.QDateTime(QtCore.QDate(2013, 6, 1), QtCore.QTime(0, 0))
max_time = QtCore.QDateTime(QtCore.QDate(2013, 6, 30), QtCore.QTime(23, 0))


class map_view(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.fol_map = folium.Map(location=start_coords, zoom_start=10)
        self.web_view = QtWebEngineWidgets.QWebEngineView()
        self.datetime_edit = QtWidgets.QDateTimeEdit()
        self.data_map = dict()
        # store marker layers for map
        self.marker_dict = dict()
        # currently active marker layer. Empty if none
        self.active_featuregroup = ""

        self.setCentralWidget(self.create_gui())

    # This function can be overwritten with a DB access or another method of getting data
    def get_dateframe_for_time_string(self, time_str: str):
        if self.data_map.__contains__(time_str):
            print("data in dict")
            df = self.data_map[time_str]
        else:
            print("data not in dict")
            df = xarray.open_dataset(
                "https://opendap.hereon.de/opendap/data/cosyna/synopsis/synopsis_BW/BW_2013_06/synop_" + str(
                    time_str) + ".nc")
            df = df.to_dataframe()
            self.data_map[time_str] = df
        return df

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
        return time_str

    # update map when new time was selected
    def update_map(self):
        date_time = self.datetime_edit.dateTime()
        time_str = self.create_time_string(date_time)

        # rebuild map
        self.fol_map = folium.Map(location=start_coords, zoom_start=10)

        # get data
        df = self.get_dateframe_for_time_string(time_str)

        # place markers on map
        self.marker_dict[time_str] = folium.FeatureGroup(name=time_str)
        for index, row in df.iterrows():
            coords = [row['latitude'], row['longitude']]
            folium.vector_layers.CircleMarker(
                location=coords, radius=5, color="#ff0000", fill=True, fillOpacity=1.0, fillColor="#ff0000"
                                              ).add_to(self.marker_dict[time_str])
        self.marker_dict[time_str].add_to(self.fol_map)

        # convert map to bytes and set html to webview
        data = io.BytesIO()
        self.fol_map.location = start_coords
        self.fol_map.save(data, close_file=False)
        self.web_view.setHtml(data.getvalue().decode())


    # create the GUI consisting of a map, a date-time selection field and an update button
    def create_gui(self):
        # build date time edit
        self.datetime_edit.setDateTimeRange(min_time, max_time)
        self.datetime_edit.setCalendarPopup(1)
        self.datetime_edit.setDateTime(min_time)

        # build button
        button = QtWidgets.QPushButton("Update")
        button.clicked.connect(lambda: self.update_map())

        # build lower layout
        control_layout = QtWidgets.QHBoxLayout()
        control_layout.addWidget(self.datetime_edit)
        control_layout.addWidget(button)

        # build main widget
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.web_view)
        layout.addLayout(control_layout)
        widget.setLayout(layout)

        self.update_map()
        return widget


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    Window = map_view()
    Window.resize(1600,900)
    Window.setWindowTitle("Flaschenpost Map View")
    Window.showMaximized()

    sys.exit(app.exec_())
