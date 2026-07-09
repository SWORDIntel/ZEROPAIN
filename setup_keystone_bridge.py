from setuptools import setup
from Cython.Build import cythonize

setup(
    name='keystone_bridge',
    ext_modules=cythonize([
        "src/patient_simulation.py", 
        "src/tolerance_models.py"
    ], compiler_directives={'language_level' : "3", 'profile': False})
)
