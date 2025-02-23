//
// Created by haridev on 3/28/23.
//

#include <dlio_profiler/writer/chrome_writer.h>
#include <fcntl.h>
#include <dlio_profiler/core/macro.h>
#include <cassert>
#include <unistd.h>
#include <thread>
#include <sstream>
#include <cmath>

#define ERROR(cond, format, ...) \
  DLIO_PROFILER_LOGERROR(format, __VA_ARGS__); \
  if (this->throw_error) assert(cond);

void dlio_profiler::ChromeWriter::initialize(char *filename, bool throw_error) {
  this->throw_error = throw_error;
  this->filename = filename;
  if (fd == -1) {
    fd = dlp_open(filename, O_WRONLY | O_APPEND | O_CREAT, S_IRUSR | S_IWUSR);
    if (fd == -1) {
      ERROR(fd == -1, "unable to create log file %s", filename); // GCOVR_EXCL_LINE
    } else {
      DLIO_PROFILER_LOGINFO("created log file %s with fd %d", filename, fd);
    }
  }
}

void
dlio_profiler::ChromeWriter::log(std::string &event_name, std::string &category, TimeResolution &start_time,
                                 TimeResolution &duration,
                                 std::unordered_map<std::string, std::any> &metadata, ProcessID process_id, ThreadID thread_id) {
  if (fd != -1) {
    std::string json = convert_json(event_name, category, start_time, duration, metadata, process_id, thread_id);
    auto written_elements = dlp_write(fd, json.c_str(), json.size());
    if (written_elements != json.size()) {  // GCOVR_EXCL_START
      ERROR(written_elements != json.size(), "unable to log write %s fd %d for a+ written only %d of %d with error %s",
            filename.c_str(), fd, written_elements, json.size(), strerror(errno));
    }  // GCOVR_EXCL_STOP
  }
  is_first_write = false;
}

void dlio_profiler::ChromeWriter::finalize() {
  if (fd != -1) {
    DLIO_PROFILER_LOGINFO("Profiler finalizing writer %s\n", filename.c_str());
    int status = dlp_close(fd);
    if (status != 0) {
      ERROR(status != 0, "unable to close log file %d for a+", filename.c_str());  // GCOVR_EXCL_LINE
    }
    if (index == 0) {
      DLIO_PROFILER_LOGINFO("No trace data written. Deleting file %s", filename.c_str());
      dlp_unlink(filename.c_str());
    } else {
      fd = dlp_open(this->filename.c_str(), O_WRONLY);
      if (fd == -1) {
        ERROR(fd == -1, "unable to open log file %s with O_WRONLY", this->filename.c_str());  // GCOVR_EXCL_LINE
      }
      std::string data = "[\n";
      auto written_elements = dlp_write(fd, data.c_str(), data.size());
      if (written_elements != data.size()) {  // GCOVR_EXCL_START
        ERROR(written_elements != data.size(), "unable to finalize log write %s for r+ written only %d of %d",
              filename.c_str(), data.size(), written_elements);
      } // GCOVR_EXCL_STOP
      status = dlp_close(fd);
      if (status != 0) {
        ERROR(status != 0, "unable to close log file %d for r+", filename.c_str());  // GCOVR_EXCL_LINE
      }
      if (enable_compression) {
        if (system("which gzip > /dev/null 2>&1")) {
          DLIO_PROFILER_LOGERROR("Gzip compression does not exists", "");  // GCOVR_EXCL_LINE
        } else {
          DLIO_PROFILER_LOGINFO("Applying Gzip compression on file %s", filename.c_str());
          char cmd[2048];
          sprintf(cmd, "gzip %s", filename.c_str());
          int ret = system(cmd);
          if (ret == 0) {
            DLIO_PROFILER_LOGINFO("Successfully compressed file %s.gz", filename.c_str());
          } else
            DLIO_PROFILER_LOGERROR("Unable to compress file %s", filename.c_str());
        }
      }
    }
  }
  if (enable_core_affinity) {
    hwloc_topology_destroy(topology);
  }
}


std::string
dlio_profiler::ChromeWriter::convert_json(std::string &event_name, std::string &category, TimeResolution start_time,
                                          TimeResolution duration, std::unordered_map<std::string, std::any> &metadata,
                                          ProcessID process_id, ThreadID thread_id) {
  std::stringstream all_stream;
  if (is_first_write) all_stream << "   ";
  all_stream << R"({"id":")" << index++ << "\","
             << R"("name":")" << event_name << "\","
             << R"("cat":")" << category << "\","
             << "\"pid\":" << process_id << ","
             << "\"tid\":" << thread_id << ","
             << "\"ts\":" << start_time << ","
             << "\"dur\":" << duration << ","
             << R"("ph":"X",)"
             << R"("args":{)";
  if (include_metadata) {
    all_stream << "\"hostname\":\"" << hostname() << "\"";
    auto cores = core_affinity();
    auto cores_size = cores.size();
    if (cores_size > 0) {
      all_stream << ", \"core_affinity\": [";
      for (int i = 0; i < cores_size; ++i) {
        all_stream << cores[i];
        if (i < cores_size - 1) all_stream << ",";
      }
      all_stream << "]";
    }
    bool has_meta = false;
    std::stringstream meta_stream;
    auto meta_size = metadata.size();
    int i = 0;
    for (auto item : metadata) {
      has_meta = true;
      if (item.second.type() == typeid(unsigned int)) {
        meta_stream << "\"" << item.first << "\":" << std::any_cast<unsigned int>(item.second);
        if (i < meta_size - 1) meta_stream << ",";
      } else if (item.second.type() == typeid(int)) {
        meta_stream << "\"" << item.first << "\":" << std::any_cast<int>(item.second);
        if (i < meta_size - 1) meta_stream << ",";
      } else if (item.second.type() == typeid(const char *)) {
        meta_stream << "\"" << item.first << "\":\"" << std::any_cast<const char *>(item.second) << "\"";
        if (i < meta_size - 1) meta_stream << ",";
      } else if (item.second.type() == typeid(std::string)) {
        meta_stream << "\"" << item.first << "\":\"" << std::any_cast<std::string>(item.second) << "\"";
        if (i < meta_size - 1) meta_stream << ",";
      } else if (item.second.type() == typeid(size_t)) {
        meta_stream << "\"" << item.first << "\":\"" << std::any_cast<size_t>(item.second) << "\"";
        if (i < meta_size - 1) meta_stream << ",";
      } else if (item.second.type() == typeid(long)) {
        meta_stream << "\"" << item.first << "\":\"" << std::any_cast<long>(item.second) << "\"";
        if (i < meta_size - 1) meta_stream << ",";
      } else if (item.second.type() == typeid(ssize_t)) {
        meta_stream << "\"" << item.first << "\":\"" << std::any_cast<ssize_t>(item.second) << "\"";
        if (i < meta_size - 1) meta_stream << ",";
      } else if (item.second.type() == typeid(off_t)) {
        meta_stream << "\"" << item.first << "\":\"" << std::any_cast<off_t>(item.second) << "\"";
        if (i < meta_size - 1) meta_stream << ",";
      } else if (item.second.type() == typeid(off64_t)) {
        meta_stream << "\"" << item.first << "\":\"" << std::any_cast<off64_t>(item.second) << "\"";
        if (i < meta_size - 1) meta_stream << ",";
      } else {
        DLIO_PROFILER_LOGINFO("No conversion for type %s", item.first);
      }
      i++;
    }
    if (has_meta) {
      all_stream << ", " << meta_stream.str();
    }
  }
  all_stream << "}";
  all_stream << "}\n";
  DLIO_PROFILER_LOGINFO("event logged %s into %s", all_stream.str().c_str(), this->filename.c_str());
  return all_stream.str();
}
