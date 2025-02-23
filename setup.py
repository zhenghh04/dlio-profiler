import os
import re
import subprocess
import sys
from pathlib import Path
print(sys.argv)
from setuptools import Extension, setup, find_namespace_packages
from setuptools.command.build_ext import build_ext
import site

# Convert distutils Windows platform specifiers to CMake -A arguments
PLAT_TO_CMAKE = {
    "win32": "Win32",
    "win-amd64": "x64",
    "win-arm32": "ARM",
    "win-arm64": "ARM64",
}


# A CMakeExtension needs a sourcedir instead of a file list.
# The name must be the _single_ output extension from the CMake build.
# If you need multiple extensions, see scikit-build.
class CMakeExtension(Extension):
    def __init__(self, name: str, sourcedir: str = "") -> None:
        super().__init__(name, sources=[])
        self.sourcedir = os.fspath(Path(sourcedir).resolve())


class CMakeBuild(build_ext):
    def build_extension(self, ext: CMakeExtension) -> None:
        cmake_args = []
        from distutils.sysconfig import get_python_lib
        install_prefix = f"{get_python_lib()}/dlio_profiler"
        if "DLIO_LOGGER_USER" in os.environ:
            install_prefix=f"{site.USER_SITE}/dlio_profiler"
            # cmake_args += [f"-DUSER_INSTALL=ON"]
        if "DLIO_PROFILER_DIR" in os.environ:
            install_prefix = os.environ['DLIO_PROFILER_DIR']
        cmake_args += [f"-DCMAKE_INSTALL_PREFIX={install_prefix}"]
        if "DLIO_PYTHON_SITE" in os.environ:
            dlio_site = os.environ['DLIO_PYTHON_SITE']
            cmake_args += [f"-DDLIO_PYTHON_SITE={dlio_site}"]
        project_dir = Path.cwd()
        if "DLIO_BUILD_DEPENDENCIES" not in os.environ or os.environ['DLIO_BUILD_DEPENDENCIES'] == "1":
            dependency_file = open(f"{project_dir}/dependency/cpp.requirements.txt", 'r')
            dependencies = dependency_file.readlines()
            for dependency in dependencies:
                parts = dependency.split(",")
                clone_dir = f"{project_dir}/dependency/{parts[0]}"
                need_install = parts[3]
                print(f"Installing {parts[0]} into {install_prefix}")
                os.system(f"bash {project_dir}/dependency/install_dependency.sh {parts[1]} {clone_dir} {install_prefix} {parts[2]} {need_install}")

        import pybind11 as py
        py_cmake_dir = py.get_cmake_dir()
        # py_cmake_dir = os.popen('python3 -c " import pybind11 as py; print(py.get_cmake_dir())"').read() #python("-c", "import pybind11 as py; print(py.get_cmake_dir())", output=str).strip()
        cmake_args += [f"-DCMAKE_PREFIX_PATH={install_prefix}", f"-Dpybind11_DIR={py_cmake_dir}"]
        print(cmake_args)
        # Must be in this form due to bug in .resolve() only fixed in Python 3.10+
        ext_fullpath = project_dir / self.get_ext_fullpath(ext.name)
        extdir = ext_fullpath.parent.parent.resolve()
        sourcedir = extdir.parent.resolve()
        print(f"{extdir}")
        # Using this requires trailing slash for auto-detection & inclusion of
        # auxiliary "native" libs
        build_type = os.environ.get("CMAKE_BUILD_TYPE", "Release")
        cmake_args += [f"-DCMAKE_BUILD_TYPE={build_type}"]
        enable_tests = os.environ.get("DLIO_PROFILER_ENABLE_TESTS", "On")
        cmake_args += [f"-DDLIO_PROFILER_ENABLE_TESTS={enable_tests}"]
        enable_dlio_tests = os.environ.get("ENABLE_DLIO_BENCHMARK_TESTS", "On")
        cmake_args += [f"-DENABLE_DLIO_BENCHMARK_TESTS={enable_dlio_tests}"]

        # CMake lets you override the generator - we need to check this.
        # Can be set with Conda-Build, for example.
        cmake_generator = os.environ.get("CMAKE_GENERATOR", "")

        # Set Python_EXECUTABLE instead if you use PYBIND11_FINDPYTHON
        # EXAMPLE_VERSION_INFO shows you how to pass a value into the C++ code
        # from Python.

        #    f"-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={extdir}/lib",
        #    f"-DPYTHON_EXECUTABLE={sys.executable}",
        #    f"-DCMAKE_BUILD_TYPE={cfg}",  # not used on MSVC, but no harm
        #]
        build_args = []
        # Adding CMake arguments set as environment variable
        # (needed e.g. to build for ARM OSx on conda-forge)
        if "CMAKE_ARGS" in os.environ:
            cmake_args += [item for item in os.environ["CMAKE_ARGS"].split(" ") if item]

        # In this example, we pass in the version to C++. You might not need to.
        cmake_args += [f"-DEXAMPLE_VERSION_INFO={self.distribution.get_version()}"]


        # Set CMAKE_BUILD_PARALLEL_LEVEL to control the parallel build level
        # across all generators.
        build_args += [f"--", "-j"]

        build_temp = Path(self.build_temp) / ext.name
        if not build_temp.exists():
            build_temp.mkdir(parents=True)
        print("cmake", ext.sourcedir, cmake_args)
        subprocess.run(
            ["cmake", ext.sourcedir, *cmake_args], cwd=build_temp, check=True
        )
        subprocess.run(
            ["cmake", "--build", ".", *build_args], cwd=build_temp, check=True
        )
        subprocess.run(
            ["cmake", "--install", "."], cwd=build_temp, check=True
        )

import pathlib
here = pathlib.Path(__file__).parent.resolve()
long_description = (here / "README.md").read_text(encoding="utf-8")
# The information here can also be placed in setup.cfg - better separation of
# logic and declaration, and simpler if you include description/version in a file.
setup(
    name="dlio_profiler_py",
    version="0.0.1",
    description="I/O profiler for deep learning python apps. Specifically for dlio_benchmark.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hariharan-devarajan/dlio-profiler",
    author="Hariharan Devarajan (Hari)",
    classifiers=[  # Optional
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        "Development Status :: 3 - Alpha",
        # Indicate who your project is intended for
        "Intended Audience :: HPC",
        "Topic :: Software Development :: Build Tools",
        # Pick your license as you wish
        "License :: OSI Approved :: MIT License",
        # Specify the Python versions you support here. In particular, ensure
        # that you indicate you support Python 3. These classifiers are *not*
        # checked by 'pip install'. See instead 'python_requires' below.
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3 :: Only",
    ],
    install_requires=["pybind11"],
    requires=["pybind11"],
    keywords="profiler, deep learning, I/O, benchmark, NPZ, pytorch benchmark, tensorflow benchmark",
    project_urls={  # Optional
        "Bug Reports": "https://github.com/hariharan-devarajan/dlio-profiler/issues",
        "Source": "https://github.com/hariharan-devarajan/dlio-profiler",
    },
    packages=find_namespace_packages(where="."),
    package_dir={"dlio_profiler": "dlio_profiler"},
    ext_modules=[CMakeExtension("dlio_profiler_py")],
    cmdclass={"build_ext": CMakeBuild},
    zip_safe=False,
    extras_require={"test": ["pytest>=6.0"]},
    python_requires=">=3.7",
)
