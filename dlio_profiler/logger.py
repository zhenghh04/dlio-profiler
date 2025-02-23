from functools import wraps
from typing import Dict
import os

DLIO_PROFILER_ENABLE_ENV = "DLIO_PROFILER_ENABLE"
DLIO_PROFILER_INIT_ENV = "DLIO_PROFILER_INIT"

DLIO_PROFILER_ENABLE = True if os.getenv(DLIO_PROFILER_ENABLE_ENV, '1') == '1' else False
DLIO_PROFILER_INIT_PRELOAD = True if os.getenv(DLIO_PROFILER_INIT_ENV, 'PRELOAD') == 'PRELOAD' else False

if DLIO_PROFILER_ENABLE:
    import dlio_profiler_py as profiler

from pathlib import Path
import inspect
import sys, signal


def capture_signal(signal_number, frame):
    dlio_logger.get_instance().finalize()
    sys.exit(1)


signal.signal(signal.SIGABRT, capture_signal)


class dlio_logger:
    __instance = None

    def __init__(self, logfile):
        if DLIO_PROFILER_ENABLE:
            self.logfile = logfile
            self.logger = None
        dlio_logger.__instance = self

    @classmethod
    def get_instance(cls, log_file=None):
        """ Static access method. """
        if dlio_logger.__instance is None:
            dlio_logger(log_file)
        return dlio_logger.__instance

    @staticmethod
    def initialize_log(logfile, data_dir, process_id):
        log_file = None
        if logfile:
            log_file = Path(logfile)
        instance = dlio_logger.get_instance(log_file)
        if DLIO_PROFILER_ENABLE:
            if log_file:
                os.makedirs(log_file.parent, exist_ok=True)
                if os.path.isfile(log_file):
                    os.remove(log_file)
            instance.logger = profiler
            if log_file:
                log_file = f"{instance.logfile}"
            if data_dir:
                data_dir = f"{data_dir}"
            instance.logger.initialize(log_file=log_file, data_dirs=data_dir, process_id=process_id)
        return instance

    def get_time(self):
        if DLIO_PROFILER_ENABLE:
            return self.logger.get_time()
        return 0

    def log_event(self, name, cat, start_time, duration, int_args=None):
        if DLIO_PROFILER_ENABLE:
            if int_args is None:
                int_args = {}
            self.logger.log_event(name=name, cat=cat, start_time=start_time, duration=duration, int_args=int_args)

    def finalize(self):
        if DLIO_PROFILER_ENABLE:
            self.logger.finalize()


class fn_interceptor(object):

    def __init__(self, cat, name=None, epoch=None, step=None, image_idx=None, image_size=None):
        if DLIO_PROFILER_ENABLE:
            if not name:
                name = inspect.stack()[1].function
            self._name = name
            self._cat = cat
            self._arguments: Dict[str, str] = {}
            if epoch is not None: self._arguments["epoch"] = str(epoch)
            if step is not None: self._arguments["step"] = str(step)
            if image_idx is not None: self._arguments["image_idx"] = str(image_idx)
            if image_size is not None: self._arguments["image_size"] = str(image_size)
            self.reset()

    def __enter__(self):
        if DLIO_PROFILER_ENABLE:
            self._t1 = dlio_logger.get_instance().get_time()
        return self

    def update(self, epoch=None, step=None, image_idx=None, image_size=None, args={}):
        if DLIO_PROFILER_ENABLE:
            if epoch is not None: self._arguments["epoch"] = str(epoch)
            if step is not None: self._arguments["step"] = str(step)
            if image_idx is not None: self._arguments["image_idx"] = str(image_idx)
            if image_size is not None: self._arguments["image_size"] = str(image_size)
            for key, value in args.items():
                self._arguments[key] = str(value)
        return self

    def flush(self):
        if DLIO_PROFILER_ENABLE:
            self._t2 = dlio_logger.get_instance().get_time()
            if len(self._arguments) > 0:
                dlio_logger.get_instance().log_event(name=self._name, cat=self._cat, start_time=self._t1,
                                                     duration=self._t2 - self._t1,
                                                     string_args=self._arguments)
            else:
                dlio_logger.get_instance().log_event(name=self._name, cat=self._cat, start_time=self._t1,
                                                     duration=self._t2 - self._t1)
            self._flush = True
        return self

    def reset(self):
        if DLIO_PROFILER_ENABLE:
            self._t1 = dlio_logger.get_instance().get_time()
            self._t2 = self._t1
            self._flush = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if DLIO_PROFILER_ENABLE:
            if not self._flush:
                self.flush()

    def log(self, func):
        if DLIO_PROFILER_ENABLE:
            arg_names = inspect.getfullargspec(func)[0]

        @wraps(func)
        def wrapper(*args, **kwargs):
            if DLIO_PROFILER_ENABLE:
                if "self" == arg_names[0]:
                    if hasattr(args[0], "epoch"):
                        self._arguments["epoch"] = str(args[0].epoch)
                    if hasattr(args[0], "step"):
                        self._arguments["step"] = str(args[0].step)
                    if hasattr(args[0], "image_size"):
                        self._arguments["image_size"] = str(args[0].image_size)
                    if hasattr(args[0], "image_idx"):
                        self._arguments["image_idx"] = str(args[0].image_idx)
                for name, value in zip(arg_names[1:], kwargs):
                    if hasattr(args, name):
                        setattr(args, name, value)
                        if name == "epoch":
                            self._arguments["epoch"] = str(value)
                        elif name == "image_idx":
                            self._arguments["image_idx"] = str(value)
                        elif name == "image_size":
                            self._arguments["image_size"] = str(value)
                        elif name == "step":
                            self._arguments["image_size"] = str(value)

                start = dlio_logger.get_instance().get_time()
            x = func(*args, **kwargs)
            if DLIO_PROFILER_ENABLE:
                end = dlio_logger.get_instance().get_time()
                if len(self._arguments) > 0:
                    dlio_logger.get_instance().log_event(name=func.__qualname__, cat=self._cat, start_time=start,
                                                         duration=end - start,
                                                         string_args=self._arguments)
                else:
                    dlio_logger.get_instance().log_event(name=func.__qualname__, cat=self._cat, start_time=start,
                                                         duration=end - start)
            return x

        return wrapper

    def iter(self, func, iter_name="step"):
        if DLIO_PROFILER_ENABLE:
            iter_val = 1
            name = f"{self._name}.iter"
            kernal_name = f"{self._name}.yield"
            start = dlio_logger.get_instance().get_time()
        for v in func:
            if DLIO_PROFILER_ENABLE:
                end = dlio_logger.get_instance().get_time()
                t0 = dlio_logger.get_instance().get_time()
            yield v
            if DLIO_PROFILER_ENABLE:
                t1 = dlio_logger.get_instance().get_time()
                self._arguments[iter_name] = str(iter_val)
                if len(self._arguments) > 0:
                    dlio_logger.get_instance().log_event(name=name, cat=self._cat, start_time=start,
                                                         duration=end - start,
                                                         int_args=self._arguments)
                    dlio_logger.get_instance().log_event(name=kernal_name, cat=self._cat, start_time=t0,
                                                         duration=t1 - t0,
                                                         int_args=self._arguments)
                else:
                    dlio_logger.get_instance().log_event(name=name, cat=self._cat, start_time=start,
                                                         duration=end - start)
                    dlio_logger.get_instance().log_event(name=kernal_name, cat=self._cat, start_time=t0,
                                                         duration=t1 - t0)
                iter_val += 1
                start = dlio_logger.get_instance().get_time()

    def log_init(self, init):
        if DLIO_PROFILER_ENABLE:
            arg_names = inspect.getfullargspec(init)[0]

        @wraps(init)
        def new_init(args, *kwargs):
            if DLIO_PROFILER_ENABLE:
                for name, value in zip(arg_names[1:], kwargs):
                    setattr(args, name, value)
                    if name == "epoch":
                        self._arguments["epoch"] = str(value)
                start = dlio_logger.get_instance().get_time()
            init(args, *kwargs)
            if DLIO_PROFILER_ENABLE:
                end = dlio_logger.get_instance().get_time()

                if len(self._arguments) > 0:
                    dlio_logger.get_instance().log_event(name=init.__qualname__, cat=self._cat, start_time=start,
                                                         duration=end - start,
                                                         int_args=self._arguments)
                else:
                    dlio_logger.get_instance().log_event(name=init.__qualname__, cat=self._cat, start_time=start,
                                                         duration=end - start)

        return new_init
