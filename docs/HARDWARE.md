# Known hardware / required on-host verification

The operator reports:

- Intel Core Ultra 9 285K processor, hardware NPU and Intel integrated graphics.
- 128 GB DDR5 RAM.
- **2× Intel Arc Pro B70, 32 GB VRAM EACH**. No automatic 64 GB memory pooling assumed.
- Linux as the experiment host; existing local model serving and concurrent agent workloads must remain available.

**Do not presume** the motherboard PCIe lane mode, memory clock, Linux distro, kernel/driver level, Intel Level Zero packages, or XPU index mapping from historical descriptions. The first tool execution on the actual machine must determine them using read-only commands.

## Read-only quick check

```bash
cd /work/subtitle
export PYTHONPATH="$PWD/src"
mkdir -p output/RECEIPTS
python3 -m subtitle_lab doctor --out output/RECEIPTS/doctor-first.json
lspci -nn | grep -Ei 'VGA|3D|Display'
command -v sycl-ls && sycl-ls || true
command -v xpu-smi && xpu-smi discovery || true
```

The doctor includes GPU visibility through `torch.xpu` if PyTorch is already installed **in the active Python environment**; otherwise it truthfully reports no torch. That does **not** prove Intel driver absence. The agent may then create a separate venv/conda environment with official PyTorch XPU wheels for further testing.

**Critical verification:** print each `torch.xpu.get_device_properties(i).name`, `is_integrated_gpu`, and `total_memory`. It may list iGPU alongside discrete cards, and device ordering can change when environment filters change.

## Avoid harming the other inference system

- Determine active processes/VRAM pressure before heavy new model loads.
- Do not stop vLLM, existing models, launchers, or remote access to make memory without explicit permission.
- Keep Intel XPU nightly test env isolated from stable inference stack; pin working versions once identified.
- Do not assume the 285K's NPU runs a GPU-focused TTS model. OpenVINO NPU optimization is a separate performance research question, not a G3 prerequisite.
