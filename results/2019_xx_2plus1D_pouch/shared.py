import pybamm
import numpy as np
import scipy.interpolate as interp
import matplotlib.pyplot as plt


def make_comsol_model(comsol_variables, mesh, param, y_interp=None, z_interp=None):
    "Make Comsol 'model' for comparison"

    comsol_t = comsol_variables["time"]

    # interpolate using *dimensional* space. Note that both y and z are scaled with L_z
    L_z = param.evaluate(pybamm.standard_parameters_lithium_ion.L_z)
    if y_interp is None:
        pybamm_y = mesh["current collector"][0].edges["y"]
        y_interp = pybamm_y * L_z
    if z_interp is None:
        pybamm_z = mesh["current collector"][0].edges["z"]
        z_interp = pybamm_z * L_z  # np.linspace(0, L_z, 20)
    grid_y, grid_z = np.meshgrid(y_interp, z_interp)

    def get_interp_fun(variable):
        """
        Interpolate in space to plotting nodes, and then create function to interpolate
        in time that can be called for plotting at any t.
        """
        comsol_y = comsol_variables["y"]
        comsol_z = comsol_variables["z"]

        # Note order of rows and cols!
        interp_var = np.zeros((len(z_interp), len(y_interp), variable.shape[1]))
        for i in range(0, variable.shape[1]):
            interp_var[:, :, i] = interp.griddata(
                np.column_stack((comsol_y, comsol_z)),
                variable[:, i],
                (grid_y, grid_z),
                method="cubic",
            )

        def myinterp(t):
            return interp.interp1d(comsol_t, interp_var, axis=2)(t)

        return myinterp

    # Create interpolating functions to put in comsol_model.variables dict
    def comsol_voltage(t):
        return interp.interp1d(comsol_t, comsol_variables["voltage"])(t)

    def comsol_vol_av_temperature(t):
        return interp.interp1d(
            comsol_t, comsol_variables["volume-averaged temperature"]
        )(t)

    comsol_phi_s_cn = get_interp_fun(comsol_variables["phi_s_cn"])
    comsol_phi_s_cp = get_interp_fun(comsol_variables["phi_s_cp"])
    comsol_temperature = get_interp_fun(comsol_variables["temperature"])
    comsol_current = get_interp_fun(comsol_variables["current"])

    # Create comsol model with dictionary of Matrix variables
    comsol_model = pybamm.BaseModel()
    comsol_model.variables = {
        "Terminal voltage [V]": comsol_voltage,
        "Negative current collector potential [V]": comsol_phi_s_cn,
        "Positive current collector potential [V]": comsol_phi_s_cp,
        "X-averaged cell temperature [K]": comsol_temperature,
        "Volume-averaged cell temperature [K]": comsol_vol_av_temperature,
        "Current collector current density [A.m-2]": comsol_current,
    }
    comsol_model.y_interp = y_interp
    comsol_model.z_interp = z_interp

    return comsol_model


def plot_t_var(var, t, comsol_model, output_variables, param):
    # discharge timescale
    tau = param.process_symbol(
        pybamm.standard_parameters_lithium_ion.tau_discharge
    ).evaluate()

    plt.figure()
    plt.plot(t, comsol_model.variables[var](t), label="COMSOL")
    plt.plot(t, output_variables[var](t=(t / tau)), label="PyBaMM")
    plt.xlabel(r"$t$")
    plt.ylabel(var)
    plt.legend()


def plot_2D_var(
    var, t, comsol_model, output_variables, param, cmap="viridis", error="abs"
):
    fig, ax = plt.subplots(figsize=(15, 8))

    # get y and z vals from comsol interp points (will be dimensional)
    y_plot = comsol_model.y_interp
    z_plot = comsol_model.z_interp

    # plot pybamm solution
    L_z = param.evaluate(pybamm.standard_parameters_lithium_ion.L_z)
    tau = param.evaluate(pybamm.standard_parameters_lithium_ion.tau_discharge)
    y_plot_non_dim = y_plot / L_z  # Note that both y and z are scaled with L_z
    z_plot_non_dim = z_plot / L_z
    t_non_dim = t / tau

    pybamm_var = np.transpose(
        output_variables[var](y=y_plot_non_dim, z=z_plot_non_dim, t=t_non_dim)
    )
    plt.subplot(131)
    pybamm_plot = plt.pcolormesh(y_plot, z_plot, pybamm_var, shading="gouraud")
    plt.axis([0, y_plot[-1], 0, z_plot[-1]])
    plt.xlabel(r"$y$")
    plt.ylabel(r"$z$")
    plt.title(r"PyBaMM: " + var)
    plt.set_cmap(cmap)
    plt.colorbar(pybamm_plot)

    # plot comsol solution
    comsol_var = comsol_model.variables[var](t=t)
    plt.subplot(132)
    comsol_plot = plt.pcolormesh(y_plot, z_plot, comsol_var, shading="gouraud")
    plt.axis([0, y_plot[-1], 0, z_plot[-1]])
    plt.xlabel(r"$y$")
    plt.ylabel(r"$z$")
    plt.title(r"COMSOL: " + var)
    plt.set_cmap(cmap)
    plt.colorbar(comsol_plot)

    # plot "error"
    plt.subplot(133)
    if error == "abs":
        error = np.abs(pybamm_var - comsol_var)
    elif error == "rel":
        error = np.abs((pybamm_var - comsol_var) / comsol_var)
    diff_plot = plt.pcolormesh(y_plot, z_plot, error, shading="gouraud")
    plt.axis([0, y_plot[-1], 0, z_plot[-1]])
    plt.xlabel(r"$y$")
    plt.ylabel(r"$z$")
    plt.title(r"Error: " + var)
    plt.set_cmap(cmap)
    plt.colorbar(diff_plot)
