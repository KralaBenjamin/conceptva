""" little script to download the data """
import time
import sqlite3 as sql
import xarray as xr
import pandas as pd


def write_into_database():
    """ connect to db """
    list_file_names = list()
    for i in range(1, 31):
        for j in range(0, 24):
            list_file_names.append(f"synop_201306{i:02d}{j:02d}.nc")
    conn = sql.connect("data/data_test2.db")
    df = xr.open_dataset(
        "https://opendap.hereon.de/opendap/data/cosyna/synopsis/OBS/obs_2013.nc"
    )
    df = df.to_dataframe()
    df.to_sql("OBS", conn, if_exists='append')
    for i, file_name in enumerate(list_file_names):
        df1 = xr.open_dataset(
            "https://opendap.hereon.de/opendap/data/cosyna/synopsis/synopsis_BW/BW_2013_06/"
            + file_name
            )
        df1 = df1.to_dataframe()
        df1['initial_time'] = int(file_name[6:-3]) * 100
        process_extrapolated_data(df1, df)
        df1.to_sql("BW", conn, if_exists='append')

        df2 = xr.open_dataset(
            "https://opendap.hereon.de/opendap/data/cosyna/synopsis/synopsis_BW/BW_2013_06/"
            + file_name
            )
        df2 = df2.to_dataframe()
        df2['initial_time'] = int(file_name[6:-3]) * 100
        process_extrapolated_data(df2, df)
        df2.to_sql("FW", conn, if_exists='append')

        print(int(file_name[6:-3]) * 100)


def process_extrapolated_data(df_ext: pd.DataFrame, df_obs: pd.DataFrame):
    """ processing the data """
    sen_list = [[] for _ in range(7)]  # [], [], [], [], [], [], []]
    for _, row in df_ext.iterrows():
        id_row = row['label']
        mask = df_obs['label'].values == id_row

        sen1 = df_obs[mask]['sensor_1'].values[0]
        sen2 = df_obs[mask]['sensor_2'].values[0]
        sen3 = df_obs[mask]['sensor_3'].values[0]
        sen4 = df_obs[mask]['sensor_4'].values[0]
        sen5 = df_obs[mask]['sensor_5'].values[0]
        sen6 = df_obs[mask]['sensor_6'].values[0]
        sen7 = df_obs[mask]['sensor_7'].values[0]

        sen_list[0].append(sen1)
        sen_list[1].append(sen2)
        sen_list[2].append(sen3)
        sen_list[3].append(sen4)
        sen_list[4].append(sen5)
        sen_list[5].append(sen6)
        sen_list[6].append(sen7)

    df_ext['sensor_1'] = sen_list[0]
    df_ext['sensor_2'] = sen_list[1]
    df_ext['sensor_3'] = sen_list[2]
    df_ext['sensor_4'] = sen_list[3]
    df_ext['sensor_5'] = sen_list[4]
    df_ext['sensor_6'] = sen_list[5]
    df_ext['sensor_7'] = sen_list[6]


if __name__ == "__main__":
    print("started building db...")
    start_time = time.time()
    write_into_database()
    print("building db done in "
            + str(int((time.time() - start_time) / 60))
            + " minutes and "
            + str((time.time() - start_time) % 60)
            + " seconds"
        )
