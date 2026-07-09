from setuptools import setup, Extension

# Define the extension module
extension = Extension(
    name="patient_simulation", 
    sources=["src/patient_simulation.c"],
    extra_compile_args=["-O3", "-march=native", "-ffast-math"],
)

setup(
    name="patient_simulation_ext",
    ext_modules=[extension],
)
