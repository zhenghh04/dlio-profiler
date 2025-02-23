
#include <dlio_profiler/dlio_logger.h>
#include <pybind11/pybind11.h>
#include <dlio_profiler/utils/utils.h>
#include <pybind11/stl.h>
#include <iostream>
#include <fstream>


#include <stdio.h>
#include <execinfo.h>
#include <signal.h>
#include <stdlib.h>
#include <unistd.h>
#include <dlio_profiler/core/constants.h>
#include <dlio_profiler/core/dlio_profiler_main.h>

namespace py = pybind11;
namespace dlio_profiler {


    void initialize(const char *log_file, const char *data_dirs, int process_id) {
      dlio_profiler::Singleton<dlio_profiler::DLIOProfilerCore>::get_instance(ProfilerStage::PROFILER_INIT,
                                                                              ProfileType::PROFILER_PY_APP, log_file,
                                                                              data_dirs, &process_id);
    }

    TimeResolution get_time() {
      return dlio_profiler::Singleton<dlio_profiler::DLIOProfilerCore>::get_instance(ProfilerStage::PROFILER_OTHER,
                                                                                     ProfileType::PROFILER_PY_APP)->get_time();
    }

    void log_event(std::string &name, std::string &cat, TimeResolution start_time, TimeResolution duration,
                   std::unordered_map<std::string, int> &int_args,
                   std::unordered_map<std::string, std::string> &string_args,
                   std::unordered_map<std::string, float> &float_args) {
      auto args = std::unordered_map<std::string, std::any>();
      for (auto item:int_args) args.insert_or_assign(item.first, item.second);
      for (auto item:string_args) args.insert_or_assign(item.first, item.second);
      for (auto item:float_args) args.insert_or_assign(item.first, item.second);
      dlio_profiler::Singleton<dlio_profiler::DLIOProfilerCore>::get_instance(ProfilerStage::PROFILER_OTHER,
                                                                              ProfileType::PROFILER_PY_APP)->log(
              name.c_str(), cat.c_str(), start_time, duration, args);
    }

    void finalize() {
      dlio_profiler::Singleton<dlio_profiler::DLIOProfilerCore>::get_instance(ProfilerStage::PROFILER_FINI,
                                                                              ProfileType::PROFILER_PY_APP)->finalize();
    }
} // dlio_profiler
PYBIND11_MODULE(dlio_profiler_py, m) {
  m.doc() = "Python module for dlio_logger"; // optional module docstring
  m.def("initialize", &dlio_profiler::initialize, "initialize dlio profiler",
        py::arg("log_file") = nullptr,
        py::arg("data_dirs") = nullptr,
        py::arg("process_id") = -1);
  m.def("get_time", &dlio_profiler::get_time, "get time from profiler");
  m.def("log_event", &dlio_profiler::log_event, "log event with args",
        py::arg("name"), py::arg("cat"), py::arg("start_time"), py::arg("duration"),
        py::arg("int_args") = std::unordered_map<std::string, int>(),
        py::arg("string_args") = std::unordered_map<std::string, std::string>(),
        py::arg("float_args") = std::unordered_map<std::string, float>());
  m.def("finalize", &dlio_profiler::finalize, "finalize dlio profiler");
}

