#
# Copyright (C) Mellanox Technologies Ltd. 2001-2021.
#
# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
#

import os
import sys
from setuptools import setup
import torch
from torch.utils import cpp_extension

ucc_plugin_dir = os.path.dirname(os.path.abspath(__file__))
ucx_home = os.environ.get("UCX_HOME")
if ucx_home is None:
  print("Couldn't find UCX install dir, please set UCX_HOME env variable")
  sys.exit(1)

ucc_home = os.environ.get("UCC_HOME")
if ucc_home is None:
  print("Couldn't find UCC install dir, please set UCC_HOME env variable")
  sys.exit(1)

plugin_compile_args = []
enable_debug = os.environ.get("ENABLE_DEBUG")
if enable_debug is None or enable_debug == "no":
  print("Release build")
else:
  print("Debug build")
  plugin_compile_args.extend(["-g", "-O0"])

TORCH_MAJOR = int(torch.__version__.split('.')[0])
TORCH_MINOR = int(torch.__version__.split('.')[1])

def check_if_rocm_pytorch():
    is_rocm_pytorch = False
    if TORCH_MAJOR > 1 or (TORCH_MAJOR == 1 and TORCH_MINOR >= 5):
        from torch.utils.cpp_extension import ROCM_HOME
        is_rocm_pytorch = True if ((torch.version.hip is not None) and (ROCM_HOME is not None)) else False

    return is_rocm_pytorch

IS_ROCM_PYTORCH = check_if_rocm_pytorch()

plugin_sources      = ["src/torch_ucc.cpp",
                       "src/torch_ucc_comm.cpp"]
plugin_include_dirs = ["{}/include/".format(ucc_plugin_dir),
                       "{}/include/".format(ucx_home),
                       "{}/include/".format(ucc_home)]
plugin_library_dirs = ["{}/lib/".format(ucx_home),
                       "{}/lib/".format(ucc_home)]
plugin_libraries    = ["ucp", "uct", "ucm", "ucs", "ucc"]

if '--oss' in sys.argv:
  sys.argv.remove('--oss')
  plugin_sources += ["src/torch_ucc_init_oss.cpp"]
else:
  plugin_sources += ["src/torch_ucc_init.cpp"]

CUDA_TO_HIP_MAPPINGS = [
  ('UCS_MEMORY_TYPE_CUDA', 'UCS_MEMORY_TYPE_ROCM'),
  ('UCC_MEMORY_TYPE_CUDA', 'UCC_MEMORY_TYPE_ROCM')
]

# Overwrite each source file for hipification
def torch_ucc_hipify(src_path_list):
  for src_path in src_path_list:
    print("Torch-UCC hipification applied to " + src_path)
    with open(src_path, 'rt', encoding='utf-8') as fin:
      fin.seek(0)
      source = fin.read()
      for k, v in CUDA_TO_HIP_MAPPINGS:
        source = source.replace(k, v)
      fin.close()

    with open(src_path, 'wt', encoding='utf-8') as fout:
      fout.write(source)
      fout.close()


with_cuda = os.environ.get("WITH_CUDA")
if with_cuda is None or with_cuda == "no":
    print("CUDA support is disabled")
    module = cpp_extension.CppExtension(
        name = "torch_ucc",
        sources = plugin_sources,
        include_dirs = plugin_include_dirs,
        library_dirs = plugin_library_dirs,
        libraries = plugin_libraries,
        extra_compile_args=plugin_compile_args
    )
else:
    print("CUDA support is enabled")
    plugin_compile_args.append("-DUSE_CUDA")
    module = cpp_extension.CUDAExtension(
        name = "torch_ucc",
        sources = plugin_sources,
        include_dirs = plugin_include_dirs,
        library_dirs = plugin_library_dirs,
        libraries = plugin_libraries,
        extra_compile_args=plugin_compile_args
    )
    # Apply Torch-UCC specific hipification after Pytorch hipification
    if IS_ROCM_PYTORCH:
      torch_ucc_hipify(module.sources)

setup(
    name = "torch-ucc",
    version = "1.0.0",
    ext_modules = [module],
    cmdclass={'build_ext': cpp_extension.BuildExtension}
)
