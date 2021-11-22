import sqlite3 as sql
import xarray as xr


# connect to db
def write_into_database():
    list_file_names = list()
    for i in range(1, 31):
        for j in range(0, 24):
            list_file_names.append(f"synop_201306{i:02d}{j:02d}.nc")
    conn = sql.connect("data/data_test.db")
    for i, file_name in enumerate(list_file_names):
        df1 = xr.open_dataset("bw/" + file_name)
        df1 = df1.to_dataframe()
        df1.to_sql("BW", conn, if_exists='append')

        df2 = xr.open_dataset("fw/" + file_name)
        df2 = df2.to_dataframe()
        df2.to_sql("FW", conn, if_exists='append')
    df = xr.open_dataset("obs_2013.nc")
    df = df.to_dataframe()
    df.to_sql("OBS", conn, if_exists='append')


if __name__ == "__main__":
    write_into_database()
