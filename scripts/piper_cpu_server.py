#!/usr/bin/env python3
"""Run upstream Piper HTTP with explicitly bounded ONNX session options.

Piper 1.8.0 does not expose these options through its HTTP CLI. This process-local
shim leaves installed source untouched and keeps the upstream HTTP implementation.
"""
import runpy
import onnxruntime

original_options = onnxruntime.SessionOptions


def bounded_options():
    options = original_options()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    options.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL
    options.add_session_config_entry('session.intra_op.allow_spinning', '0')
    options.add_session_config_entry('session.inter_op.allow_spinning', '0')
    return options


if __name__ == '__main__':
    onnxruntime.SessionOptions = bounded_options
    runpy.run_module('piper.http_server', run_name='__main__')
