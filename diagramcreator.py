"""
Central File for the interactive diagram
"""

import plotly.graph_objects as go
import pandas as pd


def save_diagram_file(
    m_data,
    global_data,
    salinity_value
):
    """ save the interactive file into html """

    merged_data = pd.concat([
        m_data.data_obs,
        m_data.data_bw,
        m_data.data_fw
    ])

    merge_data_below_sal = merged_data[
        merged_data["sensor_1"] <= salinity_value
    ]
    merge_data_above_sal = merged_data[
        merged_data["sensor_1"] > salinity_value
    ]

    pandas_col_to_sensor_data_name = {
        "sensor_1": "Salinity",
        "sensor_2": "Temperature",
        "sensor_3": "CDOM",
        "sensor_4": "Chlorophyll",
        "sensor_5": "DO",
        "sensor_6": "DOSat",
        "sensor_7": "DO_Anomaly",
    }

    categories = [
        pandas_col_to_sensor_data_name[f'sensor_{i}']
        for i in range(1, 8)
    ]

    data_max_above = list()
    data_min_above = list()

    data_max_below = list()
    data_min_below = list()

    # gets min and max value for all data
    for i in range(1, 8):
        cat = f'sensor_{i}'

        global_min = global_data[cat]['min']
        global_max = global_data[cat]['max']

        current_max_above = merge_data_above_sal[cat].max()
        current_min_above = merge_data_above_sal[cat].min()

        data_max_above.append((current_max_above - global_min) / global_max)
        data_min_above.append((current_min_above - global_min) / global_max)

        current_max_below = merge_data_below_sal[cat].max()
        current_min_below = merge_data_below_sal[cat].min()

        # we normalise the values
        data_max_below.append((current_max_below - global_min) / global_max)
        data_min_below.append((current_min_below - global_min) / global_max)

    fig = go.Figure()

    # stack the polar diagrams

    fig.add_trace(go.Scatterpolar(
          r=data_max_above,
          theta=categories,
          fill='none',
          name='Max Above Salinity',
          marker=go.scatterpolar.Marker(
            color="#06618f",
          )
    ))
    fig.add_trace(go.Scatterpolar(
          r=data_max_below,
          theta=categories,
          fill='none',
          name='Max Below Salinity',
          marker=go.scatterpolar.Marker(
            color="#b5212f",
          )
    ))
    fig.add_trace(go.Scatterpolar(
          r=data_min_above,
          theta=categories,
          fill='toself',
          name='Min Above Salinity',
          marker=go.scatterpolar.Marker(
            color="#de7881",
          )
    ))
    fig.add_trace(go.Scatterpolar(
          r=data_min_below,
          theta=categories,
          fill='toself',
          name='Min Below Salinity',
          marker=go.scatterpolar.Marker(
            color="#77b5d4",
          )
    ))

    fig.update_layout(
      polar=dict(
        radialaxis=dict(
          visible=True,
          range=[0, 1.0],
        )),
      legend=dict(
        xanchor="left",
        x=0.01
      ),
      showlegend=True
    )
    fig.write_html(
        'radarplot.html',
        auto_open=False,
    )
