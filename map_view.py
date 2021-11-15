import io
import sys

import xarray
import folium
from PySide2 import QtWidgets, QtWebEngineWidgets, QtCore

start_coords = [54.12, 8.37]
min_time = QtCore.QDateTime(QtCore.QDate(2013, 6, 1), QtCore.QTime(0, 0))
max_time = QtCore.QDateTime(QtCore.QDate(2013, 6, 30), QtCore.QTime(23, 0))


class map_view(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.date_label = QtWidgets.QLabel()
        self.date_label.setFixedHeight(20)
        self.fol_map = folium.Map(location=start_coords, zoom_start=10)
        self.web_view = QtWebEngineWidgets.QWebEngineView()
        self.start_datetime_edit = QtWidgets.QDateTimeEdit()
        self.end_datetime_edit = QtWidgets.QDateTimeEdit()
        self.data_map = dict()

        self.setCentralWidget(self.create_gui())

    # returns an object (currently dataframe) which contains the data relevant for the given time
    # TODO: This function can be overwritten with a DB access or another method of getting data
    def get_dateframe_for_time_string(self, start_datetime: QtCore.QDateTime, end_datetime: QtCore.QDateTime):
        time_str = self.create_time_string(start_datetime)
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
        start_datetime = self.start_datetime_edit.dateTime()
        end_datetime = self.start_datetime_edit.dateTime()
        # TODO: make sure end is greater than start, abort if not
        self.date_label.setText(
            "Currently displaying: " + self.start_datetime_edit.dateTime().toString() + " to " + self.end_datetime_edit.dateTime().toString())

        # get data
        df = self.get_dateframe_for_time_string(start_datetime, end_datetime)

        # rebuild map
        self.fol_map = folium.Map(location=start_coords, zoom_start=10)
        # place markers on map
        for index, row in df.iterrows():
            coords = [row['latitude'], row['longitude']]
            folium.vector_layers.CircleMarker(
                location=coords, radius=5, color="#ff0000", fill=True, fillOpacity=1.0, fillColor="#ff0000"
            ).add_to(self.fol_map)

        # convert map to bytes and set html to webview
        data = io.BytesIO()
        self.fol_map.location = start_coords
        self.fol_map.save(data, close_file=False)
        self.web_view.setHtml(data.getvalue().decode())

    # create the GUI consisting of a map, a date-time selection field and an update button
    def create_gui(self):
        # build upper layout
        status_layout = QtWidgets.QHBoxLayout()
        status_layout.addWidget(self.date_label)

        # build start date time edit
        self.start_datetime_edit.setDateTimeRange(min_time, max_time)
        self.start_datetime_edit.setCalendarPopup(1)
        self.start_datetime_edit.setDateTime(min_time)

        # build end date time edit
        self.end_datetime_edit.setDateTimeRange(min_time, max_time)
        self.end_datetime_edit.setCalendarPopup(1)
        self.end_datetime_edit.setDateTime(min_time)

        # build button
        button = QtWidgets.QPushButton("Update")
        button.clicked.connect(lambda: self.update_map())

        # build lower layout
        # TODO: format this properly
        control_layout = QtWidgets.QHBoxLayout()
        control_layout.addWidget(self.start_datetime_edit)
        control_layout.addWidget(self.end_datetime_edit)
        control_layout.addWidget(button)

        # build main widget
        main_widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(status_layout)
        main_layout.addWidget(self.web_view)
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
