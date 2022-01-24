

import numpy as np
from bokeh.plotting import figure, show, output_file, save
from bokeh.models import ColumnDataSource, LabelSet


def create_diagram2(diagram_average_below_salicity,
                   diagram_average_above_salicity,
                   diagram_min_below_salicity,
                   diagram_min_above_salicity,
                   diagram_max_below_salicity,
                   diagram_max_above_salicity,
                   col_names,
                   col_to_global_max,
                   col_to_global_min,
                    col_to_text):

    num_vars = len(col_names)

    centre = 0.5

    theta = np.linspace(0, 2*np.pi, num_vars, endpoint=False)
    # rotate theta such that the first axis is at the top
    theta += np.pi/2

    def unit_poly_verts(theta, centre):
        """Return vertices of polygon for subplot axes.
        This polygon is circumscribed by a unit circle centered at (0.5, 0.5)
        """
        x0, y0, r = [centre] * 3
        verts = [(r*np.cos(t) + x0, r*np.sin(t) + y0) for t in theta]
        return verts

    def radar_patch(r, theta, centre):
        """ Returns the x and y coordinates corresponding to the magnitudes of
        each variable displayed in the radar plot
        """
        # offset from centre of circle
        offset = 0.01
        yt = (r*centre + offset) * np.sin(theta) + centre
        xt = (r*centre + offset) * np.cos(theta) + centre
        return xt, yt


    def diagram_dict_to_np_array(diagram_dict):
        result_list = list()
        for col in col_names:
            scaled_max = col_to_global_max[col] - col_to_global_min[col]
            scaled_output = (diagram_dict[col] - col_to_global_min[col]) / scaled_max
            result_list.append(scaled_output)
        return np.array(result_list)


    verts = unit_poly_verts(theta, centre)
    x = [v[0] for v in verts] + [verts[0][0]]
    y = [v[1] for v in verts] + [verts[0][1]]

    p = figure(title="Baseline - Radar plot", plot_width=500, plot_height=500)
    source = ColumnDataSource({'x':x + [centre ],
                               'y':y + [1],
                               'text': [col_to_text[col] for col in col_names]})

    #p.line(x="x", y="y", source=source)
    p.patch(x='x', y='y', fill_alpha=0.0, source=source, line_width=1.5,color="black")

    labels = LabelSet(x="x", y="y", text="text",source=source)

    p.add_layout(labels)

    np_average_below_salicity = diagram_dict_to_np_array(diagram_average_below_salicity)
    np_average_above_salicity =  diagram_dict_to_np_array(diagram_average_above_salicity)
    np_min_below_salicity = diagram_dict_to_np_array(diagram_min_below_salicity)
    np_min_above_salicity = diagram_dict_to_np_array(diagram_min_above_salicity)
    np_max_below_salicity = diagram_dict_to_np_array(diagram_max_below_salicity)
    np_max_above_salicity = diagram_dict_to_np_array(diagram_max_above_salicity)

    flist = [np_average_below_salicity,
             np_average_above_salicity,
             #np_min_below_salicity,
             #np_min_above_salicity,
             #np_max_below_salicity,
             #np_max_above_salicity
             ]
    colors = ['#b5212f', '#06618f', '#b5212f', '#06618f', '#b5212f', '#06618f']

    #labels = ['avg_not_sal', 'avg_sal', 'min_not_sal', 'min_sal', 'max_not_sal', 'max_sal']

    line_widths = [2.5, 2.5, 1.5, 1.5, 1.5, 1.5]
    fill_alphas = [0.0, 0.0, 0.5, 0.5, 0.0, 0.0]

    for i in range(len(flist)):
        xt, yt = radar_patch(flist[i], theta, centre)
        p.patch(x=xt,
                y=yt,
                fill_alpha=0.0,
                fill_color=colors[i],
                line_color=colors[i],
                #legend=labels[i],
                line_width=line_widths[i])
        #p.line(x=xt, y=yt, color=colors[i])
    save(p)
