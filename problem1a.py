"""Steady radial drug release through a cylindrical water film.

Run with: python problem1a.py
Dependencies: numpy, scipy, matplotlib
Change BASELINE and SWEEPS to explore different parameters. Inputs use SI.
"""

from dataclasses import dataclass, replace
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_bvp


@dataclass(frozen=True)
class Film:
    radius: float = 2.0e-3       # m
    thickness: float = 0.5e-3    # m
    length: float = 20.0e-3      # m
    diffusivity: float = 1.0e-9  # m²/s
    total_concentration: float = 55_500.0  # mol/m³
    surface_fraction: float = 0.020
    bulk_fraction: float = 0.001

    def __post_init__(self):
        positive = (self.radius, self.thickness, self.length,
                    self.diffusivity, self.total_concentration)
        if not all(np.isfinite(value) and value > 0 for value in positive):
            raise ValueError("Dimensions, diffusivity and concentration must be positive and finite.")
        if not 0 <= self.bulk_fraction <= self.surface_fraction < 1:
            raise ValueError("Use 0 <= bulk_fraction <= surface_fraction < 1.")


BASELINE = Film()
SWEEPS = {
    "thickness": (0.2e-3, 0.5e-3, 1.0e-3),
    "diffusivity": (0.5e-9, 1.0e-9, 2.0e-9),
    "surface_fraction": (0.005, 0.020, 0.050),
}


def analytical_solution(film, s):
    """Return radius [m], drug mole fraction, and outward flux [mol/m²/s].

    s = (r - R)/delta runs from zero at the pill to one in the bulk.
    C1 = r*N_Ar is constant by the steady cylindrical shell balance.
    """
    r = film.radius + film.thickness * s
    log_radius_ratio = np.log1p(film.thickness / film.radius)
    log_water_ratio = np.log1p(
        (film.surface_fraction - film.bulk_fraction) / (1 - film.surface_fraction)
    )
    position = np.log1p(film.thickness * s / film.radius) / log_radius_ratio
    log_water_fraction = np.log1p(-film.surface_fraction) + position * log_water_ratio
    fraction = -np.expm1(log_water_fraction)
    c1 = film.total_concentration * film.diffusivity * log_water_ratio / log_radius_ratio
    return r, fraction, c1 / r


def numerical_solution(film, s):
    """Solve dx_A/ds = -q*(1-x_A)/(1+s*delta/R) with both endpoint values.

    The unknown q = C1*delta/(c*D_AB*R) is solved along with x_A.
    """
    relative_thickness = film.thickness / film.radius
    grid = np.linspace(0.0, 1.0, 25)
    initial_profile = np.linspace(film.surface_fraction, film.bulk_fraction, grid.size)

    def ode(position, state, parameter):
        return -parameter[0] * (1 - state) / (1 + relative_thickness * position)

    def boundary(left, right, parameter):
        return np.array([left[0] - film.surface_fraction, right[0] - film.bulk_fraction])

    result = solve_bvp(ode, boundary, grid, initial_profile[None, :],
                       p=[film.surface_fraction - film.bulk_fraction], tol=1e-10)
    if not result.success:
        raise RuntimeError(result.message)

    r = film.radius + film.thickness * s
    c1 = result.p[0] * film.total_concentration * film.diffusivity / relative_thickness
    return result.sol(s)[0], c1 / r


def main():
    s = np.linspace(0.0, 1.0, 241)
    colors = ("#17689c", "#bd550d", "#18776c")
    styles = ("-", "--", ":")
    row_labels = {
        "thickness": ("Boundary-layer thickness", lambda v: f"{v * 1e3:g} mm"),
        "diffusivity": ("Drug diffusivity", lambda v: f"{v * 1e9:g} × 10⁻⁹ m²/s"),
        "surface_fraction": ("Surface mole fraction", lambda v: f"{v:.1%}"),
    }

    fig, axes = plt.subplots(3, 2, figsize=(10, 9), sharex=True)
    fig.subplots_adjust(left=.12, right=.96, bottom=.12, top=.81, hspace=.55, wspace=.38)
    fig.text(.12, .963, "Drug diffusion from a cylindrical pill", fontsize=23, weight="bold")
    fig.text(.12, .922, "Problem 1(a)  •  Illustrative inputs  •  One parameter varied at a time",
             fontsize=11, color="#475c70")
    axes[0, 0].set_title("Drug concentration profile", loc="left", weight="bold", pad=40)
    axes[0, 1].set_title("Outward radial drug flux", loc="left", weight="bold", pad=40)
    max_fraction_error = 0.0
    max_flux_relative_error = 0.0
    print("Sweep                 Value                    N_A(R) [mol/m²/s]  Rate [mol/s]")
    for row, (field, values) in enumerate(SWEEPS.items()):
        concentration_ax, flux_ax = axes[row]
        title, format_value = row_labels[field]
        for value, color, style in zip(values, colors, styles, strict=True):
            film = replace(BASELINE, **{field: value})
            r, fraction, flux = analytical_solution(film, s)
            numerical_fraction, numerical_flux = numerical_solution(film, s)
            np.testing.assert_allclose(fraction[[0, -1]],
                                       [film.surface_fraction, film.bulk_fraction], atol=1e-12)
            np.testing.assert_allclose(r * flux, r[0] * flux[0], rtol=1e-12)
            np.testing.assert_allclose(numerical_fraction, fraction, atol=1e-9)
            np.testing.assert_allclose(numerical_flux, flux, rtol=1e-7, atol=1e-12)
            max_fraction_error = max(max_fraction_error, np.max(np.abs(numerical_fraction - fraction)))
            if flux[0] != 0:
                max_flux_relative_error = max(max_flux_relative_error,
                                              np.max(np.abs(numerical_flux / flux - 1)))
            # For the D_AB sweep all concentration curves coincide.
            if field != "diffusivity" or value == values[0]:
                concentration_ax.plot(s, film.total_concentration * fraction,
                                      color=color, ls=style, lw=2.2)
            flux_ax.plot(s, flux, color=color, ls=style, lw=2.2, label=format_value(value))
            rate = 2 * np.pi * film.radius * film.length * flux[0]
            print(f"{title:22} {format_value(value):24} {flux[0]:17.5g}  {rate:.5g}")

        concentration_ax.text(0, 1.06, title, transform=concentration_ax.transAxes,
                              fontsize=11, weight="bold")
        concentration_ax.set_ylabel(r"$c_A$ [mol/m³]")
        flux_ax.set_ylabel(r"$N_{Ar}$ [mol/(m² s)]")
        flux_ax.legend(frameon=False, fontsize=9, loc="lower left", bbox_to_anchor=(0, 1.005), ncol=3,
                       columnspacing=.8, handlelength=1.4, borderaxespad=0)
        if field == "diffusivity":
            concentration_ax.text(.98, .95, "All three profiles coincide", ha="right", va="top",
                                  transform=concentration_ax.transAxes, fontsize=9)
        for ax in (concentration_ax, flux_ax):
            ax.set_xlim(0, 1)
            ax.margins(y=.1)
            ax.grid(alpha=.2)
            ax.spines[["top", "right"]].set_visible(False)

    for ax in axes[-1]:
        ax.set_xlabel(r"Position in the film, $(r-R)/\delta$")
    fig.text(.12, .034, "Position 0 is the pill surface. Position 1 is the outer edge of the water film.",
             fontsize=10, color="#475c70")
    output = Path(__file__).with_name("problem1a-parameter-sweeps.png")
    fig.savefig(output, dpi=175)
    plt.close(fig)
    print(f"\nMaximum analytical vs. SciPy difference in x_A: {max_fraction_error:.2e}")
    print(f"Maximum relative flux difference: {max_flux_relative_error:.2e}")
    print(f"Saved {output.name}")


if __name__ == "__main__":
    main()
